from __future__ import annotations

from threading import Thread
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..database import get_connection, row_to_regulation
from ..services.ingestion import IngestionService
from ..services.news_analysis import NewsAnalysisService
from ..services.news_dashboard import NewsDashboardService, NewsFilterParams
from ..services.news_ingestion import NewsIngestionService
from ..services.news_keywords import NewsKeywordService
from ..services.sync_progress import sync_progress
from ..services.news_utils import now_iso


REVIEW_UNKNOWN = "\ubbf8\ud655\uc778"
REVIEW_NEEDED = "\uc870\uce58\ud544\uc694"
REVIEW_IN_PROGRESS = "\uc870\uce58\uc911"
REVIEW_DONE = "\uc870\uce58\uc644\ub8cc"
REVIEW_NOT_APPLICABLE = "\ud574\ub2f9\uc5c6\uc74c"
ACTION_STATUS_OPTIONS = (
    REVIEW_UNKNOWN,
    REVIEW_NEEDED,
    REVIEW_IN_PROGRESS,
    REVIEW_DONE,
    REVIEW_NOT_APPLICABLE,
)

UNREVIEWED = "\ubbf8\uac80\ud1a0"
RELEVANT = "\uad00\ub828"
NOISE = "\uc7a1\uc74c"
IMPACT_OPTIONS = (
    ("\uc989\uc2dc\uc870\uce58", "\uc989\uc2dc\uc870\uce58"),
    ("\uc911\uc694", "\uc911\uc694"),
    ("\uac80\ud1a0\ud544\uc694", "\uac80\ud1a0\ud544\uc694"),
    ("\ucc38\uace0", "\ucc38\uace0"),
)
URGENCY_OPTIONS = (
    ("high", "\ub192\uc74c"),
    ("medium", "\ubcf4\ud1b5"),
    ("low", "\ub0ae\uc74c"),
)


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["settings"] = settings


def _sync_progress_payload() -> dict[str, dict]:
    return sync_progress.snapshot_all()


def _build_progress_callback(kind: str):
    def _callback(current: int, total: int, message: str) -> None:
        sync_progress.update(kind, current=current, total=total, message=message)

    return _callback


def _start_regulation_sync_job() -> bool:
    started = sync_progress.begin(
        "regulation",
        message="규제 동기화를 준비하는 중입니다.",
        total=1,
    )
    if not started:
        return False

    def _worker() -> None:
        try:
            result = IngestionService().run(
                lookback_days=settings.regulation_sync_lookback_days,
                progress_callback=_build_progress_callback("regulation"),
            )
            sync_progress.complete(
                "regulation",
                message=f"규제 동기화가 완료되었습니다. 신규 {result['inserted_count']}건을 반영했습니다.",
                result={
                    "collected_count": result["collected_count"],
                    "inserted_count": result["inserted_count"],
                },
            )
        except Exception as exc:  # noqa: BLE001
            sync_progress.fail("regulation", message=f"규제 동기화 중 오류가 발생했습니다: {exc}")

    Thread(target=_worker, daemon=True, name="regulation-sync").start()
    return True


