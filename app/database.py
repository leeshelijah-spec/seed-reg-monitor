from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import settings


def _connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with get_connection() as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _ensure_column(
            connection,
            table_name="regulations",
            column_name="amendment_reason",
            definition="TEXT",
        )
        connection.execute(
            """
            UPDATE regulations
            SET amendment_reason = summary
            WHERE amendment_reason IS NULL
              AND summary IS NOT NULL
            """
        )


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in columns:
        return
    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
    )


def row_to_regulation(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["category"] = json.loads(item.get("category") or "[]")
    item["department"] = json.loads(item.get("department") or "[]")
    return item
