"""Offline regression tests; every conversation in this file is synthetic."""

import csv
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from support_agent.data.preparation import MESSAGE_FIELDS, prepare_data
from support_agent.data.splits import split_conversations
from support_agent.shared.config import PROJECT_ROOT, ConfigError, load_config
from support_agent.shared.text import normalize_text, useful_reply


def synthetic_rows():
    rows = []

    for day in range(1, 13):
        stamp = datetime(2020, 1, day, tzinfo=timezone.utc)
        customer, reply = f"customer{day:02}", f"reply{day:02}"
        rows.extend(
            [
                {
                    "tweet_id": customer,
                    "author_id": f"user{day}",
                    "inbound": "True",
                    "created_at": stamp.strftime("%a %b %d %H:%M:%S %z %Y"),
                    "text": "Synthetic question about a disconnected cable.",
                    "response_tweet_id": reply,
                    "in_response_to_tweet_id": "",
                },
                {
                    "tweet_id": reply,
                    "author_id": "example_support",
                    "inbound": "False",
                    "created_at": (stamp + timedelta(minutes=5)).strftime(
                        "%a %b %d %H:%M:%S %z %Y"
                    ),
                    "text": "Check that the cable is securely connected.",
                    "response_tweet_id": "",
                    "in_response_to_tweet_id": customer,
                },
            ]
        )

    return rows


