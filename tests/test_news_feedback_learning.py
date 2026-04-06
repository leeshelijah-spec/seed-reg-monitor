from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from app.services.news_analysis import NewsAnalysisResult
from app.services.news_feedback_learning import NewsFeedbackLearningService
from app.services.news_ingestion import NewsIngestionService


def _build_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            review_status TEXT NOT NULL DEFAULT '미검토'
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


class NewsFeedbackLearningServiceTest(unittest.TestCase):
    def test_reuses_latest_structured_feedback(self) -> None:
        connection = _build_connection()
        connection.execute(
            "INSERT INTO news_articles (id, keyword, title, review_status) VALUES (1, ?, ?, ?)",
            ("토마토", "뉴스 토마토, 멤버십 가입 지시 논란", "잡음"),
        )
        connection.execute(
            """
            INSERT INTO news_feedback (
                article_id, feedback_type, is_relevant, is_noise, impact_level, urgency_level, comment, created_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("관련", 1, 0, "중요", "high", "주간 보고 반영", "2026-04-06T12:00:00+09:00"),
        )

        service = NewsFeedbackLearningService()
        with patch("app.services.news_feedback_learning.get_connection", lambda: _shared_connection(connection)):
            result = service.reuse_feedback(keyword="토마토", title="뉴스 토마토, 멤버십 가입 지시 논란")

        self.assertEqual(result.review_status, "관련")
        self.assertEqual(result.impact_level, "중요")
        self.assertEqual(result.urgency_level, "high")
        self.assertEqual(result.comment, "주간 보고 반영")
        self.assertTrue(result.is_relevant)
        self.assertFalse(result.is_noise)
        self.assertEqual(result.match_count, 1)

    def test_returns_none_when_no_feedback_exists(self) -> None:
        connection = _build_connection()
        service = NewsFeedbackLearningService()

        with patch("app.services.news_feedback_learning.get_connection", lambda: _shared_connection(connection)):
            result = service.reuse_feedback(keyword="토마토", title="일반 기사")

        self.assertIsNone(result.review_status)
        self.assertEqual(result.match_count, 0)
        self.assertFalse(result.conflict)


class NewsIngestionFeedbackIntegrationTest(unittest.TestCase):
    def test_normalize_article_applies_learned_review_status(self) -> None:
        service = NewsIngestionService()

        class StubAnalyzer:
            def analyze(self, article: dict, matched_keywords: list[str]) -> NewsAnalysisResult:
                return NewsAnalysisResult(
                    topic_category="시장수급",
                    business_impact_level="참고",
                    urgency_level="low",
                    relevance_score=42,
                    recommended_action="follow up",
                    owner_department="경영기획",
                    review_status="미검토",
                    analysis_trace={"rule_hits": {"matched_keywords": matched_keywords}},
                )

        class StubFeedbackLearning:
            def reuse_feedback(self, *, keyword: str, title: str):
                class Result:
                    review_status = "관련"
                    impact_level = "중요"
                    urgency_level = "high"
                    comment = "주간 보고 반영"

                    @staticmethod
                    def to_trace() -> dict[str, object]:
                        return {
                            "applied": True,
                            "review_status": "관련",
                            "impact_level": "중요",
                            "urgency_level": "high",
                            "comment": "주간 보고 반영",
                            "match_count": 1,
                        }

                return Result()

        service.analyzer = StubAnalyzer()
        service.feedback_learning = StubFeedbackLearning()
        article = service._normalize_article(
            "토마토",
            {
                "title": "뉴스 토마토, 멤버십 가입 지시 논란",
                "description": "무관한 기사",
                "originallink": "https://example.com/article",
                "link": "https://search.naver.com/article",
                "pubDate": "Wed, 02 Apr 2026 09:00:00 +0900",
            },
        )

        self.assertEqual(article["review_status"], "관련")
        self.assertEqual(article["business_impact_level"], "중요")
        self.assertEqual(article["urgency_level"], "high")
        self.assertEqual(article["analysis_trace"]["feedback_learning"]["review_status"], "관련")
        self.assertIn("피드백 조치사항: 주간 보고 반영", article["recommended_action"])


if __name__ == "__main__":
    unittest.main()
