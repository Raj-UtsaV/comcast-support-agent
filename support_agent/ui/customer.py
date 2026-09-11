"""Customer conversation runtime with index revision caching."""
import json
from functools import lru_cache
from support_agent.agent.runtime import create_agent
from support_agent.retrieval.index_state import source_state, storage_directory
from support_agent.ui.conversation import respond


@lru_cache(maxsize=8)
def customer_runtime(config_json, revision):
    return create_agent(json.loads(config_json))


def answer(config, messages, text):
    revision = json.dumps(source_state(config), sort_keys=True) + (
        storage_directory(config) / "current.json"
    ).read_text()
    runtime = customer_runtime(json.dumps(config, sort_keys=True), revision)
    return respond(config, runtime, messages, text)