def setup_project(tmp_path, rows=None, *, rename_columns=False):
    (tmp_path / "configs").mkdir()
    (tmp_path / "data/raw").mkdir(parents=True)
    base = yaml.safe_load((PROJECT_ROOT / "configs/base.yaml").read_text())
    (tmp_path / "configs/base.yaml").write_text(yaml.safe_dump(base))
    company = yaml.safe_load((PROJECT_ROOT / "configs/comcast.yaml").read_text())
    # Synthetic fixtures must not inherit a user's reviewed company categories.
    company["intents"] = {"approved_taxonomy": [], "keyword_rules": {}}
    company.setdefault("safety", {})["risky_intents"] = []
    company["company"] = {
        "id": "example",
        "display_name": "Example Company",
        "instructions": "Synthetic test support instructions.",
    }
    company["dataset"]["company_author_ids"] = ["example_support"]
    company["dataset"]["source"] = {"provider": "synthetic_test_fixture"}
    company["dataset"]["csv"] = {"chunk_size": 1}
    company["paths"]["processed_dir"] = "data/processed/example"
    company["paths"]["results_dir"] = "results/example"
    rows = deepcopy(rows if rows is not None else synthetic_rows())

    if rename_columns:
        names = {name: "source_" + name for name in rows[0]}
        rows = [{names[key]: value for key, value in row.items()} for row in rows]
        company["dataset"]["columns"] = {
            key: names[value] for key, value in company["dataset"]["columns"].items()
        }

    with (tmp_path / "data/raw/twcs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    path = tmp_path / "configs/company.yaml"
    path.write_text(yaml.safe_dump(company))

    return load_config(path, project_root=tmp_path)


def output_records(config):
    result = {}

    for path in Path(config["paths"]["processed_dir"]).glob("*.jsonl"):
        result[path.stem] = [json.loads(line) for line in path.read_text().splitlines()]

    return result


def test_configuration_merges_and_preserves_environment(tmp_path, monkeypatch):
    setup_project(tmp_path)
    (tmp_path / ".env").write_text("LLM_MODEL=file_value\nLLM_PROVIDER=file_provider\n")
    monkeypatch.setenv("LLM_MODEL", "process_value")
    monkeypatch.delenv("LLM_PROVIDER")
    config = load_config("configs/company.yaml", project_root=tmp_path)
    assert config["models"]["generator"]["name"] == "process_value"
    assert config["models"]["generator"]["provider"] == "file_provider"
    assert config["dataset"]["csv"] == {"chunk_size": 1, "encoding": "utf-8"}
    assert config["company"]["id"] == "example"
    assert config["dataset"]["company_author_ids"] == ["example_support"]


@pytest.mark.parametrize(
    "override",
    [
        "company:\n  id: ../escape\n",
        "company:\n  id: first\ncompany:\n  id: second\n",
        "splits:\n  train_fraction: 0.99\n",
        "paths:\n  processed_dir: ../outside\n",
    ],
)
def test_invalid_configuration_is_rejected(tmp_path, override):
    setup_project(tmp_path)
    (tmp_path / "configs/company.yaml").write_text(override)

    with pytest.raises(ConfigError):
        load_config("configs/company.yaml", project_root=tmp_path)


def test_column_mapping_and_complete_conversations_across_chunks(tmp_path):
    config = setup_project(tmp_path, rename_columns=True)
    manifest = prepare_data(config)
    assert manifest["counts"]["conversations"] == 12
    assert manifest["counts"]["normalized_messages"] == 24
    records = output_records(config)
    assignments = {}

    for split, messages in records.items():
        for message in messages:
            assert set(message) == set(MESSAGE_FIELDS)
            assert message["company_id"] == "example"
            assert assignments.setdefault(message["conversation_id"], split) == split

    assert max(row["timestamp"] for row in records["train"]) < min(
        row["timestamp"] for row in records["validation"]
    )
    assert max(row["timestamp"] for row in records["validation"]) < min(
        row["timestamp"] for row in records["evaluation"]
    )
    assert records["golden"] == []

    with (
        Path(config["paths"]["processed_dir"]) / "intent_review.csv"
    ).open() as stream:
        review = list(csv.DictReader(stream))

    assert review and all(
        assignments[row["conversation_id"]] == "train" for row in review
    )


def test_other_company_does_not_become_evidence_or_bridge(tmp_path):
    rows = synthetic_rows()
    other = {
        **rows[1],
        "tweet_id": "other_reply",
        "author_id": "other_support",
        "response_tweet_id": "other_customer",
    }
    customer = {
        **rows[0],
        "tweet_id": "other_customer",
        "in_response_to_tweet_id": "other_reply",
        "response_tweet_id": "",
    }
    config = setup_project(tmp_path, rows + [other, customer])
    prepare_data(config)
    ids = {
        row["message_id"]
        for messages in output_records(config).values()
        for row in messages
    }
    assert ids == {row["tweet_id"] for row in rows}


def test_duplicates_are_removed_but_repeated_text_with_new_ids_is_kept(tmp_path):
    rows = synthetic_rows()
    config = setup_project(tmp_path, rows + [deepcopy(rows[0])])
    manifest = prepare_data(config)
    assert manifest["counts"]["duplicate_records_removed"] == 1
    assert manifest["counts"]["normalized_messages"] == 24


def test_conflicting_duplicate_ids_fail_without_partial_output(tmp_path):
    rows = synthetic_rows()
    config = setup_project(
        tmp_path, rows + [{**rows[0], "text": "Conflicting synthetic text."}]
    )

    with pytest.raises(ValueError, match="Conflicting"):
        prepare_data(config)

    assert not Path(config["paths"]["processed_dir"]).exists()


def test_empty_message_does_not_break_conversation_links(tmp_path):
    rows = synthetic_rows()
    rows[0]["text"] = "  \n\t "
    config = setup_project(tmp_path, rows)
    manifest = prepare_data(config)
    assert manifest["counts"]["empty_messages_removed"] == 1
    messages = [row for values in output_records(config).values() for row in values]
    reply = next(row for row in messages if row["message_id"] == "reply01")
    assert reply["conversation_id"] == "customer01"


def test_pii_masking_and_whitespace(tmp_path):
    config = setup_project(tmp_path)
    text, flags = normalize_text(
        "  Email alex@example.test\nphone +44 (20) 1234 5678; account #123456789; @test_user  ",
        config,
    )
    assert set(flags) == {"email", "phone", "account_number", "username"}

    for raw in ("alex@example.test", "1234 5678", "123456789", "@test_user"):
        assert raw not in text

    assert "\n" not in text and "  " not in text
    assert all(
        marker in text
        for marker in ("[EMAIL]", "[PHONE]", "[ACCOUNT_NUMBER]", "[USERNAME]")
    )
    assert normalize_text("Contact __email__ or __phone__", config)[1] == [
        "email",
        "phone",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Hello!",
        "Please send us a DM so we can help.",
        "[USERNAME] Please DM us for help.",
    ],
)
def test_low_quality_replies_are_marked(tmp_path, text):
    config = setup_project(tmp_path)
    assert useful_reply(text, config) is False
    assert useful_reply("Check that the cable is securely connected.", config) is True


