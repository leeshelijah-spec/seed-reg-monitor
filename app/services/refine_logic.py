from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings
from ..database import get_connection, row_to_news_article
from .news_analysis import NewsAnalysisService
from .news_ingestion import NewsIngestionService
from .news_utils import dumps_json, now_iso


NOISE_STATUS = "잡음"


@dataclass
class RefineApplySummary:
    target_date: str
    signal_count: int
    scanned_count: int
    updated_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date,
            "signal_count": self.signal_count,
            "scanned_count": self.scanned_count,
            "updated_count": self.updated_count,
        }


class RefineLogicService:
    def __init__(self) -> None:
        self.analysis = NewsAnalysisService()
        self.ingestion = NewsIngestionService()

    def run(self, *, target_date: str | None = None, run_sync: bool = True) -> dict[str, Any]:
        target = target_date or self._today()
        first_apply = self._apply_today_noise_feedback(target)
        sync_result = self._run_news_sync_once() if run_sync else {"status": "skipped", "reason": "sync_disabled"}
        second_apply = self._apply_today_noise_feedback(target)
        return {
            "target_date": target,
            "before_sync": first_apply.to_dict(),
            "sync": sync_result,
            "after_sync": second_apply.to_dict(),
        }

    def _today(self) -> str:
        return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

    def _collect_noise_signals(self, target_date: str) -> tuple[dict[str, str | None], dict[tuple[str, str], str | None]]:
        link_comments: dict[str, str | None] = {}
        title_comments: dict[tuple[str, str], str | None] = {}
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    na.keyword,
                    na.title,
                    na.original_link,
                    na.naver_link,
                    nf.comment
                FROM news_feedback nf
                JOIN news_articles na ON na.id = nf.article_id
                WHERE nf.is_noise = 1
                  AND substr(nf.created_at, 1, 10) = ?
                ORDER BY nf.created_at DESC, nf.id DESC
                """,
                (target_date,),
            ).fetchall()

        for row in rows:
            comment = row["comment"]
            original_link = (row["original_link"] or "").strip()
            naver_link = (row["naver_link"] or "").strip()
            if original_link and original_link not in link_comments:
                link_comments[original_link] = comment
            if naver_link and naver_link not in link_comments:
                link_comments[naver_link] = comment

            key = ((row["keyword"] or "").strip(), (row["title"] or "").strip())
            if key[0] and key[1] and key not in title_comments:
                title_comments[key] = comment

        return link_comments, title_comments

    def _apply_today_noise_feedback(self, target_date: str) -> RefineApplySummary:
        link_comments, title_comments = self._collect_noise_signals(target_date)
        if not link_comments and not title_comments:
            return RefineApplySummary(
                target_date=target_date,
                signal_count=0,
                scanned_count=0,
                updated_count=0,
            )

        execution_ts = now_iso()
        scanned_count = 0
        updated_count = 0
        signal_count = len(link_comments) + len(title_comments)

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) = ?
                """,
                (target_date,),
            ).fetchall()

            for row in rows:
                item = row_to_news_article(row)
                if not item:
                    continue
                scanned_count += 1
                article_id = item["id"]
                original_link = (item.get("original_link") or "").strip()
                naver_link = (item.get("naver_link") or "").strip()
                title_key = ((item.get("keyword") or "").strip(), (item.get("title") or "").strip())

                comment = link_comments.get(original_link)
                matched_by = "original_link"
                if comment is None and naver_link:
                    comment = link_comments.get(naver_link)
                    matched_by = "naver_link"
                if comment is None and title_key in title_comments:
                    comment = title_comments[title_key]
                    matched_by = "keyword_title"
                if comment is None and not (
                    original_link in link_comments or naver_link in link_comments or title_key in title_comments
                ):
                    continue

                impact_level = item.get("business_impact_level") or "참고"
                urgency_level = item.get("urgency_level") or "low"
                updated_recommended_action = self.analysis.apply_feedback_to_action(
                    base_action=item.get("recommended_action") or "",
                    review_status=NOISE_STATUS,
                    owner_department=item.get("owner_department") or "경영기획",
                    impact_level=impact_level,
                    urgency_level=urgency_level,
                    comment=comment,
                )

                trace = item.get("analysis_trace") or {}
                existing_refine_trace = trace.get("refinelogic", {})
                trace["refinelogic"] = {
                    "applied": True,
                    "applied_at": execution_ts,
                    "source": "today_noise_feedback",
                    "matched_by": matched_by,
                }

                if (
                    item.get("review_status") == NOISE_STATUS
                    and item.get("recommended_action") == updated_recommended_action
                    and existing_refine_trace.get("source") == "today_noise_feedback"
                ):
                    continue

                connection.execute(
                    """
                    UPDATE news_articles
                    SET review_status = ?,
                        recommended_action = ?,
                        analysis_trace = ?
                    WHERE id = ?
                    """,
                    (
                        NOISE_STATUS,
                        updated_recommended_action,
                        dumps_json(trace),
                        article_id,
                    ),
                )
                updated_count += 1

        return RefineApplySummary(
            target_date=target_date,
            signal_count=signal_count,
            scanned_count=scanned_count,
            updated_count=updated_count,
        )

    def _run_news_sync_once(self) -> dict[str, Any]:
        if not self.ingestion.is_configured():
            return {
                "status": "skipped",
                "reason": "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET are not configured",
            }
        return self.ingestion.run(run_type="manual")
