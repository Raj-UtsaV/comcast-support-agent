"""Offline saved-index checks with real preparation/FAISS and a test encoder."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_pipeline import setup_project

from support_agent.data.preparation import prepare_data
from support_agent.retrieval import index_store
from support_agent.retrieval.index_state import file_hash, json_bytes, storage_directory
from support_agent.retrieval.index_store import build_saved_index, load_saved_index


@pytest.fixture
def saved_inputs(tmp_path):
    config = setup_project(tmp_path)
    prepare_data(config)
    config["models"]["embedding"].update(
        provider="synthetic_test", name="example/fixture", revision="fixture-v1"
    )

    class FakeEncoder:
        dimension = 2

        def __init__(self):
            self.calls = 0
            self.identity = {**config["models"]["embedding"], "dimension": 2}

        def encode(self, texts):
            self.calls += 1
            return np.tile([0.6, 0.8], (len(texts), 1))

    return config, FakeEncoder()


def current_folder(config):
    root = storage_directory(config)
    return root / json.loads((root / "current.json").read_bytes())["generation"]


def refresh_manifest(config, manifest):
    folder = current_folder(config)
    (folder / "manifest.json").write_bytes(json_bytes(manifest))
    pointer = {
        "generation": folder.name,
        "manifest_sha256": file_hash(folder / "manifest.json"),
    }
    (folder.parent / "current.json").write_bytes(json_bytes(pointer))


def test_round_trip_preserves_results_without_loading_or_calling_encoder(saved_inputs, monkeypatch):
    config, encoder = saved_inputs
    original = build_saved_index(config, embedder=encoder)

    def unexpected(*args, **kwargs):
        raise AssertionError("Reloading must not load an encoder")

    monkeypatch.setattr(index_store, "create_embedder", unexpected)
    loaded = load_saved_index(config)
    arguments = {
        "company_id": config["company"]["id"],
        "embedding_identity": encoder.identity,
    }
    assert loaded.search([[0.6, 0.8]], **arguments) == original.search(
        [[0.6, 0.8]], **arguments
    )
    assert loaded.size == original.size
    assert encoder.calls == 1


def test_existing_index_requires_explicit_rebuild_and_retains_old_version(saved_inputs):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    first = current_folder(config)

    with pytest.raises(FileExistsError, match="rebuild=True"):
        build_saved_index(config, embedder=encoder)

    assert encoder.calls == 1
    build_saved_index(config, rebuild=True, embedder=encoder)
    assert first.exists() and current_folder(config) != first
    assert not (first.parent / ".build-lock").exists()


@pytest.mark.parametrize(
    "filename",
    [
        "train.jsonl",
        "validation.jsonl",
        "evaluation.jsonl",
        "golden.jsonl",
        "quarantine.jsonl",
        "manifest.json",
    ],
)
def test_changed_prepared_files_make_index_stale(saved_inputs, filename):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    path = Path(config["paths"]["processed_dir"]) / filename
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="stale"):
        load_saved_index(config)


def test_new_golden_labels_require_rebuild_and_remove_reserved_conversation(saved_inputs):
    config, encoder = saved_inputs
    original = build_saved_index(config, embedder=encoder)
    Path(config["paths"]["golden_labels"]).write_text(
        "company_id,conversation_id,message_id\nexample,customer01,customer01\n"
    )

    with pytest.raises(ValueError, match="stale"):
        load_saved_index(config)

    rebuilt = build_saved_index(config, rebuild=True, embedder=encoder)
    assert rebuilt.size == original.size - 1
    assert "customer01" not in (current_folder(config) / "evidence.jsonl").read_text()


@pytest.mark.parametrize("change", ["model", "masking", "source_code", "dependencies"])
def test_changed_configuration_or_implementation_is_stale(saved_inputs, monkeypatch, change):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)

    if change == "model":
        config["models"]["embedding"]["revision"] = "different"
    elif change == "masking":
        config["dataset"]["pii"]["mask_types"] = []
    else:
        real_state = index_store.source_state

        def changed(settings):
            state = real_state(settings)
            state["implementation" if change == "source_code" else "dependencies"] = {}
            return state

        monkeypatch.setattr(index_store, "source_state", changed)

    with pytest.raises(ValueError, match="stale"):
        load_saved_index(config)


def test_runtime_search_settings_apply_without_reencoding(saved_inputs):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    config["retrieval"]["top_k"] = 1
    loaded = load_saved_index(config)
    matches = loaded.search(
        [[0.6, 0.8]], company_id="example", embedding_identity=encoder.identity
    )
    assert len(matches) == 1 and encoder.calls == 1


@pytest.mark.parametrize("filename", ["evidence.jsonl", "vectors.npy", "manifest.json"])
def test_corrupt_files_fail_checksum_before_loading(saved_inputs, filename):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    path = current_folder(config) / filename
    path.write_bytes(path.read_bytes() + b"corrupt")

    with pytest.raises(ValueError, match="checksum"):
        load_saved_index(config)


@pytest.mark.parametrize(
    "change", ["count", "vector_shape", "company", "schema", "pickle"]
)
def test_structural_validation_still_runs_after_checksums_match(saved_inputs, change):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    folder = current_folder(config)
    manifest = json.loads((folder / "manifest.json").read_bytes())

    if change == "count":
        manifest["record_count"] += 1
    elif change == "company":
        manifest["company_id"] = "another_company"
    elif change == "schema":
        manifest["schema_version"] = 99
    else:
        vector = (
            np.ones((manifest["record_count"], 3))
            if change == "vector_shape"
            else np.array([{}], dtype=object)
        )
        np.save(folder / "vectors.npy", vector)
        manifest["files"]["vectors.npy"] = file_hash(folder / "vectors.npy")

    refresh_manifest(config, manifest)

    with pytest.raises(ValueError):
        load_saved_index(config)


def test_failed_write_preserves_current_and_cleans_incomplete_version(saved_inputs, monkeypatch):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    folder = current_folder(config)

    def fail(*args, **kwargs):
        raise OSError("Synthetic disk-write failure")

    monkeypatch.setattr(index_store.np, "save", fail)

    with pytest.raises(OSError, match="disk-write"):
        build_saved_index(config, rebuild=True, embedder=encoder)

    assert current_folder(config) == folder
    assert list(folder.parent.glob("index-*")) == [folder]
    assert load_saved_index(config).size > 0


def test_generation_path_cannot_escape_company_directory(saved_inputs):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    (storage_directory(config) / "current.json").write_text(
        '{"generation": "../outside"}'
    )

    with pytest.raises(ValueError, match="generation"):
        load_saved_index(config)


def test_saved_index_can_move_with_identical_data(saved_inputs, tmp_path):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    moved = deepcopy(config)
    copied = tmp_path / "moved"
    shutil.copytree(storage_directory(config), copied / "example/search")
    moved["paths"]["artifacts_dir"] = str(copied)
    assert load_saved_index(moved).size > 0


def test_existing_build_lock_is_not_removed_by_second_builder(saved_inputs):
    config, encoder = saved_inputs
    lock = storage_directory(config) / ".build-lock"
    lock.mkdir(parents=True)

    with pytest.raises(FileExistsError, match="build"):
        build_saved_index(config, embedder=encoder)

    assert lock.exists() and encoder.calls == 0


def test_inputs_changing_during_build_are_not_published(saved_inputs, monkeypatch):
    config, encoder = saved_inputs
    build_saved_index(config, embedder=encoder)
    folder = current_folder(config)
    original_encode = encoder.encode

    def change_source(texts):
        path = Path(config["paths"]["processed_dir"]) / "train.jsonl"
        path.write_bytes(path.read_bytes() + b"\n")
        return original_encode(texts)

    monkeypatch.setattr(encoder, "encode", change_source)

    with pytest.raises(ValueError, match="changed during"):
        build_saved_index(config, rebuild=True, embedder=encoder)

    assert current_folder(config) == folder
    assert list(folder.parent.glob("index-*")) == [folder]
    assert not (folder.parent / ".build-lock").exists()
