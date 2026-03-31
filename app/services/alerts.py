from __future__ import annotations

import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import settings


class AlertService:
    def __init__(self) -> None:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)

    def send_for_regulations(self, regulations: list[dict]) -> None:
        alertable = [item for item in regulations if item["severity"] in {"긴급", "중요"}]
        if not alertable:
            return

        recipients = self._load_recipients()
        if not recipients:
            return

        if settings.smtp_host:
            for regulation in alertable:
                self._send_email(recipients, regulation)
        else:
            self._write_preview(recipients, alertable)

    def _load_recipients(self) -> list[str]:
        config = json.loads(settings.alert_recipients_path.read_text(encoding="utf-8"))
        recipients: list[str] = []
        for rule in config.get("rules", []):
            if not rule.get("enabled"):
                continue
            if not set(rule.get("severity", [])) & {"긴급", "중요"}:
                continue
            for recipient in rule.get("recipients", []):
                if recipient not in recipients:
                    recipients.append(recipient)
        return recipients

    def _send_email(self, recipients: list[str], regulation: dict) -> None:
        message = EmailMessage()
        message["Subject"] = f"[Seed Regulation Monitor] {regulation['severity']} - {regulation['title']}"
        message["From"] = settings.mail_from
        message["To"] = ", ".join(recipients)
        message.set_content(
            "\n".join(
                [
                    f"제목: {regulation['title']}",
                    f"요약: {regulation['summary']}",
                    f"시행일: {regulation.get('effective_date') or '미정'}",
                    f"링크: {regulation['source_url']}",
                ]
            )
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)

    def _write_preview(self, recipients: list[str], regulations: list[dict]) -> None:
        payload = {
            "generated_at": datetime.now(ZoneInfo(settings.timezone)).isoformat(),
            "recipients": recipients,
            "items": [
                {
                    "title": item["title"],
                    "summary": item["summary"],
                    "effective_date": item.get("effective_date"),
                    "link": item["source_url"],
                    "severity": item["severity"],
                }
                for item in regulations
            ],
        }
        stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y%m%d-%H%M%S")
        output_path = Path(settings.outbox_dir) / f"alerts-{stamp}.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
