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
        _ensure_column(
            connection,
            table_name="news_feedback",
            column_name="is_relevant",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            table_name="news_feedback",
            column_name="is_noise",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            table_name="news_feedback",
            column_name="impact_level",
            definition="TEXT",
        )
        _ensure_column(
            connection,
            table_name="news_feedback",
            column_name="urgency_level",
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
        connection.execute(
            """
            UPDATE news_feedback
            SET is_noise = 1
            WHERE feedback_type = ?
              AND is_noise = 0
            """,
            ("\uc7a1\uc74c",),
        )
        connection.execute(
            """
            UPDATE news_feedback
            SET is_relevant = 1
            WHERE feedback_type = ?
              AND is_relevant = 0
            """,
            ("\uc911\uc694",),
        )
        connection.execute(
            """
            UPDATE news_feedback
            SET impact_level = COALESCE(impact_level, ?),
                urgency_level = COALESCE(urgency_level, ?)
            WHERE feedback_type = ?
              AND is_relevant = 1
            """,
            ("\uc911\uc694", "high", "\uc911\uc694"),
        )
    from .services.news_keywords import NewsKeywordService

    NewsKeywordService().ensure_seed_data()


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


def row_to_news_article(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["matched_keywords"] = json.loads(item.get("matched_keywords") or "[]")
    item["analysis_trace"] = json.loads(item.get("analysis_trace") or "{}")
    return item