def test_response_ids_and_missing_parent_connect_orphan_siblings(tmp_path):
    rows = synthetic_rows()
    rows[1]["in_response_to_tweet_id"] = ""  # Connected solely through response IDs.
    rows[2]["in_response_to_tweet_id"] = "absent_root"
    sibling = {**rows[2], "tweet_id": "sibling", "response_tweet_id": ""}
    config = setup_project(tmp_path, rows + [sibling])
    prepare_data(config)
    by_id = {
        row["message_id"]: row
        for values in output_records(config).values()
        for row in values
    }
    assert by_id["customer01"]["conversation_id"] == by_id["reply01"]["conversation_id"]
    assert by_id["customer02"]["conversation_id"] == by_id["sibling"]["conversation_id"]
    assert by_id["sibling"]["metadata"]["parent_missing_from_source"] is True


def test_cycles_do_not_duplicate_or_split_messages(tmp_path):
    rows = synthetic_rows()
    rows[0]["in_response_to_tweet_id"] = rows[1]["tweet_id"]
    config = setup_project(tmp_path, rows)
    manifest = prepare_data(config)
    assert manifest["counts"]["normalized_messages"] == 24
    assert manifest["counts"]["conversations"] == 12


def test_golden_conversations_never_enter_development_or_review(tmp_path):
    config = setup_project(tmp_path)
    Path(config["paths"]["golden_labels"]).write_text(
        "company_id,conversation_id,message_id\nexample,customer01,customer01\n"
    )
    prepare_data(config)
    records = output_records(config)
    assert {row["message_id"] for row in records["golden"]} == {"customer01", "reply01"}

    for split in ("train", "validation", "evaluation", "quarantine"):
        assert all(row["conversation_id"] != "customer01" for row in records[split])

    review = (Path(config["paths"]["processed_dir"]) / "intent_review.csv").read_text()
    assert "customer01" not in review


def test_unknown_golden_conversation_is_an_error(tmp_path):
    config = setup_project(tmp_path)
    Path(config["paths"]["golden_labels"]).write_text(
        "company_id,conversation_id\nexample,absent\n"
    )

    with pytest.raises(ValueError, match="golden conversation"):
        prepare_data(config)


def test_long_conversation_crossing_time_boundary_is_quarantined(tmp_path):
    config = setup_project(tmp_path)
    origin = datetime(2020, 1, 1, tzinfo=timezone.utc)
    spans = {
        str(day): ((origin + timedelta(days=day)).isoformat(),) * 2 for day in range(20)
    }
    spans["14"] = (origin.isoformat(), spans["14"][1])
    assignments, _ = split_conversations(spans, config, set())
    assert assignments["14"] == "quarantine"
    assert {"train", "validation", "evaluation"}.issubset(assignments.values())


def test_missing_source_and_existing_output_fail_clearly(tmp_path):
    config = setup_project(tmp_path)
    prepare_data(config)

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_data(config)

    Path(config["paths"]["raw_csv"]).unlink()

    with pytest.raises(FileNotFoundError, match="synthetic data is only for tests"):
        prepare_data(config)
