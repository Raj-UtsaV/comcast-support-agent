"""Convert text into numerical vectors using a configured pretrained model."""

from __future__ import annotations

import re
from collections.abc import Sequence
from copy import deepcopy
from importlib.metadata import version
from typing import Protocol

import numpy as np

from support_agent.shared.config import ConfigError


class TextEmbedder(Protocol):
    """Small interface that later search code can use with different providers."""

    @property
    def dimension(self) -> int: ...

    @property
    def identity(self) -> dict: ...

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


def _settings(config: dict) -> dict:
    try:
        settings = deepcopy(config["models"]["embedding"])

        if settings["provider"] != "sentence_transformers":
            raise ConfigError("Unsupported embedding provider.")

        if not isinstance(settings["name"], str) or not re.fullmatch(
            r"[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*", settings["name"]
        ):
            raise ConfigError("Embedding name must be a full Hub repository ID.")

        if not isinstance(settings["revision"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", settings["revision"]
        ):
            raise ConfigError("Embedding revision must be a full model commit hash.")

        if type(settings["batch_size"]) is not int or settings["batch_size"] < 1:
            raise ConfigError("Embedding batch_size must be a positive integer.")

        if type(settings["normalize_embeddings"]) is not bool:
            raise ConfigError("Embedding normalize_embeddings must be a boolean.")

        if not isinstance(settings["device"], str) or not re.fullmatch(
            r"cpu|mps|cuda(?::[0-9]+)?", settings["device"]
        ):
            raise ConfigError("Embedding device must be cpu, mps, cuda or cuda:N.")

        cache = config["paths"]["model_cache"]

        if not isinstance(cache, str) or not cache.strip():
            raise ConfigError("paths.model_cache is required.")

        settings["cache_folder"] = cache

        return settings
    except (KeyError, TypeError):
        raise ConfigError("Missing or invalid embedding configuration.") from None


class SentenceTransformerEmbedder:
    """Load one local encoder and reuse it across batches of texts."""

    def __init__(self, config: dict, *, local_files_only: bool = True):
        settings = _settings(config)

        if type(local_files_only) is not bool:
            raise TypeError("local_files_only must be a boolean.")

        # Import only when constructing an encoder, not during data preparation.
        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(
                settings["name"],
                revision=settings["revision"],
                device=settings["device"],
                cache_folder=settings["cache_folder"],
                local_files_only=local_files_only,
                trust_remote_code=False,
                token=False,
            )
        except (OSError, ValueError, RuntimeError) as error:
            mode = "local cache" if local_files_only else "model download/cache"
            raise RuntimeError(
                f"Cannot load the embedding model from {mode}. "
                "Check the configured model, revision, device and cache; "
                "the first download requires local_files_only=False."
            ) from error

        dimension = self._model.get_embedding_dimension()

        if type(dimension) is not int or dimension < 1:
            raise ValueError("Embedding model must report a positive vector dimension.")

        self._settings = settings
        self._identity = {
            "provider": settings["provider"],
            "name": settings["name"],
            "revision": settings["revision"],
            "normalize_embeddings": settings["normalize_embeddings"],
            "dimension": dimension,
            "max_sequence_length": self._model.max_seq_length,
            "sentence_transformers_version": version("sentence-transformers"),
        }

    @property
    def dimension(self) -> int:
        return self._identity["dimension"]

    @property
    def identity(self) -> dict:
        """Describe the encoder for a future index compatibility check."""

        return deepcopy(self._identity)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one float32 row per text, preserving input order."""

        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise TypeError("Pass a sequence of strings, such as [message].")

        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be nonempty strings.")

        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        vectors = np.array(
            self._model.encode(
                list(texts),
                batch_size=self._settings["batch_size"],
                normalize_embeddings=self._settings["normalize_embeddings"],
                precision="float32",
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
            order="C",
            copy=True,
        )

        if (
            vectors.shape != (len(texts), self.dimension)
            or not np.isfinite(vectors).all()
        ):
            raise ValueError("Embedding model returned invalid vector shape or values.")

        lengths = np.linalg.norm(vectors.astype(np.float64), axis=1, keepdims=True)

        if (lengths == 0).any():
            raise ValueError("Embedding model returned a zero vector.")

        if self._settings["normalize_embeddings"]:
            vectors /= lengths

        return vectors


def create_embedder(config: dict, *, local_files_only: bool = True) -> TextEmbedder:
    """Construct the configured provider; unsupported providers fail explicitly."""

    return SentenceTransformerEmbedder(config, local_files_only=local_files_only)
