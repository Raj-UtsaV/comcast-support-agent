"""Analyse messages or inspect project readiness without exposing credentials."""

import argparse
import csv
import json
import sqlite3
import sys
from contextlib import redirect_stdout

from support_agent.agent.runtime import create_agent
from support_agent.agent.taxonomy import approved_categories
from support_agent.models.client import create_generator
from support_agent.retrieval.index_store import load_saved_index
from support_agent.shared.config import load_config
from support_agent.shared.schemas import SupportRequest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyse", "check", "setup"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--rebuild", action="store_true", help="With setup, rebuild the vector index using existing processed data.")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--message")
    sources.add_argument("--stdin", action="store_true")
    args = parser.parse_args(argv)
    if args.rebuild and args.command != "setup":
        parser.error("--rebuild is only supported with setup")
    try:
        with redirect_stdout(sys.stderr):
            config = load_config(args.config)
            if args.command == "setup":
                from support_agent.setup import setup_pipeline

                result = setup_pipeline(config, rebuild=args.rebuild)
            elif args.command == "check":
                checks = {}
                if config["runtime"]["demo_mode"]:
                    create_agent(config)
                    checks["demo"] = "ready: explicitly synthetic"
                else:
                    for name, check in (
                        ("categories", lambda: approved_categories(config)),
                        ("generator", lambda: create_generator(config)),
                        ("judge", lambda: create_generator(config, "judge")),
                        ("saved_index", lambda: load_saved_index(config)),
                    ):
                        try:
                            check()
                            checks[name] = "ready"
                        except (ValueError, OSError, RuntimeError) as error:
                            checks[name] = str(error)
                result = {"company_id": config["company"]["id"], "checks": checks}
            else:
                if args.message is None and not args.stdin:
                    parser.error("analyse requires --message or --stdin")
                limit = config["runtime"]["max_message_characters"]
                message = sys.stdin.read(limit + 1) if args.stdin else args.message
                request = SupportRequest(
                    company_id=config["company"]["id"], message=message
                )
                result = create_agent(config).analyse(request).model_dump()
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, RuntimeError, csv.Error, sqlite3.Error) as error:
        print(f"Support workflow failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
