from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_settings_env() -> None:
    merged_values: dict[str, str | None] = {
        **dotenv_values(BASE_DIR / ".env"),
        **dotenv_values(BASE_DIR / ".env.local"),
    }

    for key, value in merged_values.items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


_load_settings_env()


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_korean_law_build(path: Path) -> bool:
    return (path / "build" / "lib" / "api-client.js").exists()


def _resolve_korean_law_mcp_dir(raw_value: str | None) -> Path:
    candidates: list[Path] = []

    if raw_value:
        candidates.append(Path(raw_value).expanduser())

    candidates.extend(
        [
            BASE_DIR / "external" / "korean-law-mcp",
            BASE_DIR.parent / "korean-law-mcp",
            BASE_DIR.parent / "korean-law-mcp-main",
            BASE_DIR.parent.parent / "korean-law-mcp",
            BASE_DIR.parent.parent / "korean-law-mcp-main",
            Path.home() / "Downloads" / "korean-law-mcp",
            Path.home() / "Downloads" / "korean-law-mcp-main",
        ]
    )

    seen: set[Path] = set()
    normalized_candidates: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        normalized_candidates.append(resolved)

    for candidate in normalized_candidates:
        if _has_korean_law_build(candidate):
            return candidate

    return normalized_candidates[0]


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8010"))
    read_only_mode: bool = _as_bool(os.getenv("READ_ONLY_MODE"), False)
    timezone: str = "Asia/Seoul"
    base_dir: Path = BASE_DIR
    db_path: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "seed_reg_monitor.db"))).resolve()
    korean_law_mcp_dir: Path = _resolve_korean_law_mcp_dir(os.getenv("KOREAN_LAW_MCP_DIR"))
    alert_recipients_path: Path = Path(
        os.getenv("ALERT_RECIPIENTS_PATH", str(BASE_DIR / "config" / "alert-recipients.json"))
    ).resolve()
    news_keywords_path: Path = Path(
        os.getenv("NEWS_KEYWORDS_PATH", str(BASE_DIR / "config" / "news-keywords.json"))
    ).resolve()
    sample_cases_dir: Path = (BASE_DIR / "docs" / "mvp" / "sample-cases").resolve()
    data_dir: Path = (BASE_DIR / "data").resolve()
    outbox_dir: Path = (BASE_DIR / "data" / "outbox").resolve()
    scheduler_enabled: bool = _as_bool(os.getenv("ENABLE_SCHEDULER"), True)
    naver_client_id: str | None = os.getenv("NAVER_CLIENT_ID") or None
    naver_client_secret: str | None = os.getenv("NAVER_CLIENT_SECRET") or None
    naver_news_display: int = int(os.getenv("NAVER_NEWS_DISPLAY", "10"))
    naver_news_sort: str = os.getenv("NAVER_NEWS_SORT", "date")
    naver_news_max_retries: int = int(os.getenv("NAVER_NEWS_MAX_RETRIES", "3"))
    naver_news_timeout: int = int(os.getenv("NAVER_NEWS_TIMEOUT", "15"))
    news_scheduler_hour: int = int(os.getenv("NEWS_SCHEDULER_HOUR", "8"))
    news_scheduler_minute: int = int(os.getenv("NEWS_SCHEDULER_MINUTE", "40"))
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None
    smtp_use_tls: bool = _as_bool(os.getenv("SMTP_USE_TLS"), True)
    mail_from: str = os.getenv("MAIL_FROM", "seed-monitor@example.com")


settings = Settings()
