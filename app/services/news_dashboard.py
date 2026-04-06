from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

from ..database import get_connection, row_to_news_article


UNREVIEWED = "\ubbf8\uac80\ud1a0"
IMPORTANT = "\uc911\uc694"
IMMEDIATE = "\uc989\uc2dc\uc870\uce58"
NEEDS_REVIEW = "\uac80\ud1a0\ud544\uc694"
REFERENCE = "\ucc38\uace0"
NOISE = "\uc7a1\uc74c"
CLASSIFICATION_ERROR = "\ubd84\ub958\uc624\ub958"

TITLE_TOKEN_RE = re.compile(r"[0-9A-Za-z\uac00-\ud7a3]+")
NEWS_TITLE_STOPWORDS = {
    "\uae30\uc0ac",
    "\ub2e8\ub3c5",
    "\uc18d\ubcf4",
    "\uc885\ud569",
    "\uc778\ud130\ubdf0",
    "\ud604\uc7a5",
    "\uc624\ub298",
    "\uc774\ubc88",
    "\uad00\ub828",
    "\ub17c\ub780",
    "\uae30\uc790",
    "\ub274\uc2a4",
    "\ub124\uc774\ubc84",
}
IMPACT_PRIORITY = {IMMEDIATE: 4, IMPORTANT: 3, NEEDS_REVIEW: 2, REFERENCE: 1}
URGENCY_PRIORITY = {"high": 3, "medium": 2, "low": 1}
REVIEW_PRIORITY = {CLASSIFICATION_ERROR: 3, IMPORTANT: 2, NOISE: 1, UNREVIEWED: 0}


@dataclass
class NewsFilterParams:
    start_date: str | None = None
    end_date: str | None = None
    keyword: str | None = None
    topic_category: str | None = None
    business_impact_level: str | None = None
    owner_department: str | None = None
    show_all_articles: bool = False