def _start_news_sync_job() -> bool:
    service = NewsIngestionService()
    if not service.is_configured():
        sync_progress.fail("news", message="뉴스 API 설정이 없어 수집을 시작할 수 없습니다.")
        return False

    started = sync_progress.begin(
        "news",
        message="뉴스 수집을 준비하는 중입니다.",
        total=1,
    )
    if not started:
        return False

    def _worker() -> None:
        try:
            result = service.run(
                run_type="manual",
                progress_callback=_build_progress_callback("news"),
            )
            final_message = (
                f"뉴스 수집이 완료되었습니다. 신규 {result['inserted_count']}건, 중복 {result['duplicate_count']}건입니다."
            )
            if result["errors"]:
                final_message = f"뉴스 수집이 끝났지만 오류 {len(result['errors'])}건이 있어 확인이 필요합니다."
            sync_progress.complete("news", message=final_message, result=result)
        except Exception as exc:  # noqa: BLE001
            sync_progress.fail("news", message=f"뉴스 수집 중 오류가 발생했습니다: {exc}")

    Thread(target=_worker, daemon=True, name="news-sync").start()
    return True


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
        review_status_rows = connection.execute(
            f"""
            SELECT
                COALESCE(
                    (
                        SELECT rl.status
                        FROM review_logs rl
                        WHERE rl.regulation_id = r.id
                        ORDER BY rl.updated_at DESC, rl.rowid DESC
                        LIMIT 1
                    ),
                    ?
                ) AS action_status,
                COUNT(*) AS count
            FROM regulations r
            GROUP BY action_status
            ORDER BY count DESC, action_status
            """,
            (REVIEW_UNKNOWN,),
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
                    ?
                ) AS action_status
            FROM regulations r
            {where_clause}
            ORDER BY r.created_at DESC, r.publication_date DESC
            LIMIT 20
        """
        recent_rows = connection.execute(
            recent_sql.format(
                where_clause=""
                if show_all
                else "WHERE NOT EXISTS (SELECT 1 FROM review_logs rl2 WHERE rl2.regulation_id = r.id)"
            ),
            (REVIEW_UNKNOWN,),
        ).fetchall()
        latest_sync = connection.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    recent_regulations: list[dict] = []
    for row in recent_rows:
        item = row_to_regulation(row)
        if item is None:
            continue
        item["action_status"] = row["action_status"] or REVIEW_UNKNOWN
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
        "review_status_summary": [
            {"label": row["action_status"], "value": row["count"]} for row in review_status_rows
        ],
        "recent_regulations": recent_regulations,
        "show_all_regulations": show_all,
        "latest_sync": dict(latest_sync) if latest_sync else None,
    }


def _derive_feedback_payload(
    *,
    impact_level: str,
    urgency_level: str,
    is_relevant: bool,
    is_noise: bool,
    comment: str | None,
) -> dict[str, object]:
    valid_impacts = {value for value, _ in IMPACT_OPTIONS}
    valid_urgencies = {value for value, _ in URGENCY_OPTIONS}

    if is_noise and is_relevant:
        raise HTTPException(status_code=400, detail="Noise items cannot also be marked relevant")

    normalized_impact_level = None
    normalized_urgency_level = None
    if is_relevant:
        if impact_level not in valid_impacts:
            raise HTTPException(status_code=400, detail="Invalid impact level")
        if urgency_level not in valid_urgencies:
            raise HTTPException(status_code=400, detail="Invalid urgency level")
        normalized_impact_level = impact_level
        normalized_urgency_level = urgency_level

    feedback_type = RELEVANT if is_relevant else NOISE if is_noise else "\uac80\ud1a0\uc644\ub8cc"
    review_status = RELEVANT if is_relevant else NOISE if is_noise else "\uac80\ud1a0\uc644\ub8cc"

    return {
        "feedback_type": feedback_type,
        "review_status": review_status,
        "impact_level": normalized_impact_level,
        "urgency_level": normalized_urgency_level,
        "is_relevant": 1 if is_relevant else 0,
        "is_noise": 1 if is_noise else 0,
        "comment": comment or None,
    }


def _parse_feedback_flags(raw_form: dict[str, list[str]]) -> tuple[bool, bool]:
    feedback_action = raw_form.get("feedback_action", [""])[0].strip()
    if feedback_action == "relevant":
        return True, False
    if feedback_action == "noise":
        return False, True
    if feedback_action:
        raise HTTPException(status_code=400, detail="Invalid feedback action")

    return (
        raw_form.get("is_relevant", [""])[0].strip() == "1",
        raw_form.get("is_noise", [""])[0].strip() == "1",
    )


def _record_news_feedback_for_articles(
    *,
    article_ids: list[int],
    impact_level: str,
    urgency_level: str,
    is_relevant: bool,
    is_noise: bool,
    comment: str | None,
) -> None:
    if not article_ids:
        raise HTTPException(status_code=400, detail="Article id is required")

    payload = _derive_feedback_payload(
        impact_level=impact_level,
        urgency_level=urgency_level,
        is_relevant=is_relevant,
        is_noise=is_noise,
        comment=comment,
    )
    unique_article_ids = list(dict.fromkeys(article_ids))
    placeholders = ",".join("?" for _ in unique_article_ids)
    created_at = now_iso()
    analyzer = NewsAnalysisService()

    with get_connection() as connection:
        existing_rows = connection.execute(
            f"SELECT * FROM news_articles WHERE id IN ({placeholders})",
            unique_article_ids,
        ).fetchall()
        existing_articles = {
            row["id"]: row
            for row in existing_rows
        }

        for article_id in unique_article_ids:
            if article_id not in existing_articles:
                raise HTTPException(status_code=404, detail="Article not found")

            article = dict(existing_articles[article_id])
            updated_impact_level = payload["impact_level"] or article.get("business_impact_level") or "참고"
            updated_urgency_level = payload["urgency_level"] or article.get("urgency_level") or "low"
            updated_recommended_action = analyzer.apply_feedback_to_action(
                base_action=article.get("recommended_action") or "",
                review_status=str(payload["review_status"]),
                owner_department=article.get("owner_department") or "경영기획",
                impact_level=str(updated_impact_level),
                urgency_level=str(updated_urgency_level),
                comment=str(payload["comment"]) if payload["comment"] else None,
            )

            connection.execute(
                """
                INSERT INTO news_feedback (
                    article_id,
                    feedback_type,
                    is_relevant,
                    is_noise,
                    impact_level,
                    urgency_level,
                    comment,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    payload["feedback_type"],
                    payload["is_relevant"],
                    payload["is_noise"],
                    payload["impact_level"],
                    payload["urgency_level"],
                    payload["comment"],
                    created_at,
                ),
            )
            connection.execute(
                """
                UPDATE news_articles
                SET review_status = ?,
                    business_impact_level = CASE WHEN ? = 1 THEN ? ELSE business_impact_level END,
                    urgency_level = CASE WHEN ? = 1 THEN ? ELSE urgency_level END,
                    recommended_action = ?
                WHERE id = ?
                """,
                (
                    payload["review_status"],
                    payload["is_relevant"],
                    payload["impact_level"],
                    payload["is_relevant"],
                    payload["urgency_level"],
                    updated_recommended_action,
                    article_id,
                ),
            )


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
            "news_impact_options": IMPACT_OPTIONS,
            "news_urgency_options": URGENCY_OPTIONS,
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


