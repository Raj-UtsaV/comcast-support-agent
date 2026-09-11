"""Evaluate frozen agent/baselines and import ratings of the exact saved replies."""

import argparse
import csv
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from support_agent.agent.runtime import create_agent
from support_agent.agent.taxonomy import approved_categories
from support_agent.data.annotations import read_labels
from support_agent.data.evidence import collect_evidence
from support_agent.evaluation.baselines import Baselines
from support_agent.evaluation.metrics import summarize
from support_agent.evaluation.ratings import import_ratings
from support_agent.models.client import create_generator
from support_agent.retrieval.index_state import file_hash, source_state
from support_agent.shared.config import load_config
from support_agent.shared.schemas import JudgeScores, SupportRequest


def evaluate(config, training_path, *, agent=None, judge=None, metrics_only=False):
    config = deepcopy(config)
    categories = approved_categories(config)
    initial_state = source_state(config)
    training_hash = file_hash(Path(training_path))
    if not config["intents"]["keyword_rules"]:
        raise ValueError(
            "Define training-reviewed keyword rules for the simple baseline first."
        )

    golden = read_labels(config, config["paths"]["golden_labels"], golden=True)
    training = read_labels(config, training_path, golden=False)
    records, _ = collect_evidence(config)
    known = {row["evidence_id"] for row in records}

    if any(not set(row["relevant_evidence_ids"]).issubset(known) for row in golden):
        raise ValueError(
            "Golden relevance labels reference ineligible historical evidence."
        )

    methods = ["agent", *config["evaluation"]["baselines"]]
    if methods != ["agent", "trivial", "simple"]:
        raise ValueError("Evaluation requires the agent, trivial and simple baselines.")

    agent = agent if agent is not None else create_agent(config)
    judging = config["evaluation"]["judge_enabled"] and not metrics_only
    judge = (
        (judge if judge is not None else create_generator(config, "judge"))
        if judging
        else None
    )
    baselines = Baselines(config, records, training)
    rows = []

    for sample in golden:
        for method in methods:
            result = (
                agent.analyse(
                    SupportRequest(
                        company_id=sample["company_id"], message=sample["text"]
                    )
                ).model_dump()
                if method == "agent"
                else baselines.analyse(method, sample["text"])
            )
            judged = None
            if judge is not None:
                judged = JudgeScores.model_validate(
                    judge.generate(
                        "judge",
                        {
                            "message": sample["text"],
                            "reply": result["draft_reply"],
                            "evidence": result["retrieved_examples"],
                            "dimensions": config["evaluation"][
                                "reply_score_dimensions"
                            ],
                            "score_min": config["evaluation"]["score_min"],
                            "score_max": config["evaluation"]["score_max"],
                        },
                        JudgeScores,
                        config["evaluation"]["judge_instructions"],
                    )
                ).model_dump()
                dimensions = set(config["evaluation"]["reply_score_dimensions"])
                if (
                    set(judged["scores"]) != dimensions
                    or set(judged["explanations"]) != dimensions
                ):
                    raise ValueError("Judge omitted required score dimensions.")
                if any(
                    not config["evaluation"]["score_min"]
                    <= score
                    <= config["evaluation"]["score_max"]
                    for score in judged["scores"].values()
                ):
                    raise ValueError("Judge returned an out-of-range score.")
                if any(
                    not explanation.strip()
                    for explanation in judged["explanations"].values()
                ):
                    raise ValueError("Judge explanations must be nonempty.")

            rows.append(
                {
                    "company_id": sample["company_id"],
                    "message_id": sample["message_id"],
                    "method": method,
                    "message": sample["text"],
                    "expected_intent": sample["intent"],
                    "expected_escalation": sample["should_escalate"],
                    "relevant_evidence_ids": sample["relevant_evidence_ids"],
                    "result": result,
                    "judge": judged,
                    "reply_sha256": hashlib.sha256(
                        result["draft_reply"].encode()
                    ).hexdigest(),
                }
            )

    if (
        source_state(config) != initial_state
        or file_hash(Path(training_path)) != training_hash
    ):
        raise ValueError(
            "Evaluation inputs changed during the run; results were not published."
        )

    report = {
        "provenance": {
            "source_state": initial_state,
            "training_labels_sha256": training_hash,
            "configuration_sha256": hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest(),
            "models": {
                role: {
                    key: value
                    for key, value in settings.items()
                    if key in ("provider", "name", "revision")
                }
                for role, settings in config["models"].items()
            },
            "workflow_code": {
                str(path.relative_to(Path(__file__).resolve().parents[1])): file_hash(
                    path
                )
                for path in sorted(Path(__file__).resolve().parents[1].rglob("*.py"))
            },
        },
        "company_id": config["company"]["id"],
        "rating_settings": {
            key: config["evaluation"][key]
            for key in (
                "reply_score_dimensions",
                "score_min",
                "score_max",
                "safety_pass_score",
            )
        },
        "status": "awaiting_human_ratings" if judging else "metrics_only_incomplete",
        "golden_examples": len(golden),
        "human_agreement": None,
        "methods": {
            method: summarize(
                [row for row in rows if row["method"] == method],
                [entry["id"] for entry in categories],
                config["evaluation"]["retrieval_k"],
            )
            for method in methods
        },
    }
    return report, rows


def save_run(config, report, rows):
    root = Path(config["paths"]["results_dir"])
    root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="evaluation-", dir=root))
    (folder / "predictions.json").write_text(
        json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8"
    )
    (folder / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    with (folder / "human_scores_template.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
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
            for dimension in config["evaluation"]["reply_score_dimensions"]:
                writer.writerow(
                    {
                        **{
                            key: row[key]
                            for key in (
                                "company_id",
                                "method",
                                "message_id",
                                "reply_sha256",
                            )
                        },
                        "dimension": dimension,
                    }
                )
    with tempfile.NamedTemporaryFile(dir=root, mode="w", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump({"run": folder.name}, stream)
    os.replace(temporary, root / "latest.json")
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "rate"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--training-labels")
    parser.add_argument("--metrics-only", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--human-scores")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "run":
            if not args.training_labels:
                parser.error("run requires --training-labels")
            report, rows = evaluate(
                config, args.training_labels, metrics_only=args.metrics_only
            )
            print(save_run(config, report, rows))
        else:
            if not args.run or not args.human_scores:
                parser.error("rate requires --run and --human-scores")
            print(
                json.dumps(
                    import_ratings(config, args.run, args.human_scores), indent=2
                )
            )
    except (ValueError, OSError, RuntimeError, csv.Error) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
