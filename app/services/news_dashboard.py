from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..database import get_connection, row_to_news_article


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
        return {
            "filters": self._serialize_filters(filters),
            "filter_options": self._load_filter_options(),
            "kpis": self._load_kpis(),
            "articles": self._load_articles(filters),
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
            params.append("미검토")

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
                    SUM(CASE WHEN business_impact_level IN ('중요', '즉시조치') THEN 1 ELSE 0 END) AS important_count,
                    SUM(CASE WHEN business_impact_level = '즉시조치' THEN 1 ELSE 0 END) AS urgent_count
                FROM news_articles
                WHERE substr(COALESCE(published_at, collected_at), 1, 10) >= ?
                """,
                (seven_days_ago,),
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
                WHERE business_impact_level IN ('중요', '즉시조치'){where_tail}
                ORDER BY relevance_score DESC, COALESCE(published_at, collected_at) DESC
                LIMIT 3
                """,
                params,
            ).fetchall()

        key_trends = [
            f"{row['topic_category']} 이슈가 최근 7일 기준 {row['count']}건으로 상위권을 형성했습니다."
            for row in top_topics
        ] or ["최근 7일 기준 누적된 산업 뉴스가 아직 없습니다."]

        implications = [
            f"{row['owner_department']} 주도로 '{row['title']}'와 유사한 이슈의 사업 영향 여부를 점검할 필요가 있습니다."
            for row in urgent_rows
        ] or ["고영향 기사 누적 전까지는 키워드 커버리지와 수집 안정성을 우선 점검하세요."]

        recommended_tasks = [
            "주간 경영회의 전에 중요/즉시조치 기사와 규제 이슈를 함께 검토해 실행 우선순위를 맞추세요.",
            "키워드 관리 화면에서 잡음이 많은 검색어는 비활성화하고 품목별 세부 키워드를 보강하세요.",
            "기사 피드백을 누적해 분류오류 패턴을 분석 규칙에 반영하세요.",
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
