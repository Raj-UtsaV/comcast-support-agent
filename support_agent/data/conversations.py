"""Read source CSV chunks and reconstruct company conversations on disk."""

import csv
import hashlib
import json
import sqlite3
import sys
from itertools import islice
from pathlib import Path

from support_agent.shared.config import ConfigError


def index_twitter_csv(connection: sqlite3.Connection, config: dict) -> dict:
    """Stage source rows and graph edges on disk, using bounded CSV chunks."""

    settings = config["dataset"]
    columns = settings["columns"]
    required = {
        "message_id",
        "author_id",
        "role",
        "timestamp",
        "text",
        "parent_message_id",
        "reply_message_ids",
    }

    if set(columns) != required or len(set(columns.values())) != len(required):
        raise ConfigError("The Twitter adapter requires seven distinct mapped columns.")

    role_values = settings["role_values"]

    if (
        set(role_values) != {"customer", "agent"}
        or any(not isinstance(value, str) for value in role_values.values())
        or len(set(role_values.values())) != 2
    ):
        raise ConfigError(
            "role_values must map customer and agent to distinct source strings."
        )

    roles = {value: role for role, value in role_values.items()}
    accounts = set(settings["company_author_ids"])
    separator = settings["reply_id_separator"]

    if not isinstance(separator, str) or not separator:
        raise ConfigError("reply_id_separator must be a nonempty string.")

    connection.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        CREATE TABLE messages (
            id TEXT PRIMARY KEY, parent TEXT, timestamp TEXT, role TEXT,
            text TEXT, signature BLOB, conflict INTEGER DEFAULT 0
        );
        CREATE TABLE links (a TEXT, b TEXT, PRIMARY KEY (a,b)) WITHOUT ROWID;
    """)
    total = 0

    with Path(config["paths"]["raw_csv"]).open(
        encoding=settings["csv"]["encoding"],
        newline="",
    ) as stream:
        reader = csv.DictReader(stream, strict=True)

        if not reader.fieldnames or not set(columns.values()).issubset(
            reader.fieldnames
        ):
            raise ValueError("The source CSV is missing configured columns.")

        while chunk := list(islice(reader, settings["csv"]["chunk_size"])):
            messages, links = [], []

            for row in chunk:
                total += 1

                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed CSV record {total}.")

                source = {key: row[column] for key, column in columns.items()}
                message_id = source["message_id"].strip()

                if not message_id or source["role"] not in roles:
                    raise ValueError(
                        f"Invalid message ID or role at CSV record {total}."
                    )

                role = roles[source["role"]]

                if source["author_id"] in accounts and role != "agent":
                    raise ValueError(
                        f"A configured support account has a customer role at record {total}."
                    )

                if role == "agent" and source["author_id"] not in accounts:
                    role = "excluded"

                signature = hashlib.sha256(
                    json.dumps(source, sort_keys=True).encode()
                ).digest()
                parent = source["parent_message_id"].strip() or None
                messages.append(
                    (
                        message_id,
                        parent,
                        source["timestamp"],
                        role,
                        source["text"] if role != "excluded" else "",
                        signature,
                    )
                )

                if role != "excluded":
                    neighbors = source["reply_message_ids"].split(separator)

                    if parent:
                        neighbors.append(parent)

                    for neighbor in neighbors:
                        neighbor = neighbor.strip()

                        if neighbor and neighbor != message_id:
                            links.append(tuple(sorted((message_id, neighbor))))

            with connection:
                connection.executemany(
                    """
                    INSERT INTO messages (id,parent,timestamp,role,text,signature) VALUES (?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                    conflict = messages.conflict OR messages.signature != excluded.signature
                """,
                    messages,
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO links VALUES (?,?)", links
                )

            print(f"Indexed {total:,} source records", file=sys.stderr, flush=True)

    if connection.execute("SELECT 1 FROM messages WHERE conflict=1 LIMIT 1").fetchone():
        raise ValueError(
            "Conflicting rows share a message ID; fix source duplicates before preparing data."
        )

    connection.execute("CREATE INDEX links_b ON links(b)")
    unique = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    return {"source_records": total, "duplicate_records_removed": total - unique}


ADAPTERS = {"twitter_csv": index_twitter_csv}


def company_groups(connection: sqlite3.Connection) -> tuple[dict, dict]:
    # Missing referenced IDs can join orphan siblings; known other-company
    # agents are blocked, so their replies never become bridges or evidence.
    connection.executescript("""
        CREATE TABLE selected (id TEXT PRIMARY KEY);
        INSERT INTO selected
        WITH RECURSIVE reachable(id) AS (
            SELECT id FROM messages WHERE role='agent'
            UNION
            SELECT CASE WHEN links.a=reachable.id THEN links.b ELSE links.a END
            FROM reachable JOIN links ON links.a=reachable.id OR links.b=reachable.id
            LEFT JOIN messages ON messages.id =
                CASE WHEN links.a=reachable.id THEN links.b ELSE links.a END
            WHERE messages.role IS NULL OR messages.role!='excluded'
        ) SELECT id FROM reachable;
    """)
    parents = {row[0]: row[0] for row in connection.execute("SELECT id FROM selected")}

    if not parents:
        raise ValueError("No replies from the configured company accounts were found.")

    def find(item):
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]

        return item

    for a, b in connection.execute("""
        SELECT links.a, links.b FROM links
        JOIN selected a ON a.id=links.a JOIN selected b ON b.id=links.b
    """):
        left, right = find(a), find(b)

        if left != right:
            parents[max(left, right)] = min(left, right)

    groups = {item: find(item) for item in parents}
    records = {
        row[0]: {
            "message_id": row[0],
            "parent_message_id": row[1],
            "timestamp": row[2],
            "role": row[3],
            "text": row[4],
            "parent_missing_from_source": bool(row[1] and row[5] is None),
            "parent_from_other_company": row[6] == "excluded",
        }
        for row in connection.execute("""
            SELECT m.id,m.parent,m.timestamp,m.role,m.text,p.id,p.role
            FROM messages m JOIN selected s ON s.id=m.id
            LEFT JOIN messages p ON p.id=m.parent WHERE m.role!='excluded'
        """)
    }

    return groups, records
