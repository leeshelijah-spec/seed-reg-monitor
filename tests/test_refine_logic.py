from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from app.services.refine_logic import RefineLogicService


def _build_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            source_title TEXT,
            summary TEXT,
            naver_link TEXT NOT NULL DEFAULT '',
            original_link TEXT NOT NULL DEFAULT '',
            published_at TEXT,
            collected_at TEXT NOT NULL,
            duplicate_hash TEXT,
            raw_json TEXT,
            topic_category TEXT,
            business_impact_level TEXT,
            urgency_level TEXT,
            relevance_score INTEGER NOT NULL DEFAULT 0,
            recommended_action TEXT NOT NULL DEFAULT '',
            owner_department TEXT,
            review_status TEXT NOT NULL DEFAULT '미검토',
            matched_keywords TEXT NOT NULL DEFAULT '[]',
            analysis_trace TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE news_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            is_relevant INTEGER NOT NULL DEFAULT 0,
            is_noise INTEGER NOT NULL DEFAULT 0,
            impact_level TEXT,
            urgency_level TEXT,
            comment TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    return connection


@contextmanager
def _shared_connection(connection: sqlite3.Connection):
    try:
        yield connection
        connection.commit()
    finally:
        pass


class RefineLogicServiceTest(unittest.TestCase):
    def test_applies_today_noise_feedback_to_today_articles(self) -> None:
        connection = _build_connection()
        target_date = "2026-04-09"
        today_ts = "2026-04-09T10:00:00+09:00"

        connection.execute(
            """
            INSERT INTO news_articles (
                id, keyword, title, naver_link, original_link, collected_at,
                business_impact_level, urgency_level, recommended_action, owner_department, review_status
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "토마토",
                "토마토 구단 개막전 승리",
                "https://search.naver.com/article?id=100",
                "https://example.com/article?id=100",
                today_ts,
                "참고",
                "low",
                "기존 권장 문구",
                "경영기획",
                "잡음",
            ),
        )
        connection.execute(
            """
            INSERT INTO news_articles (
                id, keyword, title, naver_link, original_link, collected_at,
                business_impact_level, urgency_level, recommended_action, owner_department, review_status
            ) VALUES (2, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "오이",
                "다른 키워드 제목이지만 같은 링크",
                "https://search.naver.com/article?id=100",
                "https://example.com/article?id=100",
                today_ts,
                "참고",
                "low",
                "기존 권장 문구",
                "경영기획",
                "미검토",
            ),
        )
        connection.execute(
            """
            INSERT INTO news_feedback (
                article_id, feedback_type, is_relevant, is_noise, impact_level, urgency_level, comment, created_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("잡음", 0, 1, None, None, "오늘 잡음 확정", f"{target_date}T11:20:00+09:00"),
        )

        service = RefineLogicService()
        with patch("app.services.refine_logic.get_connection", lambda: _shared_connection(connection)):
            result = service.run(target_date=target_date, run_sync=False)

        updated = connection.execute("SELECT review_status, recommended_action FROM news_articles WHERE id = 2").fetchone()
        self.assertEqual(updated["review_status"], "잡음")
        self.assertIn("잡음으로 분류된 기사입니다.", updated["recommended_action"])
        self.assertEqual(result["sync"]["status"], "skipped")
        self.assertGreaterEqual(result["before_sync"]["updated_count"], 1)


if __name__ == "__main__":
    unittest.main()
