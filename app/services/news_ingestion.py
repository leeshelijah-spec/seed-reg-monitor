from __future__ import annotations

from typing import Any

from ..database import get_connection, row_to_news_article
from .news_feedback_learning import NewsFeedbackLearningService, UNREVIEWED_STATUS
from .naver_news import NaverNewsClient
from .news_analysis import NewsAnalysisService
from .news_keywords import NewsKeywordService
from .news_utils import (
    build_duplicate_hash,
    dumps_json,
    extract_source_title,
    normalize_link,
    now_iso,
    parse_naver_pub_date,
    strip_html_markup,
)


class NewsIngestionService:
    def __init__(self) -> None:
        self.client = NaverNewsClient()
        self.keyword_service = NewsKeywordService()
        self.analyzer = NewsAnalysisService()
        self.feedback_learning = NewsFeedbackLearningService()

    def is_configured(self) -> bool:
        return self.client.is_configured()

    def run(self, run_type: str = "manual", display: int | None = None) -> dict[str, Any]:
        keywords = self.keyword_service.list_active_keywords()
        summary = {
            "status": "success",
            "keyword_count": len(keywords),
            "fetched_count": 0,
            "inserted_count": 0,
            "duplicate_count": 0,
            "errors": [],
        }
        for keyword_row in keywords:
            keyword = keyword_row["keyword"]
            started_at = now_iso()
            log_id = self._start_log(keyword, run_type, started_at)
            try:
                payload = self.client.search_news(keyword=keyword, display=display)
                items = payload.get("items", [])
                inserted_count, duplicate_count = self.ingest_items(keyword=keyword, items=items)
                summary["fetched_count"] += len(items)
                summary["inserted_count"] += inserted_count
                summary["duplicate_count"] += duplicate_count
                self._finish_log(
                    log_id=log_id,
                    status="success",
                    fetched_count=len(items),
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    retry_count=payload.get("_meta", {}).get("retry_count", 0),
                    http_status=payload.get("_meta", {}).get("http_status"),
                    message="ok",
                )
            except Exception as exc:  # noqa: BLE001
                summary["status"] = "partial_failure"
                summary["errors"].append({"keyword": keyword, "message": str(exc)})
                self._finish_log(
                    log_id=log_id,
                    status="failed",
                    fetched_count=0,
                    inserted_count=0,
                    duplicate_count=0,
                    retry_count=0,
                    http_status=None,
                    message=str(exc),
                )
        return summary

    def ingest_items(self, keyword: str, items: list[dict[str, Any]]) -> tuple[int, int]:
        inserted_count = 0
        duplicate_count = 0
        for item in items:
            normalized = self._normalize_article(keyword, item)
            result = self._upsert_article(normalized)
            if result == "inserted":
                inserted_count += 1
            else:
                duplicate_count += 1
        return inserted_count, duplicate_count

    def _normalize_article(self, keyword: str, item: dict[str, Any]) -> dict[str, Any]:
        title = strip_html_markup(item.get("title"))
        summary = strip_html_markup(item.get("description"))
        original_link = normalize_link(item.get("originallink") or item.get("link"))
        naver_link = normalize_link(item.get("link"))
        published_at = parse_naver_pub_date(item.get("pubDate"))
        matched_keywords = [keyword]
        analysis = self.analyzer.analyze(
            {"title": title, "summary": summary, "published_at": published_at},
            matched_keywords=matched_keywords,
        )
        feedback_reuse = self.feedback_learning.reuse_feedback(keyword=keyword, title=title)
        impact_level = feedback_reuse.impact_level or analysis.business_impact_level
        urgency_level = feedback_reuse.urgency_level or analysis.urgency_level
        review_status = feedback_reuse.review_status or analysis.review_status
        action_updater = getattr(self.analyzer, "apply_feedback_to_action", None)
        if not callable(action_updater):
            action_updater = NewsAnalysisService().apply_feedback_to_action
        recommended_action = action_updater(
            base_action=analysis.recommended_action,
            review_status=review_status,
            owner_department=analysis.owner_department,
            impact_level=impact_level,
            urgency_level=urgency_level,
            comment=feedback_reuse.comment,
        )
        analysis_trace = {
            **analysis.analysis_trace,
            "feedback_learning": feedback_reuse.to_trace(),
        }
        return {
            "keyword": keyword,
            "source_title": extract_source_title(original_link),
            "title": title,
            "summary": summary,
            "naver_link": naver_link,
            "original_link": original_link or naver_link,
            "published_at": published_at,
            "collected_at": now_iso(),
            "duplicate_hash": build_duplicate_hash(original_link or naver_link, title=title),
            "raw_json": dumps_json(item),
            "topic_category": analysis.topic_category,
            "business_impact_level": impact_level,
            "urgency_level": urgency_level,
            "relevance_score": analysis.relevance_score,
            "recommended_action": recommended_action,
            "owner_department": analysis.owner_department,
            "review_status": review_status,
            "matched_keywords": matched_keywords,
            "analysis_trace": analysis_trace,
        }

    def _upsert_article(self, article: dict[str, Any]) -> str:
        with get_connection() as connection:
            existing_row = connection.execute(
                "SELECT * FROM news_articles WHERE duplicate_hash = ?",
                (article["duplicate_hash"],),
            ).fetchone()
            if existing_row:
                existing = row_to_news_article(existing_row) or {}
                merged_keywords = sorted(set(existing.get("matched_keywords", [])) | set(article["matched_keywords"]))
                merged_analysis = self.analyzer.analyze(
                    {
                        "title": existing.get("title") or article["title"],
                        "summary": existing.get("summary") or article["summary"],
                        "published_at": existing.get("published_at") or article["published_at"],
                    },
                    matched_keywords=merged_keywords,
                )
                updated_review_status = existing.get("review_status") or article["review_status"]
                if updated_review_status == UNREVIEWED_STATUS and article["review_status"] != UNREVIEWED_STATUS:
                    updated_review_status = article["review_status"]
                updated_impact_level = article["business_impact_level"]
                updated_urgency_level = article["urgency_level"]
                if updated_review_status == UNREVIEWED_STATUS:
                    updated_impact_level = merged_analysis.business_impact_level
                    updated_urgency_level = merged_analysis.urgency_level

                connection.execute(
                    """
                    UPDATE news_articles
                    SET keyword = ?,
                        source_title = ?,
                        summary = ?,
                        naver_link = ?,
                        collected_at = ?,
                        topic_category = ?,
                        business_impact_level = ?,
                        urgency_level = ?,
                        relevance_score = ?,
                        recommended_action = ?,
                        owner_department = ?,
                        review_status = ?,
                        matched_keywords = ?,
                        analysis_trace = ?
                    WHERE id = ?
                    """,
                    (
                        article["keyword"],
                        article["source_title"] or existing.get("source_title"),
                        article["summary"] or existing.get("summary"),
                        article["naver_link"] or existing.get("naver_link"),
                        article["collected_at"],
                        merged_analysis.topic_category,
                        updated_impact_level,
                        updated_urgency_level,
                        merged_analysis.relevance_score,
                        merged_analysis.recommended_action,
                        merged_analysis.owner_department,
                        updated_review_status,
                        dumps_json(merged_keywords),
                        dumps_json(
                            {
                                **merged_analysis.analysis_trace,
                                "feedback_learning": article["analysis_trace"].get("feedback_learning", {}),
                            }
                        ),
                        existing["id"],
                    ),
                )
                return "duplicate"

            connection.execute(
                """
                INSERT INTO news_articles (
                    keyword, source_title, title, summary, naver_link, original_link, published_at,
                    collected_at, duplicate_hash, raw_json, topic_category, business_impact_level,
                    urgency_level, relevance_score, recommended_action, owner_department, review_status,
                    matched_keywords, analysis_trace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["keyword"],
                    article["source_title"],
                    article["title"],
                    article["summary"],
                    article["naver_link"],
                    article["original_link"],
                    article["published_at"],
                    article["collected_at"],
                    article["duplicate_hash"],
                    article["raw_json"],
                    article["topic_category"],
                    article["business_impact_level"],
                    article["urgency_level"],
                    article["relevance_score"],
                    article["recommended_action"],
                    article["owner_department"],
                    article["review_status"],
                    dumps_json(article["matched_keywords"]),
                    dumps_json(article["analysis_trace"]),
                ),
            )
        return "inserted"

    def _start_log(self, keyword: str, run_type: str, started_at: str) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO news_collection_logs (keyword, run_type, status, started_at)
                VALUES (?, ?, 'running', ?)
                """,
                (keyword, run_type, started_at),
            )
            return int(cursor.lastrowid)

    def _finish_log(
        self,
        log_id: int,
        status: str,
        fetched_count: int,
        inserted_count: int,
        duplicate_count: int,
        retry_count: int,
        http_status: int | None,
        message: str,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE news_collection_logs
                SET status = ?,
                    finished_at = ?,
                    fetched_count = ?,
                    inserted_count = ?,
                    duplicate_count = ?,
                    retry_count = ?,
                    http_status = ?,
                    message = ?
                WHERE id = ?
                """,
                (
                    status,
                    now_iso(),
                    fetched_count,
                    inserted_count,
                    duplicate_count,
                    retry_count,
                    http_status,
                    message,
                    log_id,
                ),
            )
