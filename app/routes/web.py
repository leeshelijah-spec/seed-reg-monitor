from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..database import get_connection, row_to_regulation
from ..services.ingestion import IngestionService
from ..services.news_dashboard import NewsDashboardService, NewsFilterParams
from ..services.news_ingestion import NewsIngestionService
from ..services.news_keywords import NewsKeywordService
from ..services.news_utils import now_iso


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["settings"] = settings
ACTION_STATUS_OPTIONS = ("미확인", "조치필요", "조치중", "조치완료", "해당없음")
NEWS_FEEDBACK_TYPES = ("중요", "잡음", "분류오류")


def _parse_news_filters(request: Request) -> NewsFilterParams:
    return NewsFilterParams(
        start_date=request.query_params.get("news_start_date") or None,
        end_date=request.query_params.get("news_end_date") or None,
        keyword=request.query_params.get("news_keyword") or None,
        topic_category=request.query_params.get("news_topic_category") or None,
        business_impact_level=request.query_params.get("news_business_impact_level") or None,
        owner_department=request.query_params.get("news_owner_department") or None,
        show_all_articles=request.query_params.get("show_news_all") == "1",
    )


def _dashboard_url(request: Request, updates: dict[str, str | None], anchor: str | None = None) -> str:
    params = dict(request.query_params)
    for key, value in updates.items():
        if value in (None, "", "0"):
            params.pop(key, None)
        else:
            params[key] = value

    query_string = urlencode(params)
    url = request.url.path
    if query_string:
        url = f"{url}?{query_string}"
    if anchor:
        url = f"{url}#{anchor}"
    return url


def _load_regulation_dashboard(show_all: bool = False) -> dict:
    today = date.today().isoformat()
    in_30_days = (date.today() + timedelta(days=30)).isoformat()

    with get_connection() as connection:
        today_new_count = connection.execute(
            "SELECT COUNT(*) FROM regulations WHERE substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()[0]
        unreviewed_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM regulations r
            LEFT JOIN review_logs l ON l.regulation_id = r.id
            WHERE l.regulation_id IS NULL
            """,
        ).fetchone()[0]
        imminent_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM regulations
            WHERE effective_date IS NOT NULL
              AND effective_date BETWEEN ? AND ?
            """,
            (today, in_30_days),
        ).fetchone()[0]
        severity_rows = connection.execute(
            "SELECT severity, COUNT(*) AS count FROM regulations GROUP BY severity ORDER BY count DESC"
        ).fetchall()
        recent_sql = """
            SELECT
                r.*,
                COALESCE(
                    (
                        SELECT rl.status
                        FROM review_logs rl
                        WHERE rl.regulation_id = r.id
                        ORDER BY rl.updated_at DESC, rl.rowid DESC
                        LIMIT 1
                    ),
                    '미확인'
                ) AS action_status
            FROM regulations r
            {where_clause}
            ORDER BY r.created_at DESC, r.publication_date DESC
            LIMIT 20
        """
        recent_rows = connection.execute(
            recent_sql.format(where_clause="" if show_all else "WHERE NOT EXISTS (SELECT 1 FROM review_logs rl2 WHERE rl2.regulation_id = r.id)"),
        ).fetchall()
        latest_sync = connection.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    recent_regulations: list[dict] = []
    for row in recent_rows:
        item = row_to_regulation(row)
        if item is None:
            continue
        item["action_status"] = row["action_status"] or ACTION_STATUS_OPTIONS[0]
        recent_regulations.append(item)

    return {
        "stats": {
            "today_new_count": today_new_count,
            "unreviewed_count": unreviewed_count,
            "imminent_count": imminent_count,
        },
        "severity_distribution": [
            {"label": row["severity"], "value": row["count"]} for row in severity_rows
        ],
        "recent_regulations": recent_regulations,
        "show_all_regulations": show_all,
        "latest_sync": dict(latest_sync) if latest_sync else None,
    }


@router.get("/")
def dashboard(request: Request):
    show_all_regulations = request.query_params.get("show_regulation_all") == "1"
    regulation_dashboard = _load_regulation_dashboard(show_all=show_all_regulations)
    news_filters = _parse_news_filters(request)
    news_dashboard = NewsDashboardService().load_dashboard(news_filters)
    news_keywords = NewsKeywordService().list_keywords(include_inactive=True)
    news_service = NewsIngestionService()
    current_dashboard_url = _dashboard_url(request, {})

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            **regulation_dashboard,
            "news_dashboard": news_dashboard,
            "news_keywords": news_keywords,
            "news_api_configured": news_service.is_configured(),
            "news_feedback_types": NEWS_FEEDBACK_TYPES,
            "current_dashboard_url": current_dashboard_url,
            "regulation_toggle_url": _dashboard_url(
                request,
                {"show_regulation_all": None if show_all_regulations else "1"},
                anchor="regulation-review-list",
            ),
            "news_toggle_url": _dashboard_url(
                request,
                {"show_news_all": None if news_filters.show_all_articles else "1"},
                anchor="news-review-list",
            ),
        },
    )


