from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..database import get_connection, row_to_regulation
from ..services.ingestion import IngestionService


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
ACTION_STATUS_OPTIONS = ("미확인", "조치필요", "조치중", "조치완료", "해당없음")


@router.get("/")
def dashboard(request: Request):
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
        recent_rows = connection.execute(
            """
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
            ORDER BY r.created_at DESC, r.publication_date DESC
            LIMIT 20
            """
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

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stats": {
                "today_new_count": today_new_count,
                "unreviewed_count": unreviewed_count,
                "imminent_count": imminent_count,
            },
            "severity_distribution": [
                {"label": row["severity"], "value": row["count"]} for row in severity_rows
            ],
            "recent_regulations": recent_regulations,
            "latest_sync": dict(latest_sync) if latest_sync else None,
        },
    )


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
