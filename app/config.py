from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8010"))
    timezone: str = "Asia/Seoul"
    base_dir: Path = BASE_DIR
    db_path: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "seed_reg_monitor.db"))).resolve()
    korean_law_mcp_dir: Path = Path(
        os.getenv("KOREAN_LAW_MCP_DIR", "C:/Users/senak/Downloads/korean-law-mcp-main")
    ).resolve()
    alert_recipients_path: Path = Path(
        os.getenv("ALERT_RECIPIENTS_PATH", str(BASE_DIR / "config" / "alert-recipients.json"))
    ).resolve()
    sample_cases_dir: Path = (BASE_DIR / "docs" / "mvp" / "sample-cases").resolve()
    data_dir: Path = (BASE_DIR / "data").resolve()
    outbox_dir: Path = (BASE_DIR / "data" / "outbox").resolve()
    scheduler_enabled: bool = _as_bool(os.getenv("ENABLE_SCHEDULER"), True)
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None
    smtp_use_tls: bool = _as_bool(os.getenv("SMTP_USE_TLS"), True)
    mail_from: str = os.getenv("MAIL_FROM", "seed-monitor@example.com")


settings = Settings()
