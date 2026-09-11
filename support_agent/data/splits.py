"""Chronological conversation splits and reserved evaluation conversations."""

import csv
from datetime import datetime
from pathlib import Path


def golden_conversations(config: dict, groups: dict | None = None) -> set[str]:
    path = Path(config["paths"]["golden_labels"])

    if not path.exists():
        return set()

    result = set()
    known = set(groups.values()) if groups is not None else None

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)

        if not {"company_id", "conversation_id"}.issubset(reader.fieldnames or []):
            raise ValueError(
                "Golden annotations require company_id and conversation_id columns."
            )

        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed golden annotation row.")

            if not row["company_id"].strip() or not row["conversation_id"].strip():
                raise ValueError(
                    "Golden annotations require nonempty company and conversation IDs."
                )

            if row["company_id"] != config["company"]["id"]:
                continue

            conversation_id = row["conversation_id"]

            if known is not None and conversation_id not in known:
                raise ValueError(
                    "A golden conversation cannot be matched to this source dataset."
                )

            message_id = row.get("message_id")

            if (
                groups is not None
                and message_id
                and groups.get(message_id) != conversation_id
            ):
                raise ValueError(
                    "A golden message does not belong to its annotated conversation."
                )

            result.add(conversation_id)

    return result


def split_conversations(spans: dict, config: dict, golden: set[str]) -> tuple[dict, dict]:
    """Assign complete groups to nonoverlapping UTC time ranges."""

    if len(spans) < 3:
        raise ValueError(
            "At least three conversations are required for chronological splitting."
        )

    ends = sorted(span[1] for span in spans.values())
    fractions = config["splits"]
    first = max(1, min(len(ends) - 2, int(len(ends) * fractions["train_fraction"])))
    second = max(
        first + 1,
        min(
            len(ends) - 1,
            int(
                len(ends)
                * (fractions["train_fraction"] + fractions["validation_fraction"])
            ),
        ),
    )

    def midpoint(index):
        left, right = (
            datetime.fromisoformat(ends[index - 1]),
            datetime.fromisoformat(ends[index]),
        )

        return (left + (right - left) / 2).isoformat()

    validation_start, evaluation_start = midpoint(first), midpoint(second)
    assignments = {}

    for conversation_id, (start, end) in spans.items():
        if conversation_id in golden:
            split = "golden"
        elif end < validation_start:
            split = "train"
        elif start >= validation_start and end < evaluation_start:
            split = "validation"
        elif start >= evaluation_start:
            split = "evaluation"
        else:
            split = "quarantine"

        assignments[conversation_id] = split

    missing = {"train", "validation", "evaluation"} - set(assignments.values())

    if missing:
        raise ValueError(
            "Chronological splitting leaves an empty development/evaluation split; review the data and fractions."
        )

    return assignments, {
        "validation_start": validation_start,
        "evaluation_start": evaluation_start,
    }
