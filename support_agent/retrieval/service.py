"""Build, inspect and search saved historical evidence from the command line."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from contextlib import redirect_stdout

from support_agent.embeddings.encoder import TextEmbedder, create_embedder
from support_agent.retrieval.index_store import build_saved_index, load_saved_index
from support_agent.shared.config import ConfigError, load_config
from support_agent.shared.text import normalize_text


def _message_limit(config: dict) -> int:
    try:
        limit = config["runtime"]["max_message_characters"]
    except (KeyError, TypeError):
        raise ConfigError("runtime.max_message_characters is required.") from None

    if type(limit) is not int or limit < 1:
        raise ConfigError("runtime.max_message_characters must be a positive integer.")

    return limit


def retrieve(config: dict,message: str,*,intent: str | None = None,embedder: TextEmbedder | None = None,) -> dict:
    """Mask one customer message and search a freshly validated saved index."""

    limit = _message_limit(config)

    if not isinstance(message, str) or not message.strip():
        raise ValueError("The customer message must be a nonempty string.")

    if len(message) > limit:
        raise ValueError(
            f"The customer message exceeds the configured {limit}-character limit."
        )

    text, sensitive_information = normalize_text(message, config)

    if not text or len(text) > limit:
        raise ValueError(
            "The cleaned customer message is empty or exceeds the configured limit."
        )

    if intent is not None:
        try:
            entries = config["intents"]["approved_taxonomy"]
        except (KeyError, TypeError):
            raise ConfigError(
                "intents.approved_taxonomy is required for an explicit intent."
            ) from None

        if not isinstance(entries, list) or any(
            not isinstance(entry, dict)
            or not isinstance(entry.get("id"), str)
            or not entry["id"].strip()
            for entry in entries
        ):
            raise ConfigError("Approved company categories must contain nonempty IDs.")

        approved = {entry["id"] for entry in entries}

        if not isinstance(intent, str) or intent not in approved:
            raise ValueError(
                "The supplied intent must be an approved company category ID."
            )

    index = load_saved_index(config)
    matches = []
    status = "no_matches"

    if config["retrieval"]["filter_by_intent"] and intent is None:
        status = "missing_intent"
    elif index.size:
        encoder = embedder if embedder is not None else create_embedder(config)

        if encoder.identity != index.embedding_identity:
            raise ValueError(
                "The query encoder does not match the saved index's model identity."
            )

        matches = index.search(
            encoder.encode([text]),
            company_id=config["company"]["id"],
            embedding_identity=encoder.identity,
            intent=intent,
        )

        if matches:
            status = "matches_found"

    return {
        "company_id": config["company"]["id"],
        "query": {"text": text, "sensitive_information": sensitive_information},
        "intent": intent,
        "status": status,
        "matches": matches,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build", help="Encode evidence and save a complete index"
    )
    inspect = commands.add_parser("inspect", help="Validate and describe a saved index")
    search = commands.add_parser("search", help="Find historical replies for a message")

    for command in (build, inspect, search):
        command.add_argument("--config", required=True, help="Company YAML path")

    build.add_argument(
        "--rebuild", action="store_true", help="Publish a new saved version"
    )
    message_source = search.add_mutually_exclusive_group(required=True)
    message_source.add_argument("--message", help="Customer message to search")
    message_source.add_argument(
        "--stdin", action="store_true", help="Read the message from standard input"
    )
    search.add_argument("--intent", help="Optional approved company category ID")
    args = parser.parse_args(argv)

    try:
        # Library progress belongs on stderr; stdout remains one JSON document.
        with redirect_stdout(sys.stderr):
            config = load_config(args.config)

            if args.command == "search":
                message = (
                    sys.stdin.read(_message_limit(config) + 1)
                    if args.stdin
                    else args.message
                )
                result = retrieve(config, message, intent=args.intent)
            else:
                index = (
                    build_saved_index(config, rebuild=args.rebuild)
                    if args.command == "build"
                    else load_saved_index(config)
                )
                result = {
                    "company_id": index.company_id,
                    "status": "built" if args.command == "build" else "ready",
                    "indexed_pairs": index.size,
                    "embedding_identity": index.embedding_identity,
                }
    except (ConfigError, ValueError, OSError, RuntimeError, csv.Error) as error:
        print(f"Retrieval failed: {error}", file=sys.stderr)

        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
