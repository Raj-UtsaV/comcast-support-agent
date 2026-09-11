"""Prepare missing data and build or validate a reusable local search index."""

from pathlib import Path

from support_agent.data.preparation import prepare_data
from support_agent.embeddings.encoder import create_embedder
from support_agent.retrieval.index_state import source_state, storage_directory
from support_agent.retrieval.index_store import build_saved_index, load_saved_index
from support_agent.shared.config import ConfigError


def setup_pipeline(config, *, rebuild=False):
    processed = Path(config["paths"]["processed_dir"])
    prepared = not processed.exists()
    if prepared:
        print("Preparing customer conversations...")
        prepare_data(config)
    else:
        print("Using existing processed data.")
    # Validate required processed inputs before loading/downloading the model.
    source_state(config)

    exists = (storage_directory(config) / "current.json").exists()
    if exists and not rebuild:
        print("Verifying existing index...")
        index = load_saved_index(config)
    else:
        print("Loading embedding model (downloads missing weights on first use)...")
        encoder = create_embedder(config, local_files_only=False)
        print("Encoding evidence and building the vector index...")
        build_saved_index(config, rebuild=rebuild, embedder=encoder)
        index = load_saved_index(config)

    return {
        "company_id": index.company_id,
        "status": "ready",
        "processed_data": "created" if prepared else "reused",
        "index": "reused" if exists and not rebuild else "built",
        "indexed_pairs": index.size,
    }
