"""Build and reload versioned evidence/vector files without re-encoding text."""

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from support_agent.data.evidence import collect_evidence
from support_agent.embeddings.encoder import TextEmbedder, create_embedder
from support_agent.retrieval.index_state import (
    check_encoder,
    file_hash,
    json_bytes,
    source_state,
    storage_directory,
)
from support_agent.retrieval.search_index import FaissSearchIndex, create_search_index


def build_saved_index(config: dict, *, rebuild: bool = False, embedder: TextEmbedder | None = None) -> FaissSearchIndex:
    """Publish a complete generation; retain previous generations on rebuild."""

    if type(rebuild) is not bool:
        raise TypeError("rebuild must be a boolean.")

    root = storage_directory(config)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".build-lock"

    try:
        lock.mkdir()
    except FileExistsError:
        raise FileExistsError(
            "An index build is active, or its interrupted-build lock needs review."
        ) from None

    generation, pointer = None, None
    published = False

    try:
        if (root / "current.json").exists() and not rebuild:
            raise FileExistsError(
                "A saved index exists; use rebuild=True to publish a new version."
            )

        before = source_state(config)
        records, counts = collect_evidence(config)
        encoder = embedder if embedder is not None else create_embedder(config)
        identity = encoder.identity
        check_encoder(config, identity)
        vectors = encoder.encode([record["customer_text"] for record in records])
        index = create_search_index(
            config, records, vectors, embedding_identity=identity
        )
        generation = Path(tempfile.mkdtemp(prefix="index-", dir=root))

        with (generation / "evidence.jsonl").open("wb") as stream:
            for record in records:
                stream.write(json_bytes(record) + b"\n")

        np.save(generation / "vectors.npy", vectors, allow_pickle=False)
        manifest = {
            "schema_version": 1,
            "company_id": config["company"]["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_identity": identity,
            "source_state": before,
            "record_count": index.size,
            "selection_counts": counts,
            "files": {
                name: file_hash(generation / name)
                for name in ("evidence.jsonl", "vectors.npy")
            },
        }
        (generation / "manifest.json").write_bytes(json_bytes(manifest))

        if source_state(config) != before:
            raise ValueError(
                "Source data or settings changed during the index build; retry."
            )

        with tempfile.NamedTemporaryFile(
            dir=root, prefix=".current-", delete=False
        ) as stream:
            pointer = Path(stream.name)
            stream.write(
                json_bytes(
                    {
                        "generation": generation.name,
                        "manifest_sha256": file_hash(generation / "manifest.json"),
                    }
                )
            )

        os.replace(pointer, root / "current.json")
        published = True

        return index
    finally:
        if pointer is not None:
            pointer.unlink(missing_ok=True)

        if generation is not None and not published:
            shutil.rmtree(generation)

        lock.rmdir()


def load_saved_index(config: dict) -> FaissSearchIndex:
    """Validate one complete generation and recreate FAISS from saved vectors."""

    root = storage_directory(config).resolve()

    try:
        pointer = json.loads((root / "current.json").read_bytes())
        name = pointer["generation"]

        if not isinstance(name, str) or not re.fullmatch(r"index-[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid saved-index generation name.")

        generation = (root / name).resolve()

        if generation.parent != root:
            raise ValueError(
                "Saved-index generation must remain inside its company directory."
            )

        manifest_bytes = (generation / "manifest.json").read_bytes()

        if hashlib.sha256(manifest_bytes).hexdigest() != pointer["manifest_sha256"]:
            raise ValueError("Saved-index manifest checksum mismatch.")

        manifest = json.loads(manifest_bytes)

        if (
            manifest["schema_version"] != 1
            or manifest["company_id"] != config["company"]["id"]
        ):
            raise ValueError("Saved index has an incompatible schema or company.")

        before = source_state(config)

        if manifest["source_state"] != before:
            raise ValueError("Saved index is stale; reselect evidence and rebuild it.")

        identity = manifest["embedding_identity"]
        check_encoder(config, identity)
        contents = {}

        for filename in ("evidence.jsonl", "vectors.npy"):
            contents[filename] = (generation / filename).read_bytes()

            if (
                hashlib.sha256(contents[filename]).hexdigest()
                != manifest["files"][filename]
            ):
                raise ValueError(f"Saved-index {filename} checksum mismatch.")

        records = [json.loads(line) for line in contents["evidence.jsonl"].splitlines()]
        vectors = np.load(io.BytesIO(contents["vectors.npy"]), allow_pickle=False)

        if (
            type(manifest["record_count"]) is not int
            or len(records) != manifest["record_count"]
        ):
            raise ValueError("Saved-index record count does not match its manifest.")

        index = create_search_index(
            config, records, vectors, embedding_identity=identity
        )

        if source_state(config) != before:
            raise ValueError(
                "Source data or settings changed while loading the index; retry."
            )

        return index
    except FileNotFoundError:
        raise FileNotFoundError(
            "Saved index or required prepared data is missing; prepare/build it first."
        ) from None
    except (KeyError, TypeError, UnicodeError) as error:
        raise ValueError("Saved-index metadata is incomplete or malformed.") from error
