from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import settings
from ..database import get_connection


@dataclass(frozen=True)
class StartupSyncDecision:
    should_run: bool
    message: str
    last_success_at: str | None = None


class StartupSyncPolicyService:
    def should_run_regulation_sync(self) -> StartupSyncDecision:
        interval_hours = settings.regulation_startup_sync_hours
        return self._build_decision(
            last_success_at=self._latest_regulation_success_at(),
            interval=timedelta(hours=interval_hours),
            run_label="규제 자동 동기화를 진행합니다.",
            skip_label=f"최근 {interval_hours}시간 내 규제 동기화 성공 이력이 있어 자동 동기화를 건너뜁니다.",
        )

    def should_run_news_sync(self) -> StartupSyncDecision:
        interval_hours = settings.news_startup_sync_hours
        return self._build_decision(
            last_success_at=self._latest_news_success_at(),
            interval=timedelta(hours=interval_hours),
            run_label="뉴스 자동 동기화를 진행합니다.",
            skip_label=f"최근 {interval_hours}시간 내 뉴스 수집 성공 이력이 있어 자동 동기화를 건너뜁니다.",
        )

    def _build_decision(
        self,
        *,
        last_success_at: str | None,
        interval: timedelta,
        run_label: str,
        skip_label: str,
    ) -> StartupSyncDecision:
        if not last_success_at:
            return StartupSyncDecision(should_run=True, message=run_label, last_success_at=None)

        last_run = datetime.fromisoformat(last_success_at)
        now = datetime.now(ZoneInfo(settings.timezone))
        if now - last_run < interval:
            return StartupSyncDecision(
                should_run=False,
                message=skip_label,
                last_success_at=last_success_at,
            )
        return StartupSyncDecision(
            should_run=True,
            message=run_label,
            last_success_at=last_success_at,
        )

    def _latest_regulation_success_at(self) -> str | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(finished_at, started_at) AS completed_at
                FROM sync_runs
                WHERE status = 'success'
                ORDER BY COALESCE(finished_at, started_at) DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return row["completed_at"] if row else None

    def _latest_news_success_at(self) -> str | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(finished_at, started_at) AS completed_at
                FROM news_collection_logs
                WHERE status = 'success'
                ORDER BY COALESCE(finished_at, started_at) DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return row["completed_at"] if row else None
