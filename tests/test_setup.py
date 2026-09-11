"""Exercise setup with real data preparation and FAISS, using a tiny encoder."""

from pathlib import Path

import numpy as np
import pytest
from test_pipeline import setup_project

from support_agent import setup
from support_agent.shared.config import ConfigError, load_config


def test_setup_builds_reuses_and_rebuilds_without_overwriting_reviews(tmp_path, monkeypatch):
    config = setup_project(tmp_path)

    class Encoder:
        identity = {**config["models"]["embedding"], "dimension": 2}

        def encode(self, texts):
            return np.tile([0.6, 0.8], (len(texts), 1))

    calls = []

    def model(config, *, local_files_only):
        calls.append(local_files_only)
        return Encoder()

    monkeypatch.setattr(setup, "create_embedder", model)
    first = setup.setup_pipeline(config)
    assert first["processed_data"] == "created"
    assert first["index"] == "built" and first["indexed_pairs"] > 0
    review = Path(config["paths"]["processed_dir"]) / "intent_review.csv"
    review.write_text(review.read_text() + "human review preserved\n")
    preserved = review.read_bytes()
    second = setup.setup_pipeline(config)
    assert second["processed_data"] == "reused" and second["index"] == "reused"
    assert calls == [False]
    third = setup.setup_pipeline(config, rebuild=True)
    assert third["index"] == "built"
    assert calls == [False, False]
    assert review.read_bytes() == preserved


def test_setup_missing_source_fails_before_model_loading(tmp_path, monkeypatch):
    config = setup_project(tmp_path)
    Path(config["paths"]["raw_csv"]).unlink()

    def unexpected(*args, **kwargs):
        pytest.fail("Must not download a model without source data")

    monkeypatch.setattr(setup, "create_embedder", unexpected)
    with pytest.raises(FileNotFoundError, match="Source dataset missing"):
        setup.setup_pipeline(config)


def test_setup_rejects_scripted_demo():
    with pytest.raises(ConfigError, match="Demo mode"):
        setup.setup_pipeline(load_config("configs/demo.yaml"))
