from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from ..config import settings
from .ingestion import IngestionService
from .news_ingestion import NewsIngestionService


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        IngestionService().run,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=5, timezone=ZoneInfo(settings.timezone)),
        id="weekday-regulation-sync",
        replace_existing=True,
        kwargs={"lookback_days": settings.regulation_sync_lookback_days},
    )
    news_service = NewsIngestionService()
    if news_service.is_configured():
        scheduler.add_job(
            news_service.run,
            CronTrigger(
                day_of_week="mon-fri",
                hour=settings.news_scheduler_hour,
                minute=settings.news_scheduler_minute,
                timezone=ZoneInfo(settings.timezone),
            ),
            id="weekday-news-sync",
            replace_existing=True,
            kwargs={"run_type": "scheduled"},
        )
    return scheduler
