"""Validate human-approved company request categories and baseline rules."""

import re

from support_agent.shared.config import ConfigError


def approved_categories(config: dict) -> list[dict]:
    entries = config["intents"]["approved_taxonomy"]

    if not isinstance(entries, list) or not entries:
        raise ConfigError(
            "Review intent_review.csv and fill intents.approved_taxonomy before running the real agent."
        )

    seen = set()

    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("id"), str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*", entry["id"])
        ):
            raise ConfigError(
                "Category IDs must use lowercase letters, digits and underscores."
            )

        if (
            entry["id"] in seen
            or not isinstance(entry.get("description"), str)
            or not entry["description"].strip()
        ):
            raise ConfigError(
                "Categories require unique IDs and nonempty descriptions."
            )

        seen.add(entry["id"])

    if not set(config["safety"]["risky_intents"]).issubset(seen):
        raise ConfigError("Risky categories must be approved company IDs.")

    rules = config["intents"]["keyword_rules"]

    if not isinstance(rules, dict) or not set(rules).issubset(seen):
        raise ConfigError("Baseline keyword rules must reference approved IDs.")

    for patterns in rules.values():
        if not isinstance(patterns, list):
            raise ConfigError("Each keyword rule must contain a list of patterns.")

        for pattern in patterns:
            try:
                re.compile(pattern)
            except (re.error, TypeError):
                raise ConfigError("Invalid category keyword pattern.") from None

    return entries
