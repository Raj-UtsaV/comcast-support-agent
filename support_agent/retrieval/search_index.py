"""Search one company's historical evidence using normalized FAISS vectors."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy

import faiss
import numpy as np

from support_agent.shared.config import ConfigError


def _search_settings(config: dict) -> dict:
    try:
        settings = deepcopy(config["retrieval"])

        if settings["provider"] != "faiss" or settings["similarity"] != "cosine":
            raise ConfigError("Only FAISS cosine search is currently supported.")

        if type(settings["top_k"]) is not int or settings["top_k"] < 1:
            raise ConfigError("retrieval.top_k must be a positive integer.")

        threshold = settings["min_similarity"]

        if type(threshold) not in (int, float) or not -1 <= threshold <= 1:
            raise ConfigError("retrieval.min_similarity must be between -1 and 1.")

        if type(settings["filter_by_intent"]) is not bool:
            raise ConfigError("retrieval.filter_by_intent must be a boolean.")

        return settings
    except (KeyError, TypeError):
        raise ConfigError("Missing or invalid retrieval configuration.") from None


def _unit_vectors(values, rows: int, dimension: int) -> np.ndarray:
    """Copy and normalize vectors without changing the caller's arrays."""

    raw = np.asarray(values)

    if raw.dtype.kind not in "fiu":
        raise ValueError("Search vectors must contain real numbers.")

    vectors = np.array(raw, dtype=np.float32, order="C", copy=True)

    if vectors.shape != (rows, dimension) or not np.isfinite(vectors).all():
        raise ValueError("Search vectors have invalid shape or nonfinite values.")

    lengths = np.linalg.norm(vectors.astype(np.float64), axis=1, keepdims=True)

    if (lengths == 0).any():
        raise ValueError("Cosine search cannot use zero vectors.")

    vectors /= lengths

    return vectors


def _evidence_records(records: Sequence[dict], company_id: str) -> tuple:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise TypeError("Evidence records must be a sequence of mappings.")

    copied = deepcopy(tuple(records))
    seen = set()

    for row in copied:
        if not isinstance(row, dict):
            raise TypeError("Each evidence record must be a mapping.")

        for key in (
            "evidence_id",
            "conversation_id",
            "customer_message_id",
            "reply_message_id",
            "customer_text",
            "reply_text",
            "timestamp",
        ):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Evidence requires a nonempty {key}.")

        if row.get("company_id") != company_id or row.get("split") != "train":
            raise ValueError("Evidence must belong to this company's training split.")

        if row.get("resolution_verified") is not False:
            raise ValueError("Historical evidence must retain unverified resolution.")

        intent = row.get("intent")

        if intent is not None and (not isinstance(intent, str) or not intent.strip()):
            raise ValueError("Evidence intent must be a nonempty label or null.")

        if row["evidence_id"] in seen:
            raise ValueError("Evidence IDs must be unique within an index.")

        seen.add(row["evidence_id"])

    return copied


class FaissSearchIndex:
    """Immutable in-memory evidence index; model loading and disk IO live elsewhere."""

    def __init__(self, config: dict, records: Sequence[dict], vectors, *, embedding_identity: dict):
        self._settings = _search_settings(config)
        self._company_id = config["company"]["id"]

        if not isinstance(self._company_id, str) or not self._company_id.strip():
            raise ConfigError("Search requires a nonempty company ID.")

        if not isinstance(embedding_identity, dict) or any(
            not isinstance(embedding_identity.get(key), str)
            or not embedding_identity[key].strip()
            for key in ("provider", "name", "revision")
        ):
            raise ValueError("Search requires the encoder's model identity.")

        dimension = embedding_identity.get("dimension")

        if type(dimension) is not int or dimension < 1:
            raise ValueError("Embedding identity requires a positive dimension.")

        self._embedding_identity = deepcopy(embedding_identity)
        self._records = _evidence_records(records, self._company_id)
        normalized = _unit_vectors(vectors, len(self._records), dimension)
        self._index = faiss.IndexFlatIP(dimension)
        self._index.add(normalized)

    @property
    def size(self) -> int:
        return self._index.ntotal

    @property
    def company_id(self) -> str:
        return self._company_id

    @property
    def embedding_identity(self) -> dict:
        return deepcopy(self._embedding_identity)

    def search(self, query_vector, *, company_id: str, embedding_identity: dict, intent: str | None = None) -> list[dict]:
        """Return descending matches, with one evidence record per conversation."""

        if company_id != self._company_id:
            raise ValueError("The requested company does not own this index.")

        if embedding_identity != self._embedding_identity:
            raise ValueError(
                "The query encoder does not match the index's model identity."
            )

        if intent is not None and (not isinstance(intent, str) or not intent.strip()):
            raise ValueError("Search intent must be a nonempty label or null.")

        query = _unit_vectors(query_vector, 1, self._embedding_identity["dimension"])

        if not self.size or (self._settings["filter_by_intent"] and intent is None):
            return []

        # Inspect all candidates so filtering/deduplication cannot hide valid matches.
        scores, positions = self._index.search(query, self.size)
        candidates = sorted(
            zip(scores[0], positions[0], strict=True),
            key=lambda item: (-float(item[0]), self._records[item[1]]["evidence_id"]),
        )
        results, conversations = [], set()

        for score, position in candidates:
            similarity = float(np.clip(score, -1.0, 1.0))

            if similarity < self._settings["min_similarity"]:
                break

            row = self._records[position]

            if self._settings["filter_by_intent"] and row.get("intent") != intent:
                continue

            if row["conversation_id"] in conversations:
                continue

            conversations.add(row["conversation_id"])
            results.append({"evidence": deepcopy(row), "similarity": similarity})

            if len(results) == self._settings["top_k"]:
                break

        return results


def create_search_index(config: dict, records: Sequence[dict], vectors, *, embedding_identity: dict) -> FaissSearchIndex:
    """Build the configured search provider from already selected/encoded evidence."""

    return FaissSearchIndex(
        config, records, vectors, embedding_identity=embedding_identity
    )
