"""Prepare company conversation files using the focused processing modules."""

import argparse
import csv
import hashlib
import json
import random
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from support_agent.data.conversations import ADAPTERS, company_groups
from support_agent.data.splits import golden_conversations, split_conversations
from support_agent.shared.config import ConfigError, load_config
from support_agent.shared.text import normalize_text, parse_timestamp, useful_reply

MESSAGE_FIELDS = (
    "company_id",
    "conversation_id",
    "message_id",
    "parent_message_id",
    "timestamp",
    "role",
    "text",
    "channel",
    "metadata",
)


def prepare_data(config: dict) -> dict:
    """Create masked conversation splits and a training-only intent review CSV."""

    source = Path(config["paths"]["raw_csv"])

    if not source.is_file():
        raise FileNotFoundError(
            f"Source dataset missing: {source}. Place the real CSV there; synthetic data is only for tests."
        )

    adapter = ADAPTERS.get(config["dataset"]["adapter"])

    if adapter is None:
        raise ConfigError(
            "Unsupported dataset.adapter; register an adapter for this source format."
        )

    output = Path(config["paths"]["processed_dir"])

    if output.exists():
        raise FileExistsError(
            "Processed output already exists. Choose a new paths.processed_dir to prepare another version."
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output.parent) as scratch:
        scratch = Path(scratch)
        connection = sqlite3.connect(scratch / "source.sqlite3")

        try:
            counts = adapter(connection, config)
            groups, records = company_groups(connection)
        finally:
            connection.close()

        spans = {}
        prepared = []
        empty = 0

        for message_id, row in records.items():
            conversation_id = groups[message_id]

            try:
                timestamp = parse_timestamp(
                    row["timestamp"], config["dataset"]["timestamp_format"]
                )
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid timestamp for source message {message_id}."
                ) from None

            start, end = spans.get(conversation_id, (timestamp, timestamp))
            spans[conversation_id] = min(start, timestamp), max(end, timestamp)
            text, flags = normalize_text(row["text"], config)

            if not text:
                empty += 1
                continue

            prepared.append(
                {
                    "company_id": config["company"]["id"],
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "parent_message_id": row["parent_message_id"],
                    "timestamp": timestamp,
                    "role": row["role"],
                    "text": text,
                    "channel": config["dataset"]["channel"],
                    "metadata": {
                        "sensitive_information": flags,
                        "useful_reply": useful_reply(text, config)
                        if row["role"] == "agent"
                        else None,
                        "resolution_verified": False,
                        "parent_missing_from_source": row["parent_missing_from_source"],
                        "parent_from_other_company": row["parent_from_other_company"],
                    },
                }
            )

        present = {row["conversation_id"] for row in prepared}
        spans = {key: value for key, value in spans.items() if key in present}
        golden = golden_conversations(config, groups)

        if not golden.issubset(present):
            raise ValueError(
                "A golden conversation has no nonempty messages after cleaning."
            )

        assignments, boundaries = split_conversations(spans, config, golden)
        prepared.sort(key=lambda row: (row["timestamp"], row["message_id"]))
        staged = scratch / "output"
        staged.mkdir()
        split_names = ("train", "validation", "evaluation", "golden", "quarantine")
        row_counts = Counter()

        with ExitStack() as stack:
            streams = {
                name: stack.enter_context(
                    (staged / f"{name}.jsonl").open("w", encoding="utf-8")
                )
                for name in split_names
            }

            for row in prepared:
                split = assignments[row["conversation_id"]]
                streams[split].write(json.dumps(row, ensure_ascii=False) + "\n")
                row_counts[split] += 1

        sample_pool = [
            row
            for row in prepared
            if row["role"] == "customer"
            and assignments[row["conversation_id"]] == "train"
        ]
        sample = random.Random(config["random_seed"]).sample(
            sample_pool,
            min(len(sample_pool), config["intent_discovery"]["sample_size"]),
        )
        review_fields = (
            "company_id",
            "conversation_id",
            "message_id",
            "text",
            "proposed_intent",
            "review_notes",
        )

        with (staged / "intent_review.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=review_fields)
            writer.writeheader()

            for row in sample:
                values = {key: row.get(key, "") for key in review_fields}
                # Prevent spreadsheet formulas in this human-review export only.

                if values["text"].startswith(("=", "+", "-", "@")):
                    values["text"] = "'" + values["text"]

                writer.writerow(values)

        with source.open("rb") as stream:
            source_digest = hashlib.file_digest(stream, "sha256").hexdigest()

        manifest = {
            "schema_version": 1,
            "company_id": config["company"]["id"],
            "source": {
                "sha256": source_digest,
                "bytes": source.stat().st_size,
                "provenance": config["dataset"].get("source", {}),
            },
            "config_sha256": hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest(),
            "counts": {
                **counts,
                "selected_source_messages": len(records),
                "empty_messages_removed": empty,
                "normalized_messages": len(prepared),
                "conversations": len(spans),
                "intent_review_examples": len(sample),
            },
            "messages_by_split": {name: row_counts[name] for name in split_names},
            "conversations_by_split": {
                name: sum(split == name for split in assignments.values())
                for name in split_names
            },
            "time_boundaries": boundaries,
            "golden_annotations_present": Path(
                config["paths"]["golden_labels"]
            ).is_file(),
            "evaluation_status": "not_run",
        }
        (staged / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        staged.rename(output)

    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare"])
    parser.add_argument(
        "--config",
        required=True,
        help="Company YAML path, relative to the project root or absolute",
    )
    args = parser.parse_args(argv)

    try:
        manifest = prepare_data(load_config(args.config))
    except (ConfigError, ValueError, OSError, csv.Error, sqlite3.Error) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)

        return 1

    print(json.dumps(manifest, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