@router.get("/api/sync/status")
def sync_status_api():
    return _sync_progress_payload()


@router.post("/api/sync/regulation/start")
def start_regulation_sync_api():
    started = _start_regulation_sync_job()
    payload = _sync_progress_payload()
    return JSONResponse(payload, status_code=202 if started else 200)


@router.post("/api/sync/news/start")
def start_news_sync_api():
    started = _start_news_sync_job()
    payload = _sync_progress_payload()
    return JSONResponse(payload, status_code=202 if started else 200)


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
    _start_regulation_sync_job()
    return RedirectResponse(url="/", status_code=303)


@router.post("/news/sync")
def trigger_news_sync():
    _start_news_sync_job()
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
    impact_level = raw_form.get("impact_level", [""])[0].strip()
    urgency_level = raw_form.get("urgency_level", [""])[0].strip()
    is_relevant, is_noise = _parse_feedback_flags(raw_form)
    comment = raw_form.get("comment", [""])[0].strip()
    return_to = raw_form.get("return_to", ["/"])[0].strip() or "/"
    _record_news_feedback_for_articles(
        article_ids=[article_id],
        impact_level=impact_level,
        urgency_level=urgency_level,
        is_relevant=is_relevant,
        is_noise=is_noise,
        comment=comment or None,
    )
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/news/feedback/bulk")
async def record_news_feedback_bulk(request: Request):
    raw_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    impact_level = raw_form.get("impact_level", [""])[0].strip()
    urgency_level = raw_form.get("urgency_level", [""])[0].strip()
    is_relevant, is_noise = _parse_feedback_flags(raw_form)
    comment = raw_form.get("comment", [""])[0].strip()
    return_to = raw_form.get("return_to", ["/"])[0].strip() or "/"
    article_ids = [int(value) for value in raw_form.get("article_ids", []) if value.strip()]
    _record_news_feedback_for_articles(
        article_ids=article_ids,
        impact_level=impact_level,
        urgency_level=urgency_level,
        is_relevant=is_relevant,
        is_noise=is_noise,
        comment=comment or None,
    )
    return RedirectResponse(url=return_to, status_code=303)
