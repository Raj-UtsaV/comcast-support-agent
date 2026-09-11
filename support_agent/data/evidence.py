"""Select linked customer/reply pairs from company training conversations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from support_agent.data.splits import golden_conversations
from support_agent.shared.text import normalize_text, useful_reply

SPLITS = ("train", "validation", "evaluation", "golden", "quarantine")


def _timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)

    if stamp.utcoffset() is None:
        raise ValueError("Evidence timestamps must include a timezone.")

    return stamp


def _read_messages(path: Path, company_id: str):
    """Read prepared records without accepting another company's messages."""

    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                row = json.loads(line)

                for key in ("company_id", "conversation_id", "message_id", "text"):
                    if not isinstance(row[key], str) or not row[key].strip():
                        raise ValueError("Message fields must be nonempty strings.")

                if row["company_id"] != company_id:
                    raise ValueError("Prepared data contains another company.")

                if row["role"] not in ("customer", "agent"):
                    raise ValueError("Unknown message role.")

                parent = row["parent_message_id"]

                if parent is not None and (
                    not isinstance(parent, str) or not parent.strip()
                ):
                    raise ValueError("Invalid parent message ID.")

                if not isinstance(row["metadata"], dict):
                    raise TypeError("Message metadata must be a mapping.")

                _timestamp(row["timestamp"])
            except (KeyError, TypeError, ValueError) as error:
                # Identify the record, without echoing potentially private text.
                raise ValueError(
                    f"Invalid prepared message in {path.name}, line {line_number}."
                ) from error

            yield row


def _load_training(config: dict) -> tuple[dict, set[str]]:
    """Check all split identities before any training evidence is returned."""

    directory = Path(config["paths"]["processed_dir"])
    company_id = config["company"]["id"]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))

    if manifest.get("schema_version") != 1 or manifest.get("company_id") != company_id:
        raise ValueError("Preparation manifest does not match this company/schema.")

    training = {}
    message_groups = {}
    conversation_splits = {}
    training_end = _timestamp(manifest["time_boundaries"]["validation_start"])

    for split in SPLITS:
        count = 0

        for row in _read_messages(directory / f"{split}.jsonl", company_id):
            message_id, conversation_id = row["message_id"], row["conversation_id"]

            if message_id in message_groups:
                raise ValueError(
                    "Duplicate message ID within or across prepared splits."
                )

            if conversation_splits.setdefault(conversation_id, split) != split:
                raise ValueError("A conversation overlaps prepared splits.")

            message_groups[message_id] = conversation_id
            count += 1

            if split == "train":
                if _timestamp(row["timestamp"]) >= training_end:
                    raise ValueError(
                        "Training message crosses the validation boundary."
                    )

                training[message_id] = row

        if count != manifest["messages_by_split"][split]:
            raise ValueError(f"Prepared {split} count does not match its manifest.")

    reserved = golden_conversations(config, message_groups)

    return training, reserved


def _customer_for(reply: dict, messages: dict) -> dict | None:
    """Follow only explicit parents, allowing consecutive agent follow-ups."""

    current = reply
    seen = {reply["message_id"]}

    while current["parent_message_id"] is not None:
        parent_id = current["parent_message_id"]
        parent = messages.get(parent_id)

        if parent is None or parent_id in seen:
            return None

        if parent["conversation_id"] != reply["conversation_id"]:
            return None

        if _timestamp(parent["timestamp"]) > _timestamp(current["timestamp"]):
            return None

        if parent["role"] == "customer":
            return parent

        seen.add(parent_id)
        current = parent

    return None


def collect_evidence(config: dict) -> tuple[list[dict], dict]:
    """Return historical pairs and selection counts; never train a model."""

    messages, reserved = _load_training(config)
    records = []
    counts = {
        "training_messages": len(messages),
        "agent_replies": 0,
        "excluded_golden_replies": 0,
        "rejected_reply_quality": 0,
        "missing_customer_context": 0,
        "selected_pairs": 0,
    }

    for reply in messages.values():
        if reply["role"] != "agent":
            continue

        counts["agent_replies"] += 1

        if reply["conversation_id"] in reserved:
            counts["excluded_golden_replies"] += 1
            continue

        reply_text, _ = normalize_text(reply["text"], config)

        if reply["metadata"].get("useful_reply") is not True or not useful_reply(
            reply_text, config
        ):
            counts["rejected_reply_quality"] += 1
            continue

        customer = _customer_for(reply, messages)

        if customer is None:
            counts["missing_customer_context"] += 1
            continue

        customer_text, _ = normalize_text(customer["text"], config)

        if not customer_text:
            counts["missing_customer_context"] += 1
            continue

        records.append(
            {
                "evidence_id": f"{reply['company_id']}:{reply['message_id']}",
                "company_id": reply["company_id"],
                "conversation_id": reply["conversation_id"],
                "customer_message_id": customer["message_id"],
                "reply_message_id": reply["message_id"],
                "customer_text": customer_text,
                "reply_text": reply_text,
                "timestamp": reply["timestamp"],
                "split": "train",
                "intent": None,
                "resolution_verified": False,
            }
        )

    counts["selected_pairs"] = len(records)

    return records, counts
