"""Offline contract checks using an explicitly synthetic model implementation."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from support_agent.embeddings.encoder import create_embedder
from support_agent.shared.config import PROJECT_ROOT, ConfigError


@pytest.fixture
def provider(monkeypatch, tmp_path):
    config = yaml.safe_load((PROJECT_ROOT / "configs/base.yaml").read_text())
    config["paths"]["model_cache"] = str(tmp_path / "models")
    instances = []

    class FakeModel:
        max_seq_length = 16

        def __init__(self, name, **kwargs):
            self.name = name
            self.options = kwargs
            self.output = np.array([[3.0, 4.0, 0.0]])
            self.calls = []
            instances.append(self)

        def get_embedding_dimension(self):
            return 3

        def encode(self, texts, **kwargs):
            self.calls.append((texts, kwargs))
            return self.output

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel),
    )

    return config, instances


def test_local_loading_and_normalized_float32_output(provider):
    config, instances = provider
    encoder = create_embedder(config)
    model = instances[0]
    model.output = np.array([[3, 4, 0], [0, 0, 2]], dtype=np.float64)
    vectors = encoder.encode(["first message", "second message"])

    assert vectors.dtype == np.float32
    assert vectors.flags.c_contiguous
    np.testing.assert_allclose(vectors, [[0.6, 0.8, 0], [0, 0, 1]])
    assert model.calls[0][0] == ["first message", "second message"]
    assert model.options["local_files_only"] is True
    assert model.options["trust_remote_code"] is False
    assert model.options["token"] is False
    assert model.options["revision"] == config["models"]["embedding"]["revision"]
    assert model.options["cache_folder"] == config["paths"]["model_cache"]
    assert (
        model.calls[0][1]["batch_size"] == config["models"]["embedding"]["batch_size"]
    )


def test_download_mode_and_alternate_model_come_from_settings(provider):
    config, instances = provider
    config["models"]["embedding"].update(
        name="example/synthetic-model", revision="a" * 40, batch_size=2, device="cuda:1"
    )
    encoder = create_embedder(config, local_files_only=False)
    encoder.encode(["test message"])

    assert instances[0].name == "example/synthetic-model"
    assert instances[0].options["local_files_only"] is False
    assert instances[0].options["device"] == "cuda:1"
    assert instances[0].calls[0][1]["batch_size"] == 2


def test_identity_and_settings_cannot_be_changed_through_caller_mutation(provider):
    config, _ = provider
    encoder = create_embedder(config)
    identity = encoder.identity
    identity["dimension"] = 100
    config["models"]["embedding"]["normalize_embeddings"] = False

    assert encoder.dimension == 3
    assert encoder.identity["max_sequence_length"] == 16
    assert encoder.identity["normalize_embeddings"] is True
    np.testing.assert_allclose(encoder.encode(["test message"]), [[0.6, 0.8, 0]])


def test_normalization_can_be_disabled(provider):
    config, _ = provider
    config["models"]["embedding"]["normalize_embeddings"] = False
    encoder = create_embedder(config)
    np.testing.assert_array_equal(encoder.encode(["test message"]), [[3, 4, 0]])


def test_empty_input_has_known_dimension_without_encoding(provider):
    config, instances = provider
    encoder = create_embedder(config)
    assert encoder.encode([]).shape == (0, 3)
    assert instances[0].calls == []


@pytest.mark.parametrize("texts", ["single string", b"bytes", None, [""], ["  "], [7]])
def test_invalid_inputs_fail_before_model_encoding(provider, texts):
    config, instances = provider
    encoder = create_embedder(config)

    with pytest.raises((TypeError, ValueError)):
        encoder.encode(texts)

    assert instances[0].calls == []


@pytest.mark.parametrize(
    "output", [[[0, 0, 0]], [[np.nan, 1, 2]], [[np.inf, 1, 2]], [[1, 2]], [1, 2, 3]]
)
def test_invalid_model_vectors_are_rejected(provider, output):
    config, instances = provider
    encoder = create_embedder(config)
    instances[0].output = np.array(output)

    with pytest.raises(ValueError, match="vector"):
        encoder.encode(["test message"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("provider", "unknown"),
        ("name", "short-name"),
        ("revision", "main"),
        ("revision", None),
        ("batch_size", 0),
        ("batch_size", True),
        ("normalize_embeddings", "false"),
        ("device", "unsupported"),
    ],
)
def test_bad_settings_fail_before_model_loading(provider, key, value):
    config, instances = provider
    config["models"]["embedding"][key] = value

    with pytest.raises(ConfigError):
        create_embedder(config)

    assert instances == []


def test_missing_model_does_not_fall_back_to_fake_vectors(provider, monkeypatch):
    config, _ = provider

    def unavailable(*args, **kwargs):
        raise OSError("Synthetic missing-cache failure")

    monkeypatch.setattr(
        sys.modules["sentence_transformers"], "SentenceTransformer", unavailable
    )

    with pytest.raises(RuntimeError, match="local cache"):
        create_embedder(config)
