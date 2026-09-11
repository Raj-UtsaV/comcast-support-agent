"""Use real FAISS with synthetic records and small, known numerical vectors."""

from copy import deepcopy

import numpy as np
import pytest
import yaml

from support_agent.retrieval.search_index import create_search_index
from support_agent.shared.config import PROJECT_ROOT, ConfigError


def record(identifier, conversation, intent=None):
    return {
        "company_id": "example",
        "evidence_id": identifier,
        "conversation_id": conversation,
        "customer_message_id": f"question-{identifier}",
        "reply_message_id": f"reply-{identifier}",
        "customer_text": "Synthetic customer question.",
        "reply_text": "Synthetic historical support reply for testing.",
        "timestamp": "2020-01-01T00:00:00+00:00",
        "split": "train",
        "intent": intent,
        "resolution_verified": False,
    }


@pytest.fixture
def inputs():
    config = yaml.safe_load((PROJECT_ROOT / "configs/base.yaml").read_text())
    config["company"]["id"] = "example"
    config["retrieval"].update(top_k=2, min_similarity=0.5)
    records = [
        record("a", "one"),
        record("b", "one"),
        record("c", "two"),
        record("d", "three"),
    ]
    vectors = np.array([[3, 0], [4, 3], [3, 4], [0, 4]], dtype=np.float64)
    identity = {
        "provider": "synthetic_test",
        "name": "known-vectors",
        "revision": "fixture-v1",
        "dimension": 2,
    }

    return config, records, vectors, identity


def build(inputs):
    config, records, vectors, identity = inputs
    return create_search_index(config, records, vectors, embedding_identity=identity)


def search(index, query=None, **overrides):
    arguments = {
        "company_id": "example",
        "embedding_identity": index.embedding_identity,
        **overrides,
    }
    return index.search([[10, 0]] if query is None else query, **arguments)


def test_cosine_ranking_deduplicates_without_losing_next_conversation(inputs):
    index = build(inputs)
    matches = search(index)

    assert index.size == 4
    assert index.company_id == "example"
    assert [item["evidence"]["evidence_id"] for item in matches] == ["a", "c"]
    np.testing.assert_allclose([item["similarity"] for item in matches], [1.0, 0.6])


def test_exact_threshold_includes_match_and_allows_fewer_than_top_k(inputs):
    inputs[0]["retrieval"].update(top_k=10, min_similarity=1.0)
    matches = search(build(inputs))
    assert [item["evidence"]["evidence_id"] for item in matches] == ["a"]


def test_no_match_is_empty_without_relaxing_threshold(inputs):
    assert search(build(inputs), [[-1, 0]]) == []


def test_equal_scores_use_evidence_ids_instead_of_insertion_order(inputs):
    config, _, _, identity = inputs
    records = [record("z", "one"), record("a", "two")]
    index = create_search_index(
        config, records, [[1, 0], [1, 0]], embedding_identity=identity
    )
    assert [item["evidence"]["evidence_id"] for item in search(index)] == ["a", "z"]


def test_intent_filter_runs_before_conversation_deduplication(inputs):
    inputs[0]["retrieval"]["filter_by_intent"] = True
    inputs[1][0]["intent"] = "category_a"
    inputs[1][1]["intent"] = inputs[1][2]["intent"] = "category_b"
    index = build(inputs)

    matches = search(index, intent="category_b")
    assert [item["evidence"]["evidence_id"] for item in matches] == ["b", "c"]
    assert search(index, intent=None) == []
    assert search(index, intent="unknown") == []


def test_unlabelled_evidence_does_not_match_an_intent_filter(inputs):
    inputs[0]["retrieval"]["filter_by_intent"] = True
    assert search(build(inputs), intent="category_a") == []


def test_another_company_cannot_search(inputs):
    with pytest.raises(ValueError, match="company"):
        search(build(inputs), company_id="another_company")


@pytest.mark.parametrize("key", ["name", "revision", "dimension"])
def test_different_query_encoder_is_rejected(inputs, key):
    index = build(inputs)
    identity = index.embedding_identity
    identity[key] = "different"

    with pytest.raises(ValueError, match="model identity"):
        search(index, embedding_identity=identity)


def test_input_and_result_mutations_do_not_change_index(inputs):
    config, records, vectors, identity = inputs
    original_vectors = vectors.copy()
    index = build(inputs)
    np.testing.assert_array_equal(vectors, original_vectors)
    query = np.array([[20.0, 0.0]])
    matches = search(index, query)
    np.testing.assert_array_equal(query, [[20.0, 0.0]])

    records[0]["company_id"] = "changed"
    vectors[:] = 0
    identity["name"] = "changed"
    config["retrieval"]["top_k"] = 1
    matches[0]["evidence"]["reply_text"] = "changed"
    returned_identity = index.embedding_identity
    returned_identity["name"] = "changed"

    fresh = search(index)
    assert len(fresh) == 2
    assert fresh[0]["evidence"]["company_id"] == "example"
    assert fresh[0]["evidence"]["reply_text"] != "changed"


@pytest.mark.parametrize(
    "key,value",
    [
        ("company_id", "another"),
        ("split", "evaluation"),
        ("resolution_verified", True),
        ("reply_text", ""),
        ("intent", 4),
    ],
)
def test_invalid_evidence_is_rejected(inputs, key, value):
    inputs[1][0][key] = value

    with pytest.raises(ValueError):
        build(inputs)


def test_duplicate_evidence_ids_are_rejected(inputs):
    inputs[1][1] = deepcopy(inputs[1][0])

    with pytest.raises(ValueError, match="unique"):
        build(inputs)


@pytest.mark.parametrize(
    "query",
    [
        [[0, 0]],
        [[np.nan, 1]],
        [[np.inf, 1]],
        [[1, 2, 3]],
        [1, 0],
        [[True, False]],
        [["1", "0"]],
    ],
)
def test_invalid_query_vectors_fail(inputs, query):
    with pytest.raises(ValueError):
        search(build(inputs), query)


@pytest.mark.parametrize("problem", ["count", "dimension", "zero", "nonfinite"])
def test_invalid_index_vectors_fail(inputs, problem):
    config, records, vectors, identity = inputs

    if problem == "count":
        vectors = vectors[:-1]
    elif problem == "dimension":
        vectors = vectors[:, :1]
    elif problem == "zero":
        vectors[0] = 0
    else:
        vectors[0, 0] = np.inf

    with pytest.raises(ValueError):
        create_search_index(config, records, vectors, embedding_identity=identity)


@pytest.mark.parametrize(
    "key,value",
    [
        ("provider", "unknown"),
        ("similarity", "dot"),
        ("top_k", 0),
        ("top_k", True),
        ("min_similarity", np.nan),
        ("min_similarity", 1.1),
        ("filter_by_intent", "false"),
    ],
)
def test_invalid_search_settings_fail(inputs, key, value):
    inputs[0]["retrieval"][key] = value

    with pytest.raises(ConfigError):
        build(inputs)


def test_empty_index_returns_no_matches(inputs):
    config, _, _, identity = inputs
    index = create_search_index(
        config, [], np.empty((0, 2)), embedding_identity=identity
    )
    assert index.size == 0
    assert search(index) == []
