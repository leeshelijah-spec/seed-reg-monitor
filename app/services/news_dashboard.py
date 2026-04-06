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
                  AND review_status != ?
                """,
                (IMPORTANT, IMMEDIATE, IMMEDIATE, seven_days_ago, NOISE),
            ).fetchone()
            top_topic_rows = connection.execute(
                """
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?
                  AND review_status = ?
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                LIMIT 5
                """,
                (seven_days_ago, "ê´€ë ¨"),
            ).fetchall()
        return {
            "recent_count": row["recent_count"] or 0,
            "important_count": row["important_count"] or 0,
            "urgent_count": row["urgent_count"] or 0,
            "top_topics": [
                {"label": topic_row["topic_category"], "count": topic_row["count"]}
                for topic_row in top_topic_rows
            ],
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
        cleaned = re.sub(r"[\[\]\(\)\"'â€œâ€â€˜â€™Â·,â€¦!?:;/\\|-]+", " ", title.lower())
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
                WHERE review_status != ?
                  AND substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                """,
                [NOISE, recent_7_days, *params],
            ).fetchall()
            category_30 = connection.execute(
                f"""
                SELECT topic_category, COUNT(*) AS count
                FROM news_articles
                WHERE review_status != ?
                  AND substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                """,
                [NOISE, recent_30_days, *params],
            ).fetchall()
            keyword_rows = connection.execute(
                f"""
                SELECT
                    substr(COALESCE(published_at, collected_at), 1, 10) AS day,
                    keyword,
                    COUNT(*) AS count
                FROM news_articles
                WHERE review_status != ?
                  AND substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                GROUP BY day, keyword
                ORDER BY day, keyword
                """,
                [NOISE, recent_30_days, *params],
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
                  AND review_status != ?
                GROUP BY topic_category
                ORDER BY count DESC, topic_category
                LIMIT 3
                """,
                [seven_days_ago, *params, NOISE],
            ).fetchall()
            urgent_rows = connection.execute(
                f"""
                SELECT title, owner_department, business_impact_level, review_status
                FROM news_articles
                WHERE business_impact_level IN (?, ?){where_tail}
                  AND review_status != ?
                ORDER BY CASE WHEN review_status = ? THEN 0 ELSE 1 END,
                         relevance_score DESC,
                         COALESCE(published_at, collected_at) DESC
                LIMIT 3
                """,
                [IMPORTANT, IMMEDIATE, *params, NOISE, "ê´€ë ¨"],
            ).fetchall()
            feedback_summary = connection.execute(
                f"""
                SELECT
                    SUM(CASE WHEN review_status = ? THEN 1 ELSE 0 END) AS relevant_count,
                    SUM(CASE WHEN review_status = ? THEN 1 ELSE 0 END) AS noise_count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?{where_tail}
                """,
                ["ê´€ë ¨", NOISE, seven_days_ago, *params],
            ).fetchall()
        feedback_counts = feedback_summary[0] if feedback_summary else {"relevant_count": 0, "noise_count": 0}

        key_trends = [
            f"ìµœê·¼ 7ì¼ ë™ì•ˆ '{row['topic_category']}' ì´ìŠˆê°€ {row['count']}ê±´ìœ¼ë¡œ ê°€ì¥ ë§ì´ í¬ì°©ë˜ì—ˆìŠµë‹ˆë‹¤."
            for row in top_topics
        ] or ["ìµœê·¼ ê¸°ì‚¬ ìˆ˜ê°€ ì•„ì§ ì¶©ë¶„í•˜ì§€ ì•Šì•„ æ²js®‚ß¶Vpƒ¶V×².°ƒ¶*ã®‚3®Ns®–ğƒ²jS²V÷¶VcªâÀƒ²ZÓ®‚×²*×®.#®.¸‰t((€€€€€€€¥µÁ±¥…Ñ¥½¹Ì€ôl(€€€€€€€€€€€˜‰íÉ½İl½İ¹•É}‘•Á…ÉÑµ•¹Ğu÷²^C²p€íÉ½İlÑ¥Ñ±”uôŸ²v`íÉ½İl‰ÕÍ¥¹•ÍÍ}¥µÁ…Ñ}±•Ù•°uôƒ²b¶Z”ƒ²^³®Ú®–ğƒ²jÃ²€ƒªÊ¶ƒ¶Vc²ã²jP¸ˆ(€€€€€€€€€€€™½ÈÉ½Ü¥¸ÕÉ•¹Ñ}É½İÌ(€€€€€€€t½Èl‹²’G²jS®>ƒ®K²v ƒªâÃ²
³ªÂ ƒ®6Pƒ®"²‚®B€ƒ®V3ªæ3² ƒ¶
“²n3®Npƒ®ÊS²r®–ğƒ®O¶b ƒ®ª£®.#¶Ã®²vƒ²vÓ²ZÓªÂ²ã²jP¸‰t((€€€€€€€É•½µµ•¹‘•‘}Ñ…Í­Ì€ômt(€€€€€€€¥˜€¡™••‘‰…­}½Õ¹ÑÍl‰É•±•Ù…¹Ñ}½Õ¹Ğ‰t½È€À¤€ø€Àè(€€€€€€€€€€€É•½µµ•¹‘•‘}Ñ…Í­Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€˜‹²ÖsªŞğ€ß²vğƒ®>g²V ƒªÒ®‚£²ró®†pƒ¶fW²vã®BpƒªâÃ²
°í™••‘‰…­}½Õ¹ÑÍlÉ•±•Ù…¹Ñ}½Õ¹Ğu÷ªÆÓ²v ƒ®Ú²s®Îƒ².“¶Z'ªÎ¶j7ªÎğƒ²óªÂƒ®ÎÓªÎƒ²^@ƒ®Âc²b¶Vc²ã²jP¸ˆ(€€€€€€€€€€€€¤(€€€€€€€¥˜€¡™••‘‰…­}½Õ¹ÑÍl‰¹½¥Í•}½Õ¹Ğ‰t½È€À¤€ø€Àè(€€€€€€€€€€€É•½µµ•¹‘•‘}Ñ…Í­Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€˜‹²z‡²v3²ró®†pƒ®Ú®–c®BpƒªâÃ²
°í™••‘‰…­}½Õ¹ÑÍl¹½¥Í•}½Õ¹Ğu÷ªÆÓ²v ƒ¶
“²n3®Npƒ²rƒ² ƒ²^³®Ú²f ƒªŞã®äƒªŞs²ædƒ²†Ã²‚Tƒ¶n®ÎÓ®†pƒªÊ¶ƒ¶Vc²ã²jP¸ˆ(€€€€€€€€€€€€¤(€€€€€€€É•½µµ•¹‘•‘}Ñ…Í­Ì¹•áÑ•¹ (€€€€€€€€€€€l(€€€€€€€€€€€€€€€€‹²óªÂƒªÊ÷²b¶j3²v`ƒ²‚²^@ƒ²’G²jS
ß²š'².s²†Ã²æ`ƒªâÃ²
³®–ğƒ¶V£ªî`ƒªÊ¶ƒ¶Vc²ã²jP¸ˆ°(€€€€€€€€€€€€€€€€‹®"²‚®Bpƒ¶Ró®NpîÂÇ²vƒ®ÂS¶W²ró®†pƒ®Ú®–`ƒ®Â<ƒªŞã®äƒªŞs²æg²vƒªÎ²4ƒ®ÎÓ²‚W¶Vc²ã²jP¸ˆ°(€€€€€€€€€€€t(€€€€€€€€¤(€€€€€€€É•ÑÕÉ¸ì(€€€€€€€€€€€€‰­•å}ÑÉ•¹‘Ìˆè­•å}ÑÉ•¹‘ÍlèÍt°(€€€€€€€€€€€€‰¥µÁ±¥…Ñ¥½¹Ìˆè¥µÁ±¥…Ñ¥½¹ÍlèÍt°(€€€€€€€€€€€€‰É•½µµ•¹‘•‘}Ñ…Í­ÌˆèÉ•½µµ•¹‘•‘}Ñ…Í­ÍlèÍt°(€€€€€€€ô((€€€‘•˜}±½…‘}½Á•É…Ñ¥½¹Ì¡Í•±˜¤€´ø‘¥ÑmÍÑÈ°¹åtè(€€€€€€€Ñ½‘…ä€ô‘…Ñ”¹Ñ½‘…ä ¤¹¥Í½™½Éµ…Ğ ¤(€€€€€€€İ••­}…¼€ô€¡‘…Ñ”¹Ñ½‘…ä ¤€´Ñ¥µ•‘•±Ñ„¡‘…åÌôØ¤¤¹¥Í½™½Éµ…Ğ ¤(€€€€€€€İ¥Ñ •Ñ}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€…Ñ¥Ù•}­•åİ½É‘}½Õ¹Ğ€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€‰M1P=U9P ¨¤I=4¹•İÍ}­•åİ½É‘Ì]!I¥Í}…Ñ¥Ù”€ô€Äˆ(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€ÕÍ…•}Ñ½‘…ä€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P=U9P ¨¤(€€€€€€€€€€€€€€€I=4¹•İÍ}½±±•Ñ¥½¹}±½Ì(€€€€€€€€€€€€€€€]!IÍÕ‰ÍÑÈ¡ÍÑ…ÉÑ•‘}…Ğ°€Ä°€ÄÀ¤€ô€ü(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡Ñ½‘…ä°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€•ÉÉ½É}½Õ¹Ğ€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P=U9P ¨¤(€€€€€€€€€€€€€€€I=4¹•İÍ}½±±•Ñ¥½¹}±½Ì(€€€€€€€€€€€€€€€]!IÍÕ‰ÍÑÈ¡ÍÑ…ÉÑ•‘}…Ğ°€Ä°€ÄÀ¤€øô€ü(€€€€€€€€€€€€€€€€€9ÍÑ…ÑÕÌ€ô€™…¥±•œ(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡İ••­}…¼°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€±…Ñ•ÍÑ}±½Ì€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P€¨(€€€€€€€€€€€€€€€I=4¹•İÍ}½±±•Ñ¥½¹}±½Ì(€€€€€€€€€€€€€€€=IH	dÍÑ…ÉÑ•‘}…ĞM°¥M(€€€€€€€€€€€€€€€1%5%P€à(€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸ì(€€€€€€€€€€€€‰…Ñ¥Ù•}­•åİ½É‘}½Õ¹Ğˆè…Ñ¥Ù•}­•åİ½É‘}½Õ¹Ğ°(€€€€€€€€€€€€‰ÕÍ…•}Ñ½‘…äˆèÕÍ…•}Ñ½‘…ä°(€€€€€€€€€€€€‰•ÉÉ½É}½Õ¹Ğˆè•ÉÉ½É}½Õ¹Ğ°(€€€€€€€€€€€€‰±…Ñ•ÍÑ}±½Ìˆèm‘¥Ğ¡É½Ü¤™½ÈÉ½Ü¥¸±…Ñ•ÍÑ}±½Ít°(€€€€€€€ô(