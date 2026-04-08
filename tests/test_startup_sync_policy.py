from __future__ import annotations

import shutil
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings
from app.services.startup_sync_policy import StartupSyncPolicyService


class StartupSyncPolicyServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_db_path = settings.db_path
        self.original_regulation_hours = settings.regulation_startup_sync_hours
        self.original_news_hours = settings.news_startup_sync_hours
        self.temp_root = Path("C:/PJT/seed-reg-monitor/tests/.tmp/startup-sync-policy")
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_db_path = self.temp_root / "test.db"
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()
        object.__setattr__(settings, "db_path", self.temp_db_path)

        connection = sqlite3.connect(self.temp_db_path)
        connection.execute(
            """
            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                collected_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                message TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE news_collection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                run_type TEXT NOT NULL DEFAULT 'scheduled',
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                message TEXT
            )
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        object.__setattr__(settings, "db_path", self.original_db_path)
        object.__setattr__(settings, "regulation_startup_sync_hours", self.original_regulation_hours)
        object.__setattr__(settings, "news_startup_sync_hours", self.original_news_hours)
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_regulation_sync_is_skipped_when_recent_success_exists(self) -> None:
        object.__setattr__(settings, "regulation_startup_sync_hours", 12)
        recent = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(hours=6)).isoformat()
        connection = sqlite3.connect(self.temp_db_path)
        connection.execute(
            "INSERT INTO sync_runs (started_at, finished_at, status) VALUES (?, ?, 'success')",
            (recent, recent),
        )
        connection.commit()
        connection.close()

        decision = StartupSyncPolicyService().should_run_regulation_sync()

        self.assertFalse(decision.should_run)
        self.assertIn("12시간", decision.message)

    def test_regulation_sync_runs_when_last_success_is_old(self) -> None:
        object.__setattr__(settings, "regulation_startup_sync_hours", 12)
        older = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(hours=13)).isoformat()
        connection = sqlite3.connect(self.temp_db_path)
        connection.execute(
            "INSERT INTO sync_runs (started_at, finished_at, status) VALUES (?, ?, 'success')",
            (older, older),
        )
        connection.commit()
        connection.close()

        decision = StartupSyncPolicyService().should_run_regulation_sync()

        self.assertTrue(decision.should_run)

    def test_news_sync_is_skipped_when_recent_success_exists(self) -> None:
        object.__setattr__(settings, "news_startup_sync_hours", 3)
        recent = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(hours=2)).isoformat()
        connection = sqlite3.connect(self.temp_db_path)
        connection.execute(
            "INSERT INTO news_collection_logs (keyword, status, started_at, finished_at) VALUES ('토마토', 'success', ?, ?)",
            (recent, recent),
        )
        connection.commit()
        connection.close()

        decision = StartupSyncPolicyService().should_run_news_sync()

        self.assertFalse(decision.should_run)
        self.assertIn("3시간", decision.message)

    def test_news_sync_runs_when_no_recent_success_exists(self) -> None:
        object.__setattr__(settings, "news_startup_sync_hours", 3)
        older = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(hours=5)).isoformat()
        connection = sqlite3.connect(self.temp_db_path)
        connection.execute(
            "INSERT INTO news_collection_logs (keyword, status, started_at, finished_at) VALUES ('토마토', 'success', ?, ?)",
            (older, older),
        )
        connection.commit()
        connection.close()

        decision = StartupSyncPolicyService().should_run_news_sync()

        self.assertTrue(decision.should_run)


if __name__ == "__main__":
    unittest.main()
