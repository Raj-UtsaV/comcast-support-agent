"""Bounded, configured basic guidance when a customer cannot get a useful draft."""

import re

from support_agent.agent.safety import pattern_flags
from support_agent.shared.text import normalize_text


def basic_guidance(config, messages, text):
    """Offer each configured guide once; do not mask sensitive/account requests."""
    customer_texts = [text] + [
        item["text"] for item in messages
        if item["role"] == "customer" and item.get("context", True)
    ]
    for message in customer_texts:
        _, sensitive = normalize_text(message, config)
        if sensitive or pattern_flags(message, config["safety"]["request_patterns"]):
            return None
    if re.search(r"(?i)\b(human|representative|person|agent)\b", text):
        return None
    previous = {item["text"] for item in messages if item["role"] == "agent"}
    guides = config.get("customer_support", {}).get("troubleshooting", [])
    matching = [g for g in guides if any(re.search(p, text) for p in g["patterns"])]
    # Explicit new topics take precedence. Otherwise recover the active guide
    # from the latest assistant turn, including its diagnostic follow-ups.
    active = matching
    if not active:
        for item in reversed(messages):
            if item["role"] != "agent":
                continue
            active = [g for g in guides if item["text"] in {
                g["reply"].strip(), *(f["reply"].strip() for f in g.get("followups", []))
            }]
            break
    for guide in active:
        reply = guide["reply"].strip()
        if (
            reply not in previous
            and any(re.search(pattern, text) for pattern in guide["patterns"])
            and not pattern_flags(reply, config["safety"]["reply_patterns"])
        ):
            return reply
        if reply in previous:
            for followup in guide.get("followups", []):
                next_reply = followup["reply"].strip()
                if (
                    next_reply not in previous
                    and any(re.search(pattern, text) for pattern in followup["patterns"])
                    and not pattern_flags(next_reply, config["safety"]["reply_patterns"])
                ):
                    return next_reply
    return None


def is_handoff(text):
    return bool(re.search(
        r"(?i)\b(contact|call|reach out to)\b.{0,50}\b(support|representative|service)\b"
        r"|\b(send|provide)\b.{0,30}\b(dm|direct message)\b",
        text,
    ))
