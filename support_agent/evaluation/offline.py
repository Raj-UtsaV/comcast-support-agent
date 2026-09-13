"""Reproduce the submitted evaluation from frozen replies and ratings."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from support_agent.agent.taxonomy import approved_categories
from support_agent.data.annotations import read_labels
from support_agent.evaluation.metrics import human_agreement, summarize
from support_agent.shared.config import PROJECT_ROOT, load_config


DEFAULT_PREDICTIONS = "data/frozen_predictions.jsonl"
DEFAULT_HUMAN_SCORES = "data/human_reply_scores.csv"


def _project_path(path):
    selected = Path(path)
    return selected if selected.is_absolute() else PROJECT_ROOT / selected


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, strict=True))


def offline_report(config, predictions_path, human_scores_path):
    golden = read_labels(config, config["paths"]["golden_labels"], golden=True)
    golden_by_id = {row["message_id"]: row for row in golden}
    rows = _read_jsonl(predictions_path)
    methods = ["agent", *config["evaluation"]["baselines"]]
    expected = {(method, message_id) for message_id in golden_by_id for method in methods}
    observed = {(row["method"], row["message_id"]) for row in rows}

    if expected != observed:
        raise ValueError("Frozen predictions do not cover exactly the golden set.")

    for row in rows:
        source = golden_by_id[row["message_id"]]
        if (
            row["company_id"] != config["company"]["id"]
            or row["message"] != source["text"]
            or row["expected_intent"] != source["intent"]
            or row["expected_escalation"] != source["should_escalate"]
            or row["relevant_evidence_ids"] != source["relevant_evidence_ids"]
        ):
            raise ValueError("Frozen prediction no longer matches the golden labels.")
        if row["reply_sha256"] != hashlib.sha256(
            row["result"]["draft_reply"].encode()
        ).hexdigest():
            raise ValueError("Frozen reply checksum mismatch.")

    dimensions = config["evaluation"]["reply_score_dimensions"]
    ratings = _read_csv(human_scores_path)
    agreement, safety = human_agreement(
        rows,
        ratings,
        dimensions,
        config["evaluation"]["score_min"],
        config["evaluation"]["score_max"],
    )
    report = {
        "status": "complete",
        "company_id": config["company"]["id"],
        "golden_examples": len(golden),
        "provenance": {
            "golden_labels_sha256": _hash(config["paths"]["golden_labels"]),
            "predictions_sha256": _hash(predictions_path),
            "human_scores_sha256": _hash(human_scores_path),
        },
        "human_agreement": agreement,
        "methods": {
            method: summarize(
                [row for row in rows if row["method"] == method],
                [entry["id"] for entry in approved_categories(config)],
                config["evaluation"]["retrieval_k"],
            )
            for method in methods
        },
    }
    settings = config["evaluation"]

    for method, metrics in report["methods"].items():
        subset = [row for row in rows if row["method"] == method]
        auto = [row for row in subset if row["result"]["decision"] == "auto_handle"]
        if auto and all((method, row["message_id"]) in safety for row in auto):
            metrics["safe_auto_handle_coverage"] = sum(
                not row["expected_escalation"]
                and row["result"]["intent"] == row["expected_intent"]
                and safety[(method, row["message_id"])] >= settings["safety_pass_score"]
                for row in auto
            ) / len(subset)
            metrics["safe_coverage_note"] = (
                "Correct intent, no required escalation, and passing author safety rating."
            )

    return report


def print_headline(report):
    agent = report["methods"]["agent"]
    print(
        json.dumps(
            {
                "golden_examples": report["golden_examples"],
                "headline_safe_auto_handle_coverage": agent[
                    "safe_auto_handle_coverage"
                ],
                "agent_intent_accuracy": agent["intent_accuracy"],
                "agent_escalation_f1": agent["escalation_f1"],
                "trivial_intent_accuracy": report["methods"]["trivial"][
                    "intent_accuracy"
                ],
                "simple_intent_accuracy": report["methods"]["simple"][
                    "intent_accuracy"
                ],
                "judge_human_exact_safety_agreement": report["human_agreement"][
                    "safety"
                ]["exact_agreement"],
            },
            indent=2,
            allow_nan=False,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/comcast.yaml")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--human-scores", default=DEFAULT_HUMAN_SCORES)
    parser.add_argument("--output", default="results/comcast/offline_report.json")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        report = offline_report(
            config, _project_path(args.predictions), _project_path(args.human_scores)
        )
        output = _project_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print_headline(report)
        print(output)
    except (ValueError, OSError, csv.Error, json.JSONDecodeError) as error:
        parser.exit(1, f"Offline evaluation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
