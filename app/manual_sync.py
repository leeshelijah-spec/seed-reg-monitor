from __future__ import annotations

import sys

from .config import settings
from .database import init_db
from .services.ingestion import IngestionService
from .services.news_ingestion import NewsIngestionService
from .services.startup_sync_policy import StartupSyncPolicyService


class StartupSyncProgressReporter:
    def __init__(self) -> None:
        self._last_signature: tuple[str, int, str] | None = None
        self._last_line_length = 0
        self._line_open = False

    def regulation_progress(self, current: int, total: int, message: str) -> None:
        self._render_progress(
            phase="규제",
            phase_progress=self._percent(current, total),
            overall_progress=self._blend_progress(current=current, total=total, start=0, end=50),
            message=message,
        )

    def news_progress(self, current: int, total: int, message: str) -> None:
        self._render_progress(
            phase="뉴스",
            phase_progress=self._percent(current, total),
            overall_progress=self._blend_progress(current=current, total=total, start=50, end=100),
            message=message,
        )

    @staticmethod
    def _percent(current: int, total: int) -> int:
        safe_total = max(total, 1)
        bounded_current = max(0, min(current, safe_total))
        return int(round((bounded_current / safe_total) * 100))

    def _blend_progress(self, *, current: int, total: int, start: int, end: int) -> int:
        phase_percent = self._percent(current, total)
        return start + int(round(((end - start) * phase_percent) / 100))

    def _render_progress(self, *, phase: str, phase_progress: int, overall_progress: int, message: str) -> None:
        signature = (phase, overall_progress, message)
        if signature == self._last_signature:
            return
        self._last_signature = signature

        line = (
            f"[startup sync] [{self._gauge(overall_progress)}] "
            f"전체 {overall_progress:>3}% | {phase} {phase_progress:>3}% | {message}"
        )
        padding = max(0, self._last_line_length - len(line))
        sys.stdout.write(f"\r{line}{' ' * padding}")
        sys.stdout.flush()
        self._last_line_length = len(line)
        self._line_open = True

    def finish_line(self) -> None:
        if not self._line_open:
            return
        sys.stdout.write("\n")
        sys.stdout.flush()
        self._line_open = False

    @staticmethod
    def _gauge(percent: int, width: int = 20) -> str:
        filled = max(0, min(width, int(round((percent / 100) * width))))
        return f"{'#' * filled}{'-' * (width - filled)}"


def main() -> None:
    init_db()
    reporter = StartupSyncProgressReporter()
    policy = StartupSyncPolicyService()
    print("[startup sync] 초기 동기화를 시작합니다.")

    regulation_decision = policy.should_run_regulation_sync()
    if regulation_decision.should_run:
        regulation_result = IngestionService().run(
            lookback_days=settings.regulation_sync_lookback_days,
            progress_callback=reporter.regulation_progress,
        )
    else:
        reporter.regulation_progress(1, 1, regulation_decision.message)
        regulation_result = {
            "status": "skipped",
            "reason": regulation_decision.message,
            "last_success_at": regulation_decision.last_success_at,
        }
    reporter.finish_line()
    print({"regulations": regulation_result})

    news_service = NewsIngestionService()
    if news_service.is_configured():
        news_decision = policy.should_run_news_sync()
        if news_decision.should_run:
            news_result = news_service.run(
                run_type="manual",
                progress_callback=reporter.news_progress,
            )
        else:
            reporter.news_progress(1, 1, news_decision.message)
            news_result = {
                "status": "skipped",
                "reason": news_decision.message,
                "last_success_at": news_decision.last_success_at,
            }
        reporter.finish_line()
        print({"news": news_result})
    else:
        reporter.news_progress(1, 1, "뉴스 API 설정이 없어 뉴스 수집을 건너뜁니다.")
        reporter.finish_line()
        print({"news": "skipped: NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not configured"})

    print("[startup sync] 초기 동기화가 끝났습니다.")


if __name__ == "__main__":
    main()
