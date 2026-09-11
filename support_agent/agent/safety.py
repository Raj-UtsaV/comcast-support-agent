"""Configurable risk signals and deterministic draft checks."""

import re

from support_agent.shared.config import ConfigError


def pattern_flags(text: str, patterns: dict) -> list[str]:
    return [
        name
        for name, rules in patterns.items()
        if any(re.search(rule, text) for rule in rules)
    ]


def validate_safety(config: dict) -> None:
    settings = config["safety"]
    threshold = settings["min_intent_confidence"]

    if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
        raise ConfigError("Safety confidence threshold must be between zero and one.")

    if not isinstance(settings["escalate_on"], list) or any(
        not isinstance(flag, str) or not flag for flag in settings["escalate_on"]
    ):
        raise ConfigError("safety.escalate_on must be a list of signal names.")

    for field in ("request_patterns", "reply_patterns"):
        if not isinstance(settings[field], dict):
            raise ConfigError("Safety patterns must be mappings.")

        for patterns in settings[field].values():
            if not isinstance(patterns, list):
                raise ConfigError("Safety rules must be lists of regular expressions.")

            for pattern in patterns:
                try:
                    re.compile(pattern)
                except (re.error, TypeError):
                    raise ConfigError("Invalid safety regular expression.") from None

    if (
        not isinstance(settings["fallback_reply"], str)
        or not settings["fallback_reply"].strip()
    ):
        raise ConfigError("A nonempty safety fallback reply is required.")

    if pattern_flags(settings["fallback_reply"], settings["reply_patterns"]):
        raise ConfigError("The fallback reply matches a prohibited reply pattern.")


def decision_flags(config: dict, classification, matches: list, flags: list[str]) -> list[str]:
    flags = list(flags)

    if classification.intent is None:
        flags.append("unknown_intent")

    if classification.confidence < config["safety"]["min_intent_confidence"]:
        flags.append("low_intent_confidence")

    if not matches:
        flags.extend(["missing_evidence", "low_retrieval_similarity"])

    if classification.intent in config["safety"]["risky_intents"]:
        flags.append("risky_intent")

    return sorted(set(flags))
