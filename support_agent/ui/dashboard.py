"""Load evaluation artifacts and identify failures."""

import json
from pathlib import Path

def load_report(config):
    root = Path(config["paths"]["results_dir"]).resolve()
    pointer = root / "latest.json"
    if not pointer.exists():
        return None, []
    name = json.loads(pointer.read_text())["run"]
    folder = (root / name).resolve()
    if folder.parent != root:
        raise ValueError("Evaluation path is outside this company's results directory.")
    report = json.loads((folder / "report.json").read_text())
    rows = json.loads((folder / "predictions.json").read_text())
    if report["company_id"] != config["company"]["id"] or any(
        row["company_id"] != config["company"]["id"] for row in rows
    ):
        raise ValueError("Evaluation results belong to another company.")
    return report, rows



def failure_rows(rows, config):
    failures = []
    for row in rows:
        result = row["result"]
        reasons = []
        if result["intent"] != row["expected_intent"]:
            reasons.append("incorrect category")
        found = {
            item["evidence"]["evidence_id"] for item in result["retrieved_examples"]
        }
        if row["relevant_evidence_ids"] and not found.intersection(
            row["relevant_evidence_ids"]
        ):
            reasons.append("poor retrieval")
        if set(result["safety_flags"]) & {"unsupported_claim", "verification_failed"}:
            reasons.append("blocked or unverified draft")
        if (
            row.get("judge")
            and row["judge"]["scores"].get("safety", 0)
            < config["evaluation"]["safety_pass_score"]
        ):
            reasons.append("low judge safety score")
        if (
            row["method"] == "agent"
            and result["intent_confidence"] < config["safety"]["min_intent_confidence"]
        ):
            reasons.append("low confidence")
        if reasons:
            failures.append(
                {
                    "method": row["method"],
                    "message_id": row["message_id"],
                    "message": row["message"],
                    "expected": row["expected_intent"],
                    "predicted": result["intent"],
                    "reasons": "; ".join(reasons),
                }
            )
    return failures
