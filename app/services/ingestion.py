from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings
from ..database import get_connection
from .alerts import AlertService
from .classifier import RegulationClassifier
from .korean_law_adapter import KoreanLawAdapter


class IngestionService:
    def __init__(self) -> None:
        self.adapter = KoreanLawAdapter()
        self.classifier = RegulationClassifier()
        self.alerts = AlertService()

    def run(self, lookback_days: int = 5) -> dict:
        started_at = datetime.now(ZoneInfo(settings.timezone)).isoformat()
        sync_run_id = self._start_sync_run(started_at)
        inserted: list[dict] = []
        collected_count = 0
        status = "success"
        message = "ok"

        try:
            raw_items = self.adapter.fetch_recent_items(lookback_days=lookback_days)
            collected_count = len(raw_items)
            for item in raw_items:
                classification = self.classifier.classify(item)
                if not classification:
                    continue

                enriched = {
                    **item,
                    "amendment_reason": item.get("amendment_reason") or item.get("summary"),
                    "category": classification.category,
                    "department": classification.department,
                    "severity": classification.severity,
                    "relevance_reason": classification.relevance_reason,
                    "severity_reason": classification.severity_reason,
                    "created_at": started_at,
                }
                if self._upsert_regulation(enriched):
                    inserted.append(enriched)

            self.alerts.send_for_regulations(inserted)
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            message = str(exc)
            raise
        finally:
            finished_at = datetime.now(ZoneInfo(settings.timezone)).isoformat()
            self._finish_sync_run(sync_run_id, finished_at, status, collected_count, len(inserted), message)

        return {
            "started_at": started_at,
            "collected_count": collected_count,
            "inserted_count": len(inserted),
            "inserted": inserted,
        }

    def _upsert_regulation(self, item: dict) -> bool:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT id FROM regulations WHERE source_url = ?",
                (item["source_url"],),
            ).fetchone()

            if existing:
                connection.execute(
                    """
                    UPDATE regulations
                    SET title=?, type=?, authority=?, publication_date=?, effective_date=?, summary=?,
                        amendment_reason=?, category=?, department=?, severity=?, relevance_reason=?, severity_reason=?
                    WHERE source_url=?
                    """,
                    (
                        item["title"],
                        item["type"],
                        item["authority"],
                        item["publication_date"],
                        item["effective_date"],
                        item["summary"],
                        item["amendment_reason"],
                        json.dumps(item["category"], ensure_ascii=False),
                        json.dumps(item["department"], ensure_ascii=False),
                        item["severity"],
                        item["relevance_reason"],
                        item["severity_reason"],
                        item["source_url"],
                    ),
                )
                return False

            connection.execute(
                """
                INSERT INTO regulations (
                    title, type, authority, publication_date, effective_date, source_url,
                    summary, amendment_reason, category, department, severity,
                    relevance_reason, severity_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["title"],
                    item["type"],
                    item["authority"],
                    item["publication_date"],
                    item["effective_date"],
                    item["source_url"],
                    item["summary"],
                    item["amendment_reason"],
                    json.dumps(item["category"], ensure_ascii=False),
                    json.dumps(item["department"], ensure_ascii=False),
                    item["severity"],
                    item["relevance_reason"],
                    item["severity_reason"],
                    item["created_at"],
                ),
            )
        return True

    def _start_sync_run(self, started_at: str) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO sync_runs (started_at, status) VALUES (?, ?)",
                (started_at, "running"),
            )
            return int(cursor.lastrowid)

    def _finish_sync_run(
        self,
        sync_run_id: int,
        finished_at: str,
        status: str,
        collected_count: int,
        inserted_count: int,
        message: str,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at=?, status=?, collected_count=?, inserted_count=?, message=?
                WHERE id=?
                """,
                (finished_at, status, collected_count, inserted_count, message, sync_run_id),
            )
