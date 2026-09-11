"""Construct reusable company runtimes while checking index freshness."""

from copy import deepcopy
from threading import Lock
from typing import Protocol

import numpy as np

from support_agent.agent.taxonomy import approved_categories
from support_agent.agent.workflow import SupportAgent
from support_agent.embeddings.encoder import create_embedder
from support_agent.models.client import create_generator
from support_agent.retrieval.index_state import source_state
from support_agent.retrieval.index_store import load_saved_index
from support_agent.shared.config import ConfigError


class VectorStore(Protocol):
    @property
    def embedding_identity(self) -> dict: ...

    def search(self, query_vector: np.ndarray, *, company_id: str, embedding_identity: dict, intent: str | None = None) -> list[dict]: ...


class SavedRetriever:
    def __init__(self, config):
        self.config = deepcopy(config)
        before = source_state(config)
        self.index: VectorStore = load_saved_index(config)
        self.state = source_state(config)
        if before != self.state:
            raise ValueError("Retrieval inputs changed during runtime loading.")
        self.encoder = create_embedder(config)
        self.lock = Lock()

        if self.encoder.identity != self.index.embedding_identity:
            raise ValueError("Query encoder differs from the saved index model.")

    def search(self, message, intent=None):
        # Never silently reuse a resource cached before golden/data changes.
        if source_state(self.config) != self.state:
            raise ValueError(
                "Retrieval inputs changed; rebuild the index and reload the runtime."
            )

        with self.lock:
            vector = self.encoder.encode([message])
            result = self.index.search(
                vector,
                company_id=self.config["company"]["id"],
                embedding_identity=self.encoder.identity,
                intent=intent,
            )

        if source_state(self.config) != self.state:
            raise ValueError(
                "Retrieval inputs changed during search; retry after rebuilding."
            )

        return result


def create_agent(config) -> SupportAgent:
    approved_categories(config)
    generator = create_generator(config)
    return SupportAgent(config, generator, SavedRetriever(config))
