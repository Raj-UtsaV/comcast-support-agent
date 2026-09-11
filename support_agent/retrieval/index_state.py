"""Fingerprint the data and implementation used to build saved evidence."""

import hashlib
import json
import re
from importlib.metadata import version
from pathlib import Path

from support_agent.data.evidence import SPLITS
from support_agent.shared.config import ConfigError


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def storage_directory(config: dict) -> Path:
    company = config["company"]["id"]

    if not isinstance(company, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]*", company
    ):
        raise ConfigError("Saved indexes require a company ID without path separators.")

    return Path(config["paths"]["artifacts_dir"]) / company / "search"


def check_encoder(config: dict, identity: dict) -> None:
    settings = config["models"]["embedding"]

    if not isinstance(identity, dict) or any(
        identity.get(key) != settings[key]
        for key in ("provider", "name", "revision", "normalize_embeddings")
    ):
        raise ValueError("Saved-index encoder does not match embedding configuration.")


def source_state(config: dict) -> dict:
    """Use content hashes, not absolute paths, so a project can be moved."""

    processed = Path(config["paths"]["processed_dir"])
    files = {
        name: file_hash(processed / name)
        for name in ["manifest.json", *(f"{split}.jsonl" for split in SPLITS)]
    }
    golden = Path(config["paths"]["golden_labels"])
    files["golden_annotations"] = file_hash(golden) if golden.exists() else None
    embedding = config["models"]["embedding"]
    settings = {
        "company_id": config["company"]["id"],
        "dataset": config["dataset"],
        "splits": config["splits"],
        "embedding": {
            key: embedding[key]
            for key in ("provider", "name", "revision", "normalize_embeddings")
        },
        "retrieval": {
            key: config["retrieval"][key] for key in ("provider", "similarity")
        },
    }
    directory = Path(__file__).resolve().parents[1]
    implementation = {
        name: file_hash(directory / name)
        for name in (
            "shared/config.py",
            "shared/text.py",
            "data/splits.py",
            "data/evidence.py",
            "embeddings/encoder.py",
            "retrieval/search_index.py",
            "retrieval/index_state.py",
            "retrieval/index_store.py",
        )
    }

    return {
        "files": files,
        "settings_sha256": hashlib.sha256(json_bytes(settings)).hexdigest(),
        "implementation": implementation,
        "dependencies": {
            name: version(name)
            for name in (
                "numpy",
                "faiss-cpu",
                "sentence-transformers",
                "torch",
                "transformers",
            )
        },
    }
