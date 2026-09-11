"""Exercise the retrieval API and CLI with real saved synthetic evidence."""

import io
import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_index_store import (
    saved_inputs as saved_inputs,  # noqa: PLC0414 -- Re-export the pytest fixture.
)

from support_agent.retrieval import index_store
from support_agent.retrieval import service as retrieval
from support_agent.retrieval.index_store import build_saved_index
from support_agent.shared.config import ConfigError


@pytest.fixture
def ready(saved_inputs, monkeypatch):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    monkeypatch.setattr(retrieval, "load_config", lambda path: config)
    monkeypatch.setattr(retrieval, "create_embedder", lambda settings: encoder)

    return config, encoder


def test_message_is_masked_before_encoding_and_output(ready, monkeypatch):
    config, encoder = ready
    inputs = []
    original = encoder.encode

    def capture(texts):
        inputs.extend(texts)
        return original(texts)

    monkeypatch.setattr(encoder, "encode", capture)
    result = retrieval.retrieve(
        config, "Email alex@example.test about my connection.", embedder=encoder
    )
    assert inputs == [result["query"]["text"]]
    assert "[EMAIL]" in inputs[0]
    assert "alex@example.test" not in json.dumps(result)
    assert result["query"]["sensitive_information"] == ["email"]
    assert result["status"] == "matches_found"


@pytest.mark.parametrize("message", ["", "   ", "&nbsp;", None, 3])
def test_invalid_messages_fail_before_loading_index(ready, monkeypatch, message):
    config, _ = ready

    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid inputs must not load the index")

    monkeypatch.setattr(retrieval, "load_saved_index", unexpected)

    with pytest.raises(ValueError):
        retrieval.retrieve(config, message)


def test_message_longer_than_configured_limit_is_rejected(ready):
    config, _ = ready
    message = "x" * (config["runtime"]["max_message_characters"] + 1)

    with pytest.raises(ValueError, match="exceeds"):
        retrieval.retrieve(config, message)


@pytest.mark.parametrize("categories", [None, ["bad entry"], [{"id": ""}]])
def test_malformed_category_settings_are_reported_clearly(ready, categories):
    config, _ = ready
    config["intents"]["approved_taxonomy"] = categories

    with pytest.raises(ConfigError):
        retrieval.retrieve(config, "question", intent="connection")


def test_normalization_expansion_obeys_configured_limit(ready):
    config, _ = ready
    config["runtime"]["max_message_characters"] = 1

    with pytest.raises(ValueError, match="cleaned"):
        retrieval.retrieve(
            config, "\ufb03"
        )  # NFKC expands this ligature to three letters.


@pytest.mark.parametrize("limit", [0, True, "10"])
def test_invalid_runtime_limit_is_configuration_error(ready, limit):
    config, _ = ready
    config["runtime"]["max_message_characters"] = limit

    with pytest.raises(ConfigError):
        retrieval.retrieve(config, "question")


def test_unapproved_intent_is_rejected_and_missing_filtered_intent_skips_encoder(ready):
    config, encoder = ready

    with pytest.raises(ValueError, match="approved"):
        retrieval.retrieve(config, "question", intent="invented", embedder=encoder)

    config["retrieval"]["filter_by_intent"] = True
    result = retrieval.retrieve(config, "question", embedder=encoder)
    assert result["status"] == "missing_intent" and result["matches"] == []
    assert encoder.calls == 1  # Only the fixture's historical build.


def test_approved_intent_with_no_labelled_evidence_returns_no_matches(ready):
    config, encoder = ready
    config["intents"]["approved_taxonomy"] = [
        {"id": "connection", "description": "Synthetic category"}
    ]
    config["retrieval"]["filter_by_intent"] = True
    result = retrieval.retrieve(
        config, "question", intent="connection", embedder=encoder
    )
    assert result["status"] == "no_matches" and result["matches"] == []


def test_wrong_encoder_is_rejected_before_query_encoding(ready):
    config, encoder = ready
    encoder.identity = deepcopy(encoder.identity)
    encoder.identity["revision"] = "different"

    with pytest.raises(ValueError, match="identity"):
        retrieval.retrieve(config, "question", embedder=encoder)

    assert encoder.calls == 1


def test_stale_index_fails_before_loading_query_encoder(ready, monkeypatch):
    config, _ = ready
    Path(config["paths"]["golden_labels"]).write_text("company_id,conversation_id\n")

    def unexpected(*args, **kwargs):
        raise AssertionError("Stale evidence must be rejected before model loading")

    monkeypatch.setattr(retrieval, "create_embedder", unexpected)

    with pytest.raises(ValueError, match="stale"):
        retrieval.retrieve(config, "question")


def test_inspect_outputs_json_without_encoding(ready, capsys):
    _, encoder = ready
    assert retrieval.main(["inspect", "--config", "example.yaml"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ready" and result["indexed_pairs"] > 0
    assert encoder.calls == 1


def test_search_from_stdin_keeps_progress_out_of_json(ready, monkeypatch, capsys):
    _, encoder = ready
    original = encoder.encode

    def noisy(texts):
        print("Synthetic model progress")
        return original(texts)

    monkeypatch.setattr(encoder, "encode", noisy)
    monkeypatch.setattr(retrieval.sys, "stdin", io.StringIO("My connection is broken."))
    assert retrieval.main(["search", "--config", "example.yaml", "--stdin"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "matches_found"
    assert "Synthetic model progress" in output.err


def test_stdin_read_is_bounded_and_errors_do_not_echo_message(ready, monkeypatch, capsys):
    config, _ = ready
    config["runtime"]["max_message_characters"] = 4
    stream = io.StringIO("private message much longer than allowed")
    monkeypatch.setattr(retrieval.sys, "stdin", stream)
    assert retrieval.main(["search", "--config", "example.yaml", "--stdin"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and "private message" not in output.err
    assert stream.tell() == 5


def test_cli_build_requires_rebuild_for_existing_index(ready, monkeypatch, capsys):
    _, encoder = ready
    monkeypatch.setattr(index_store, "create_embedder", lambda settings: encoder)
    assert retrieval.main(["build", "--config", "example.yaml"]) == 1
    assert "rebuild" in capsys.readouterr().err
    assert retrieval.main(["build", "--config", "example.yaml", "--rebuild"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "built"


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["search", "--config", "example.yaml"],
        ["search", "--config", "example.yaml", "--message", "question", "--stdin"],
    ],
)
def test_invalid_command_syntax_has_standard_exit_code(arguments):
    with pytest.raises(SystemExit) as error:
        retrieval.main(arguments)

    assert error.value.code == 2