@router.get("/api/news/dashboard")
def news_dashboard_api(request: Request):
    return NewsDashboardService().load_dashboard(_parse_news_filters(request))


@router.get("/api/news/articles")
def news_articles_api(request: Request):
    data = NewsDashboardService().load_dashboard(_parse_news_filters(request))
    return {"count": len(data["articles"]), "items": data["articles"]}


@router.get("/regulations/{regulation_id}")
def regulation_detail(request: Request, regulation_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM regulations WHERE id = ?",
            (regulation_id,),
        ).fetchone()
        review_row = connection.execute(
            """
            SELECT reviewer, status, comment, updated_at
            FROM review_logs
            WHERE regulation_id = ?
            ORDER BY updated_at DESC, rowid DESC
            LIMIT 1
            """,
            (regulation_id,),
        ).fetchone()

    regulation = row_to_regulation(row)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "regulation": regulation,
            "review_log": dict(review_row) if review_row else None,
            "action_status_options": ACTION_STATUS_OPTIONS,
        },
    )


@router.post("/regulations/{regulation_id}/review")
async def update_regulation_review(request: Request, regulation_id: int):
    raw_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    action_status = raw_form.get("action_status", [""])[0].strip()
    action_note = raw_form.get("action_note", [""])[0].strip()

    if action_status not in ACTION_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid action status")

    updated_at = datetime.now(ZoneInfo(settings.timezone)).isoformat()
    with get_connection() as connection:
        exists = connection.execute(
            "SELECT 1 FROM regulations WHERE id = ?",
            (regulation_id,),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Regulation not found")

        connection.execute(
            """
            INSERT INTO review_logs (regulation_id, reviewer, status, comment, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (regulation_id, "web", action_status, action_note or None, updated_at),
        )

    return RedirectResponse(url=f"/regulations/{regulation_id}", status_code=303)


@router.post("/sync")
def trigger_sync():
    IngestionService().run(lookback_days=5)
    return RedirectResponse(url="/", status_code=303)


@router.post("/news/sync")
def trigger_news_sync():
    service = NewsIngestionService()
    if service.is_configured():
        service.run(run_type="manual")
    return RedirectResponse(url="/", status_code=303)


@router.post("/news/keywords")
async def add_news_keyword(request: Request):
    raw_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    keyword = raw_form.get("keyword", [""])[0].strip()
    keyword_group = raw_form.get("keyword_group", [""])[0].strip()
    notes = raw_form.get("notes", [""])[0].strip()
    return_to = raw_form.get("return_to", ["/"])[0].strip() or "/"
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")
    NewsKeywordService().add_keyword(keyword=keyword, keyword_group=keyword_group, notes=notes or None)
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/news/keywords/{keyword_id}/toggle")
async def toggle_news_keyword(request: Request, keyword_id: int):
    raw_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    desired_state = raw_form.get("desired_state", [""])[0].strip()
    return_to = raw_form.get("return_to", ["/"])[0].strip() or "/"
    NewsKeywordService().set_keyword_active(keyword_id, desired_state == "activate")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/news/{article_id}/feedback")
async def record_news_feedback(request: Request, article_id: int):
    raw_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    feedback_type = raw_form.get("feedback_type", [""])[0].strip()
    comment = raw_form.get("comment", [""])[0].strip()
    return_to = raw_form.get("return_to", ["/"])[0].strip() or "/"
    if feedback_type not in NEWS_FEEDBACK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid feedback type")

    with get_connection() as connection:
        exists = connection.execute(
            "SELECT 1 FROM news_articles WHERE id = ?",
            (article_id,),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Article not found")
        connection.execute(
            """
            INSERT INTO news_feedback (article_id, feedback_type, comment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (article_id, feedback_type, comment or None, now_iso()),
        )
        connection.execute(
            """
            UPDATE news_articles
            SET review_status = ?
            WHERE id = ?
            """,
            (feedback_type, article_id),
        )

    return RedirectResponse(url=return_to, status_code=303)
