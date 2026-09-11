"""Import independent human ratings of exact saved evaluation replies."""

import csv
import json
import os
import tempfile
from pathlib import Path

from support_agent.evaluation.metrics import human_agreement


def import_ratings(config, folder, path):
    folder = Path(folder)
    report = json.loads((folder / "report.json").read_text())
    rows = json.loads((folder / "predictions.json").read_text())
    with Path(path).open(newline="", encoding="utf-8") as stream:
        ratings = list(csv.DictReader(stream, strict=True))
    expected = {(row["method"], row["message_id"]): row["reply_sha256"] for row in rows}
    if report["company_id"] != config["company"]["id"] or any(
        row["company_id"] != report["company_id"] for row in rows
    ):
        raise ValueError("Evaluation run belongs to another company.")
    for row in ratings:
        if row.get("company_id") != report["company_id"] or expected.get(
            (row.get("method"), row.get("message_id"))
        ) != row.get("reply_sha256"):
            raise ValueError("Human ratings do not match these exact saved replies.")
    settings = report["rating_settings"]
    agreement, safety = human_agreement(
        rows,
        ratings,
        settings["reply_score_dimensions"],
        settings["score_min"],
        settings["score_max"],
    )
    report["human_agreement"] = agreement
    for method, metrics in report["methods"].items():
        metrics["safe_auto_handle_coverage"] = None
        metrics["safe_coverage_note"] = (
            "Requires matched independent human reply-safety ratings."
        )
        subset = [row for row in rows if row["method"] == method]
        auto = [row for row in subset if row["result"]["decision"] == "auto_handle"]
        if all((method, row["message_id"]) in safety for row in auto):
            metrics["safe_auto_handle_coverage"] = sum(
                not row["expected_escalation"]
                and row["result"]["intent"] == row["expected_intent"]
                and safety[(method, row["message_id"])] >= settings["safety_pass_score"]
                for row in auto
            ) / len(subset)
            metrics["safe_coverage_note"] = (
                "Requires correct intent, no required escalation and a passing independent human safety rating."
            )
    complete = len(ratings) == len(rows) * len(
        settings["reply_score_dimensions"]
    ) and all(row.get("judge") for row in rows)
    report["status"] = "complete" if complete else "partial_human_ratings"
    with tempfile.NamedTemporaryFile(dir=folder, mode="w", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(report, stream, indent=2, allow_nan=False)
    os.replace(temporary, folder / "report.json")
    return report
