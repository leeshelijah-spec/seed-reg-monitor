from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from ..config import settings
from .ingestion import IngestionService


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        IngestionService().run,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=5, timezone=ZoneInfo(settings.timezone)),
        id="weekday-regulation-sync",
        replace_existing=True,
        kwargs={"lookback_days": 3},
    )
    return scheduler
