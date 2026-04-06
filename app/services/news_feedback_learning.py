from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..database import get_connection


UNREVIEWED_STATUS = "\ubbf8\uac80\ud1a0"
RELEVANT_STATUS = "\uad00\ub828"
NOISE_STATUS = "\uc7a1\uc74c"


@dataclass
class FeedbackReuseResult:
    review_status: str | None
    impact_level: str | None
    urgency_level: str | None
    is_relevant: bool
    is_noise: bool
    match_count: int
    latest_feedback_id: int | None
    latest_feedback_at: str | None
    conflict: bool

    def to_trace(self) -> dict[str, Any]:
        return {
            "applied": self.review_status is not None,
            "review_status": self.review_status,
            "impact_level": self.impact_level,
            "urgency_level": self.urgency_level,
            "is_relevant": self.is_relevant,
            "is_noise": self.is_noise,
            "match_count": self.match_count,
            "latest_feedback_id": self.latest_feedback_id,
            "latest_feedback_at": self.latest_feedback_at,
            "conflict": self.conflict,
        }


class NewsFeedbackLearningService:
    def reuse_feedback(self, *, keyword: str, title: str) -> FeedbackReuseResult:
        if not keyword or not title:
            return FeedbackReuseResult(
                review_status=None,
                impact_level=None,
                urgency_level=None,
                is_relevant=False,
                is_noise=False,
                match_count=0,
                latest_feedback_id=None,
                latest_feedback_at=None,
                conflict=False,
            )

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    nf.id,
                    nf.feedback_type,
                    nf.is_relevant,
                    nf.is_noise,
                    nf.impact_level,
                    nf.urgency_level,
                    nf.created_at
                FROM news_feedback nf
                JOIN news_articles na ON na.id = nf.article_id
                WHERE na.keyword = ?
                  AND na.title = ?
                ORDER BY nf.created_at DESC, nf.id DESC
                """,
                (keyword, title),
            ).fetchall()

        if not rows:
            return FeedbackReuseResult(
                review_status=None,
                impact_level=None,
                urgency_level=None,
                is_relevant=False,
                is_noise=False,
                match_count=0,
                latest_feedback_id=None,
                latest_feedback_at=None,
                conflict=False,
            )

        latest = rows[0]
        distinct_types = {
            (
                row["feedback_type"],
                row["impact_level"],
                row["urgency_level"],
                int(row["is_relevant"] or 0),
                int(row["is_noise"] or 0),
            )
            for row in rows
        }
        review_status = self._derive_review_status(
            is_relevant=bool(latest["is_relevant"]),
            is_noise=bool(latest["is_noise"]),
            feedback_type=latest["feedback_type"],
        )
        return FeedbackReuseResult(
            review_status=review_status,
            impact_level=latest["impact_level"],
            urgency_level=latest["urgency_level"],
            is_relevant=bool(latest["is_relevant"]),
            is_noise=bool(latest["is_noise"]),
            match_count=len(rows),
            latest_feedback_id=int(latest["id"]),
            latest_feedback_at=latest["created_at"],
            conflict=len(distinct_types) > 1,
        )

    def reuse_review_status(self, *, keyword: str, title: str) -> FeedbackReuseResult:
        return self.reuse_feedback(keyword=keyword, title=title)

    def _derive_review_status(self, *, is_relevant: bool, is_noise: bool, feedback_type: str | None) -> str | None:
        if is_noise:
            return NOISE_STATUS
        if is_relevant:
            return RELEVANT_STATUS
        return feedback_type or None
