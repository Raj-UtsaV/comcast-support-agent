"""Export review sheets and validate human labels against source identities."""

import argparse
import csv
import json
import random
from pathlib import Path

from support_agent.data.splits import golden_conversations
from support_agent.shared.config import PROJECT_ROOT, load_config

FIELDS = [
    "company_id",
    "conversation_id",
    "message_id",
    "text",
    "intent",
    "should_escalate",
    "relevant_evidence_ids",
    "notes",
]


def customer_messages(config: dict, split: str) -> dict:
    if split not in ("train", "evaluation"):
        raise ValueError("Annotation sources must be train or evaluation.")

    messages = {}
    excluded = golden_conversations(config) if split == "train" else set()
    path = Path(config["paths"]["processed_dir"]) / f"{split}.jsonl"

    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)

        if row["company_id"] != config["company"]["id"]:
            raise ValueError("Annotation source contains another company.")

        if row["role"] == "customer" and row["conversation_id"] not in excluded:
            if row["message_id"] in messages:
                raise ValueError("Duplicate annotation source identity.")

            messages[row["message_id"]] = row

    return messages


def export_review(config, kind, output, size=None):
    split = "evaluation" if kind == "golden" else "train"
    rows = list(customer_messages(config, split).values())
    random.Random(config["random_seed"]).shuffle(rows)
    count = (
        size
        if size is not None
        else (
            config["evaluation"]["golden_set"]["target_size"]
            if kind == "golden"
            else config["intent_discovery"]["sample_size"]
        )
    )

    if type(count) is not int or count < 1:
        raise ValueError("Review size must be a positive integer.")

    selected, seen = [], set()

    for row in rows:
        if row["conversation_id"] not in seen:
            seen.add(row["conversation_id"])
            selected.append(row)

        if len(selected) == count:
            break

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()

        for row in selected:
            text = row["text"]
            if text.lstrip().startswith(("=", "+", "-", "@")):
                text = "'" + text
            writer.writerow({**{key: row[key] for key in FIELDS[:3]}, "text": text})

    return len(selected)


def read_labels(config, path, *, golden):
    lookup = customer_messages(config, "evaluation" if golden else "train")
    allowed = {entry["id"] for entry in config["intents"]["approved_taxonomy"]}
    result, seen, conversations = [], set(), set()

    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, strict=True)

        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed label CSV row.")

            if row.get("company_id") != config["company"]["id"]:
                raise ValueError("Labels must belong to the selected company.")

            source = lookup.get(row.get("message_id"))

            if source is None or source["conversation_id"] != row.get(
                "conversation_id"
            ):
                raise ValueError(
                    "Label identity does not match the required source split."
                )

            if row["message_id"] in seen or (
                golden and row["conversation_id"] in conversations
            ):
                raise ValueError("Duplicate message/conversation in evaluation labels.")

            if row.get("intent") not in allowed:
                raise ValueError("Every label requires an approved intent ID.")

            seen.add(row["message_id"])
            conversations.add(row["conversation_id"])
            item = {**source, "intent": row["intent"]}

            if golden:
                if row.get("should_escalate", "").lower() not in ("true", "false"):
                    raise ValueError(
                        "Golden should_escalate labels must be true or false."
                    )

                relevant = json.loads(row.get("relevant_evidence_ids", ""))

                if not isinstance(relevant, list) or any(
                    not isinstance(value, str) or not value for value in relevant
                ):
                    raise ValueError(
                        "Relevant evidence IDs must be a JSON list of strings."
                    )

                item.update(
                    should_escalate=row["should_escalate"].lower() == "true",
                    relevant_evidence_ids=relevant,
                )

            result.append(item)

    if not result:
        raise ValueError("No completed labels found.")

    if golden:
        bounds = config["evaluation"]["golden_set"]
        if not bounds["min_size"] <= len(result) <= bounds["max_size"]:
            raise ValueError(
                "Golden set size is outside the configured evaluation bounds."
            )

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["golden", "training"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int)
    args = parser.parse_args(argv)
    output = (PROJECT_ROOT / args.output).resolve()

    if not output.is_relative_to(PROJECT_ROOT):
        parser.error("Review output must stay inside the project.")

    try:
        count = export_review(load_config(args.config), args.kind, output, args.size)
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, f"Review export failed: {error}\n")

    print(
        json.dumps(
            {"examples": count, "output": str(output), "labels": "pending_human_review"}
        )
    )


if __name__ == "__main__":
    main()
