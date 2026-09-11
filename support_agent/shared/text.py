"""Reusable text cleaning, sensitive-information masking and time parsing."""

import html
import re
import unicodedata
from datetime import datetime, timezone

PII_PATTERNS = {
    "email": re.compile(
        r"__email__|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE
    ),
    "account_number": re.compile(
        r"\b(?:account|acct)(?:\s+(?:number|no\.?|id))?\s*[:#-]?\s*\d[\d -]*\d\b",
        re.IGNORECASE,
    ),
    "phone": re.compile(
        r"__phone__|(?<!\w)(?:\+?\d[\d ().-]{5,}\d)(?!\w)", re.IGNORECASE
    ),
    "username": re.compile(r"(?<!\w)@[A-Z0-9_]+", re.IGNORECASE),
}


def normalize_text(text: str, config: dict) -> tuple[str, list[str]]:
    """Return cleaned text and detected sensitive-information categories."""

    settings = config["dataset"]
    text = unicodedata.normalize(
        settings["normalization"]["unicode_form"], html.unescape(text)
    )

    if settings["normalization"]["collapse_whitespace"]:
        text = " ".join(text.split())

    flags = []

    for category, pattern in PII_PATTERNS.items():
        if category in settings["pii"]["mask_types"] and pattern.search(text):
            flags.append(category)
            text = pattern.sub(f"[{category.upper()}]", text)

    return text.strip(), flags


def useful_reply(text: str, config: dict) -> bool:
    """Heuristic evidence filter; a useful reply is not proof of resolution."""

    settings = config["dataset"]["reply_quality"]
    body = re.sub(r"\[(?:EMAIL|PHONE|ACCOUNT_NUMBER|USERNAME)\]", "", text).strip()

    return len(body.split()) >= settings["min_words"] and not any(
        re.fullmatch(pattern, body) for pattern in settings["reject_fullmatch_patterns"]
    )


def parse_timestamp(text: str, format_string: str) -> str:
    # Translate English names to numbers without changing process-wide locale.
    for directive, names, replacement, start in (
        ("%b", "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec", "%m", 1),
        ("%a", "Sun Mon Tue Wed Thu Fri Sat", "%w", 0),
    ):
        if directive in format_string:
            lookup = {
                name: str(index) for index, name in enumerate(names.split(), start)
            }
            text = re.sub(
                r"\b(" + "|".join(lookup) + r")\b",
                lambda match, names=lookup: names[match[0]],
                text,
            )
            format_string = format_string.replace(directive, replacement)

    result = datetime.strptime(text, format_string)  # noqa: DTZ007 -- offset validated below

    if result.utcoffset() is None:
        raise ValueError("Source timestamps must include a timezone offset.")

    return result.astimezone(timezone.utc).isoformat()
