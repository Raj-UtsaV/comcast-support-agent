"""Evaluation mechanics on synthetic labelled conversations, never headline metrics."""

import csv
import json

import pytest
from test_pipeline import setup_project

from fakes import FakeGenerator
from support_agent.agent.workflow import SupportAgent
from support_agent.data.annotations import (
    FIELDS,
    customer_messages,
    export_review,
    read_labels,
)
from support_agent.data.evidence import collect_evidence
from support_agent.data.preparation import prepare_data
from support_agent.evaluation.runner import evaluate, import_ratings, save_run
from support_agent.evaluation.offline import offline_report
from support_agent.shared.schemas import JudgeScores


@pytest.fixture
def labelled(tmp_path):
    config = setup_project(tmp_path)
    prepare_data(config)
    config["intents"] = {
        "approved_taxonomy": [
            {"id": "connection", "description": "Synthetic cable question"}
        ],
        "keyword_rules": {"connection": ["(?i)cable"]},
    }
    config["evaluation"]["golden_set"].update(min_size=1, max_size=5, target_size=2)
    records, _ = collect_evidence(config)
    evaluation = list(customer_messages(config, "evaluation").values())[:2]
    training = list(customer_messages(config, "train").values())[:2]
    training_path = tmp_path / "training_labels.csv"

    for path, samples in [
        (training_path, training),
        (tmp_path / "data/golden_set.csv", evaluation),
    ]:
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for row in samples:
                writer.writerow(
                    {
                        **{key: row[key] for key in FIELDS[:4]},
                        "intent": "connection",
                        "should_escalate": "false",
                        "relevant_evidence_ids": json.dumps(
                            [records[0]["evidence_id"]]
                        ),
                    }
                )

    class Retriever:
        def search(self, message, intent=None):
            return [{"evidence": records[0], "similarity": 1.0}]

    class Judge:
        def generate(self, task, payload, schema, instructions):
            assert "expected_intent" not in payload
            dimensions = config["evaluation"]["reply_score_dimensions"]
            return JudgeScores(
                scores=dict.fromkeys(dimensions, 5),
                explanations=dict.fromkeys(dimensions, "Synthetic test judgment"),
            )

    agent = SupportAgent(config, FakeGenerator(config), Retriever())
    return config, training_path, agent, Judge()


def test_all_methods_metrics_and_exact_saved_reply_rating_import(labelled, tmp_path):
    config, training, agent, judge = labelled
    report, rows = evaluate(config, training, agent=agent, judge=judge)
    assert set(report["methods"]) == {"agent", "trivial", "simple"}
    assert report["methods"]["agent"]["intent_accuracy"] == 1
    assert report["methods"]["agent"]["safe_auto_handle_coverage"] is None
    assert report["methods"]["trivial"]["false_auto_handle_rate"] is None
    assert report["status"] == "awaiting_human_ratings"
    assert "agent/workflow.py" in report["provenance"]["workflow_code"]
    assert "embeddings/encoder.py" in report["provenance"]["workflow_code"]
    folder = save_run(config, report, rows)
    template = folder / "human_scores_template.csv"
    with template.open() as stream:
        ratings = list(csv.DictReader(stream))
    for row in ratings:
        row["score"] = "5"
    completed = tmp_path / "human.csv"
    with completed.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ratings[0].keys())
        writer.writeheader()
        writer.writerows(ratings)
    rated = import_ratings(config, folder, completed)
    assert rated["status"] == "complete"
    assert rated["methods"]["agent"]["safe_auto_handle_coverage"] == 1
    assert rated["human_agreement"]["safety"]["exact_agreement"] == 1
    assert rated["human_agreement"]["safety"]["cohen_kappa"] is None
    # A new partial import replaces prior ratings and cannot retain old coverage.
    with completed.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ratings[0].keys())
        writer.writeheader()
        writer.writerows(ratings[:1])
    config["evaluation"]["score_max"] = 1
    partial = import_ratings(config, folder, completed)
    assert partial["status"] == "partial_human_ratings"
    assert partial["methods"]["agent"]["safe_auto_handle_coverage"] is None
    ratings[0]["reply_sha256"] = "wrong"
    with completed.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ratings[0].keys())
        writer.writeheader()
        writer.writerows(ratings)
    with pytest.raises(ValueError, match="exact saved"):
        import_ratings(config, folder, completed)


def test_metrics_only_is_explicitly_incomplete(labelled):
    config, training, agent, _ = labelled
    report, rows = evaluate(config, training, agent=agent, metrics_only=True)
    assert report["status"] == "metrics_only_incomplete"
    assert all(row["judge"] is None for row in rows)


def test_offline_report_replays_frozen_predictions(labelled, tmp_path):
    config, training, agent, judge = labelled
    _, rows = evaluate(config, training, agent=agent, judge=judge)
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    human_scores = tmp_path / "human.csv"
    with human_scores.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "company_id",
                "method",
                "message_id",
                "reply_sha256",
                "dimension",
                "score",
            ],
        )
        writer.writeheader()
        for row in rows:
            for dimension, score in row["judge"]["scores"].items():
                writer.writerow(
                    {
                        "company_id": row["company_id"],
                        "method": row["method"],
                        "message_id": row["message_id"],
                        "reply_sha256": row["reply_sha256"],
                        "dimension": dimension,
                        "score": score,
                    }
                )

    report = offline_report(config, predictions, human_scores)
    assert report["status"] == "complete"
    assert report["methods"]["agent"]["intent_accuracy"] == 1
    assert report["human_agreement"]["safety"]["exact_agreement"] == 1



def test_review_export_is_blank_and_does_not_overwrite(labelled, tmp_path):
    config, _, _, _ = labelled
    output = tmp_path / "review.csv"
    count = export_review(config, "golden", output, size=2)
    with output.open() as stream:
        rows = list(csv.DictReader(stream))
    assert count == len(rows) == 2
    assert all(not row["intent"] and not row["should_escalate"] for row in rows)
    assert len({row["conversation_id"] for row in rows}) == 2
    with pytest.raises(FileExistsError):
        export_review(config, "golden", output, size=2)


def test_training_labels_cannot_use_held_out_messages(labelled):
    config, _, _, _ = labelled
    with pytest.raises(ValueError, match="required source split"):
        read_labels(config, config["paths"]["golden_labels"], golden=False)
