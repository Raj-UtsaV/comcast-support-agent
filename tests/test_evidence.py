"""Synthetic checks for company isolation, held-out data and reply linking."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from support_agent.data.evidence import collect_evidence
from support_agent.shared.config import PROJECT_ROOT


def message(message_id, role, parent=None, *, conversation="conversation1"):
    return {
        "company_id": "example",
        "conversation_id": conversation,
        "message_id": message_id,
        "parent_message_id": parent,
        "timestamp": "2020-01-01T00:00:00+00:00",
        "role": role,
        "text": (
            "My connection stopped working. Email alex@example.test."
            if role == "customer"
            else "Check that your cable is securely connected."
        ),
        "metadata": {"useful_reply": role == "agent"},
    }


@pytest.fixture
def prepared(tmp_path):
    config = yaml.safe_load((PROJECT_ROOT / "configs/base.yaml").read_text())
    config["company"]["id"] = "example"
    config["paths"]["processed_dir"] = str(tmp_path / "processed")
    config["paths"]["golden_labels"] = str(tmp_path / "golden.csv")
    rows = {
        "train": [
            message("question", "customer"),
            message("reply", "agent", "question"),
        ],
        "validation": [],
        "evaluation": [],
        "golden": [],
        "quarantine": [],
    }

    def write():
        directory = Path(config["paths"]["processed_dir"])
        directory.mkdir(exist_ok=True)

        for split, messages in rows.items():
            (directory / f"{split}.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in messages)
            )

        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "company_id": "example",
                    "time_boundaries": {
                        "validation_start": "2020-02-01T00:00:00+00:00"
                    },
                    "messages_by_split": {
                        key: len(value) for key, value in rows.items()
                    },
                }
            )
        )

    return config, rows, write


def test_pair_is_traceable_masked_and_does_not_claim_resolution(prepared):
    config, rows, write = prepared
    original = deepcopy(rows)
    write()
    pairs, counts = collect_evidence(config)

    assert len(pairs) == counts["selected_pairs"] == 1
    assert pairs[0]["evidence_id"] == "example:reply"
    assert pairs[0]["customer_message_id"] == "question"
    assert pairs[0]["split"] == "train"
    assert "[EMAIL]" in pairs[0]["customer_text"]
    assert "alex@example.test" not in pairs[0]["customer_text"]
    assert pairs[0]["intent"] is None
    assert pairs[0]["resolution_verified"] is False
    assert rows == original


@pytest.mark.parametrize("split", ["validation", "evaluation", "golden", "quarantine"])
def test_held_out_pairs_are_never_selected(prepared, split):
    config, rows, write = prepared
    rows[split] = [
        message("held_question", "customer", conversation="held"),
        message("held_reply", "agent", "held_question", conversation="held"),
    ]
    write()
    pairs, _ = collect_evidence(config)
    assert [pair["reply_message_id"] for pair in pairs] == ["reply"]


def test_annotations_added_after_preparation_exclude_entire_conversation(prepared):
    config, _, write = prepared
    write()
    Path(config["paths"]["golden_labels"]).write_text(
        "company_id,conversation_id,message_id\nexample,conversation1,question\n"
    )
    pairs, counts = collect_evidence(config)
    assert pairs == []
    assert counts["excluded_golden_replies"] == 1


@pytest.mark.parametrize(
    "conversation,source_id", [("unknown", "question"), ("conversation1", "unknown")]
)
def test_unknown_annotation_ids_fail(prepared, conversation, source_id):
    config, _, write = prepared
    write()
    Path(config["paths"]["golden_labels"]).write_text(
        f"company_id,conversation_id,message_id\nexample,{conversation},{source_id}\n"
    )

    with pytest.raises(ValueError, match="golden"):
        collect_evidence(config)


@pytest.mark.parametrize(
    "problem", ["company", "duplicate", "conversation", "time", "count"]
)
def test_invalid_prepared_data_is_rejected(prepared, problem):
    config, rows, write = prepared

    if problem == "company":
        rows["train"][1]["company_id"] = "another_company"
    elif problem == "duplicate":
        rows["evaluation"].append(deepcopy(rows["train"][1]))
    elif problem == "conversation":
        rows["evaluation"].append(message("held", "customer"))
    elif problem == "time":
        rows["train"][1]["timestamp"] = "2020-02-01T00:00:00+00:00"

    write()

    if problem == "count":
        (Path(config["paths"]["processed_dir"]) / "train.jsonl").write_text("")

    with pytest.raises(ValueError):
        collect_evidence(config)


@pytest.mark.parametrize(
    "problem", ["missing", "cross_conversation", "future", "cycle", "no_parent"]
)
def test_unusable_parent_links_are_skipped_without_guessing(prepared, problem):
    config, rows, write = prepared
    customer, reply = rows["train"]

    if problem == "missing":
        reply["parent_message_id"] = "absent"
    elif problem == "cross_conversation":
        customer["conversation_id"] = "different"
    elif problem == "future":
        customer["timestamp"] = "2020-01-02T00:00:00+00:00"
    elif problem == "cycle":
        reply["parent_message_id"] = "reply"
    else:
        reply["parent_message_id"] = None

    write()
    pairs, counts = collect_evidence(config)
    assert pairs == []
    assert counts["missing_customer_context"] == 1


def test_agent_follow_up_uses_linked_customer_instead_of_nearest_row(prepared):
    config, rows, write = prepared
    rows["train"].extend(
        [
            message("unrelated_question", "customer"),
            message("follow_up", "agent", "reply"),
        ]
    )
    write()
    pairs, _ = collect_evidence(config)
    assert [pair["customer_message_id"] for pair in pairs] == ["question", "question"]


def test_customer_text_that_becomes_empty_is_not_evidence(prepared):
    config, rows, write = prepared
    rows["train"][0]["text"] = "&nbsp;"
    write()
    pairs, counts = collect_evidence(config)
    assert pairs == []
    assert counts["missing_customer_context"] == 1


@pytest.mark.parametrize(
    "problem", ["previous_filter", "current_filter", "greeting", "dm_only"]
)
def test_quality_filter_is_enforced_before_indexing(prepared, problem):
    config, rows, write = prepared

    if problem == "previous_filter":
        rows["train"][1]["metadata"]["useful_reply"] = False
    elif problem == "current_filter":
        config["dataset"]["reply_quality"]["min_words"] = 100
    elif problem == "greeting":
        rows["train"][1]["text"] = "Hello!"
    else:
        rows["train"][1]["text"] = "Please send us a DM so we can help."

    write()
    pairs, counts = collect_evidence(config)
    assert pairs == []
    assert counts["rejected_reply_quality"] == 1