class NewsDashboardService:
    def load_dashboard(self, filters: NewsFilterParams) -> dict[str, Any]:
        articles = self._load_articles(filters)
        return {
            "filters": self._serialize_filters(filters),
            "filter_options": self._load_filter_options(),
            "kpis": self._load_kpis(),
            "articles": articles,
            "article_groups": self._group_articles(articles),
            "trend": self._load_trend_data(filters),
            "executive_summary": self._build_executive_summary(filters),
            "operations": self._load_operations(),
        }

    def _serialize_filters(self, filters: NewsFilterParams) -> dict[str, str]:
        return {
            "start_date": filters.start_date or "",
            "end_date": filters.end_date or "",
            "keyword": filters.keyword or "",
            "topic_category": filters.topic_category or "",
            "business_impact_level": filters.business_impact_level or "",
            "owner_department": filters.owner_department or "",
            "show_all_articles": "1" if filters.show_all_articles else "",
        }

    def _where_clause(
        self,
        filters: NewsFilterParams,
        apply_review_filter: bool = True,
    ) -> tuple[str, list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []

        if filters.start_date:
            conditions.append("substr(COALESCE(published_at, collected_at), 1, 10) >= ?")
            params.append(filters.start_date)
        if filters.end_date:
            conditions.append("substr(COALESCE(published_at, collected_at), 1, 10) <= ?")
            params.append(filters.end_date)
        if filters.keyword:
            conditions.append("keyword = ?")
            params.append(filters.keyword)
        if filters.topic_category:
            conditions.append("topic_category = ?")
            params.append(filters.topic_category)
        if filters.business_impact_level:
            conditions.append("business_impact_level = ?")
            params.append(filters.business_impact_level)
        if filters.owner_department:
            conditions.append("owner_department = ?")
            params.append(filters.owner_department)
        if apply_review_filter and not filters.show_all_articles:
            conditions.append("review_status = ?")
            params.append(UNREVIEWED)

        if not conditions:
            return "", params
        return "WHERE " + " AND ".join(conditions), params

    def _load_filter_options(self) -> dict[str, list[str]]:
        with get_connection() as connection:
            keywords = [
                row[0]
                for row in connection.execute(
                    "SELECT keyword FROM news_keywords WHERE is_active = 1 ORDER BY keyword_group, keyword"
                )
            ]
            topic_categories = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT topic_category FROM news_articles ORDER BY topic_category"
                )
            ]
            impact_levels = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT business_impact_level FROM news_articles ORDER BY business_impact_level"
                )
            ]
            owner_departments = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT owner_department FROM news_articles ORDER BY owner_department"
                )
            ]
        return {
            "keywords": keywords,
            "topic_categories": topic_categories,
            "business_impact_levels": impact_levels,
            "owner_departments": owner_departments,
        }

    def _load_kpis(self) -> dict[str, Any]:
        seven_days_ago = (date.today() - timedelta(days=6)).isoformat()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS recent_count,
                    SUM(CASE WHEN business_impact_level IN (?, ?) THEN 1 ELSE 0 END) AS important_count,
                    SUM(CASE WHEN business_impact_level = ? THEN 1 ELSE 0 END) AS urgent_count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?
                """,
                (IMPORTANT, IMMEDIATE, IMMEDIATE, seven_days_ago),
            ).fetchone()
            top_topic_row = connection.execute(
                """
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                LIMIT 1
                """,
                (seven_days_ago,),
            ).fetchone()
        return {
            "recent_count": row["recent_count"] or 0,
            "important_count": row["important_count"] or 0,
            "urgent_count": row["urgent_count"] or 0,
            "top_topic": top_topic_row["topic_category"] if top_topic_row else "-",
        }

    def _load_articles(self, filters: NewsFilterParams) -> list[dict[str, Any]]:
        where_clause, params = self._where_clause(filters, apply_review_filter=True)
        sql = f"""
            SELECT *
            FROM news_articles
            {where_clause}
            ORDER BY COALESCE(published_at, collected_at) DESC, relevance_score DESC
            LIMIT 40
        """
        with get_connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        articles: list[dict[str, Any]] = []
        for row in rows:
            item = row_to_news_article(row)
            if item:
                articles.append(item)
        return articles

    def _group_articles(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clusters: list[list[dict[str, Any]]] = []

        for article in articles:
            matched_cluster: list[dict[str, Any]] | None = None
            for cluster in clusters:
                if any(self._are_related_articles(article, existing) for existing in cluster):
                    matched_cluster = cluster
                    break
            if matched_cluster is None:
                clusters.append([article])
            else:
                matched_cluster.append(article)

        groups = [self._build_article_group(index, cluster) for index, cluster in enumerate(clusters, start=1)]
        groups.sort(
            key=lambda group: (
                group["latest_published_at"] or "",
                group["max_relevance_score"],
                group["total_count"],
            ),
            reverse=True,
        )
        return groups

    def _build_article_group(self, index: int, articles: list[dict[str, Any]]) -> dict[str, Any]:
        sorted_articles = sorted(
            articles,
            key=lambda article: (
                article.get("published_at") or article.get("collected_at") or "",
                article.get("relevance_score", 0),
                article.get("id", 0),
            ),
            reverse=True,
        )
        representative = sorted_articles[0]
        matched_keywords = sorted({keyword for article in sorted_articles for keyword in article.get("matched_keywords", [])})
        topic_categories = sorted({article.get("topic_category") or "-" for article in sorted_articles})
        impact_levels = sorted(
            {article.get("business_impact_level") or "-" for article in sorted_articles},
            key=lambda value: (-IMPACT_PRIORITY.get(value, 0), value),
        )
        urgency_levels = sorted(
            {article.get("urgency_level") or "-" for article in sorted_articles},
            key=lambda value: (-URGENCY_PRIORITY.get(value, 0), value),
        )
        review_statuses = sorted(
            {article.get("review_status") or UNREVIEWED for article in sorted_articles},
            key=lambda value: (-REVIEW_PRIORITY.get(value, 0), value),
        )
        source_titles = sorted({article.get("source_title") or "-" for article in sorted_articles})
        latest_published_at = max(
            (article.get("published_at") or article.get("collected_at") or "" for article in sorted_articles),
            default="",
        )

        return {
            "group_id": f"news-group-{index}",
            "display_title": representative["title"],
            "related_count": max(len(sorted_articles) - 1, 0),
            "total_count": len(sorted_articles),
            "representative": representative,
            "articles": sorted_articles,
            "article_ids": [article["id"] for article in sorted_articles],
            "latest_published_at": latest_published_at,
            "matched_keywords": matched_keywords,
            "topic_categories": topic_categories,
            "business_impact_levels": impact_levels,
            "urgency_levels": urgency_levels,
            "review_statuses": review_statuses,
            "primary_topic_category": representative.get("topic_category") or "-",
            "primary_business_impact_level": impact_levels[0] if impact_levels else representative.get("business_impact_level") or "-",
            "primary_urgency_level": urgency_levels[0] if urgency_levels else representative.get("urgency_level") or "-",
            "primary_review_status": review_statuses[0] if review_statuses else representative.get("review_status") or UNREVIEWED,
            "has_mixed_review_statuses": len(review_statuses) > 1,
            "source_count": len(source_titles),
            "max_relevance_score": max((article.get("relevance_score", 0) for article in sorted_articles), default=0),
            "title_filter_values": sorted(
                {
                    value
                    for article in sorted_articles
                    for value in [article.get("title") or "-", article.get("source_title") or "-"]
                }
            ),
        }

    def _are_related_articles(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_title = self._normalize_group_title(left.get("title"))
        right_title = self._normalize_group_title(right.get("title"))
        if not left_title or not right_title:
            return False
        if left_title == right_title:
            return True
        if (left_title in right_title or right_title in left_title) and min(len(left_title), len(right_title)) >= 12:
            return True

        left_tokens = self._title_tokens(left.get("title"))
        right_tokens = self._title_tokens(right.get("title"))
        if not left_tokens or not right_tokens:
            return False

        intersection = left_tokens & right_tokens
        if not intersection:
            return False

        overlap_ratio = len(intersection) / min(len(left_tokens), len(right_tokens))
        jaccard = len(intersection) / len(left_tokens | right_tokens)
        title_char_jaccard = self._char_ngram_similarity(left.get("title"), right.get("title"))
        same_keyword = bool(set(left.get("matched_keywords", [])) & set(right.get("matched_keywords", [])))
        same_category = left.get("topic_category") == right.get("topic_category")
        left_context_tokens = self._context_tokens(left)
        right_context_tokens = self._context_tokens(right)
        context_intersection = left_context_tokens & right_context_tokens
        context_jaccard = (
            len(context_intersection) / len(left_context_tokens | right_context_tokens)
            if left_context_tokens and right_context_tokens
            else 0.0
        )
        shared_salient_tokens = self._salient_tokens(left_context_tokens) & self._salient_tokens(right_context_tokens)

        if overlap_ratio >= 0.8:
            return True
        if same_keyword and title_char_jaccard >= 0.48:
            return True
        if same_keyword and len(shared_salient_tokens) >= 3 and context_jaccard >= 0.28:
            return True
        if same_keyword and jaccard >= 0.5:
            return True
        if same_keyword and same_category and title_char_jaccard >= 0.35:
            return True
        if same_keyword and same_category and context_jaccard >= 0.38:
            return True
        if same_keyword and same_category and overlap_ratio >= 0.6:
            return True
        return False

    def _normalize_group_title(self, title: str | None) -> str:
        if not title:
            return ""
        cleaned = re.sub(r"[\[\]\(\)\"'“”‘’·,…!?:;/\\|-]+", " ", title.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _title_tokens(self, title: str | None) -> set[str]:
        normalized = self._normalize_group_title(title)
        tokens = {token for token in TITLE_TOKEN_RE.findall(normalized) if len(token) >= 2}
        return {token for token in tokens if token not in NEWS_TITLE_STOPWORDS}

    def _context_tokens(self, article: dict[str, Any]) -> set[str]:
        normalized = self._normalize_group_title(
            " ".join(
                part
                for part in [
                    article.get("title") or "",
                    article.get("summary") or "",
                    " ".join(article.get("matched_keywords", [])),
                ]
                if part
            )
        )
        tokens = {token for token in TITLE_TOKEN_RE.findall(normalized) if len(token) >= 2}
        return {token for token in tokens if token not in NEWS_TITLE_STOPWORDS}

    def _salient_tokens(self, tokens: set[str]) -> set[str]:
        return {
            token
            for token in tokens
            if len(token) >= 4 or any(character.isdigit() for character in token)
        }

    def _char_ngram_similarity(self, left_text: str | None, right_text: str | None, size: int = 3) -> float:
        left_ngrams = self._char_ngrams(left_text, size=size)
        right_ngrams = self._char_ngrams(right_text, size=size)
        if not left_ngrams or not right_ngrams:
            return 0.0
        return len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)

    def _char_ngrams(self, text: str | None, *, size: int) -> set[str]:
        compact = re.sub(r"\s+", "", self._normalize_group_title(text))
        if not compact:
            return set()
        if len(compact) <= size:
            return {compact}
        return {compact[index : index + size] for index in range(len(compact) - size + 1)}

    def _load_trend_data(self, filters: NewsFilterParams) -> dict[str, Any]:
        where_clause, params = self._where_clause(filters, apply_review_filter=False)
        recent_7_days = (date.today() - timedelta(days=6)).isoformat()
        recent_30_days = (date.today() - timedelta(days=29)).isoformat()
        where_tail = f" AND {where_clause[6:]}" if where_clause else ""
        with get_connection() as connection:
            category_7 = connection.execute(
                f"""
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                """,
                [recent_7_days, *params],
            ).fetchall()
            category_30 = connection.execute(
                f"""
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                """,
                [recent_30_days, *params],
            ).fetchall()
            keyword_rows = connection.execute(
                f"""
                SELECT
                    substr(COALESCE(published_at, collected_at), 1, 10) AS day,
                    keyword,
                    COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY day, keyword
                ORDER BY day, keyword
                """,
                [recent_30_days, *params],
            ).fetchall()
        return {
            "category_7d": [{"label": row["topic_category"], "value": row["count"]} for row in category_7],
            "category_30d": [{"label": row["topic_category"], "value": row["count"]} for row in category_30],
            "keyword_series": [{"day": row["day"], "keyword": row["keyword"], "value": row["count"]} for row in keyword_rows],
        }

    def _build_executive_summary(self, filters: NewsFilterParams) -> dict[str, list[str]]:
        where_clause, params = self._where_clause(filters, apply_review_filter=False)
        seven_days_ago = (date.today() - timedelta(days=6)).isoformat()
        where_tail = f" AND {where_clause[6:]}" if where_clause else ""
        with get_connection() as connection:
            top_topics = connection.execute(
                f"""
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                LIMIT 3
                """,
                [seven_days_ago, *params],
            ).fetchall()
            urgent_rows = connection.execute(
                f"""
                SELECT title, owner_department, business_impact_level
                FROM news_articles
                WHERE business_impact_level IN (?, ?){where_tail}
                ORDER BY relevance_score DESC, COALESCE(published_at, collected_at) DESC
                LIMIT 3
                """,
                [IMPORTANT, IMMEDIATE, *params],
            ).fetchall()

        key_trends = [
            f"{row['topic_category']} issue led the last 7 days with {row['count']} tracked articles."
            for row in top_topics
        ] or ["There are not enough recent articles yet to summarize a clear trend."]

        implications = [
            f"{row['owner_department']} should review the business impact of '{row['title']}'."
            for row in urgent_rows
        ] or ["Keep expanding the keyword set until higher-priority news accumulates."]

        recommended_tasks = [
            "Review important and urgent articles together before the weekly management meeting.",
            "Disable noisy keywords and add replacement keywords from the operations panel.",
            "Use accumulated feedback to tighten classification and grouping rules.",
        ]
        return {
            "key_trends": key_trends[:3],
            "implications": implications[:3],
            "recommended_tasks": recommended_tasks,
        }

    def _load_operations(self) -> dict[str, Any]:
        today = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=6)).isoformat()
        with get_connection() as connection:
            active_keyword_count = connection.execute(
                "SELECT COUNT(*) FROM news_keywords WHERE is_active = 1"
            ).fetchone()[0]
            usage_today = connection.execute(
                """
                SELECT COUNT(*)
                FROM news_collection_logs
                WHERE substr(started_at, 1, 10) = ?
                """,
                (today,),
            ).fetchone()[0]
            error_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM news_collection_logs
                WHERE substr(started_at, 1, 10) >= ?
                  AND status = 'failed'
                """,
                (week_ago,),
            ).fetchone()[0]
            latest_logs = connection.execute(
                """
                SELECT *
                FROM news_collection_logs
                ORDER BY started_at DESC, id DESC
                LIMIT 8
                """
            ).fetchall()
        return {
            "active_keyword_count": active_keyword_count,
            "usage_today": usage_today,
            "error_count": error_count,
            "latest_logs": [dict(row) for row in latest_logs],
        }
