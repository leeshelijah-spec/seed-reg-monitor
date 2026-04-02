from __future__ import annotations

import json
import tempfile
import unittest
import asyncio
from pathlib import Path

from app import main as main_module
from app.config import settings
from app.database import get_connection, init_db


class ReadOnlyModeTest(unittest.TestCase):
    def _request(self, method: str, path: str) -> tuple[int, str, dict[str, str]]:
        async def run_request() -> tuple[int, str, dict[str, str]]:
            body_parts: list[bytes] = []
            response_status = 500
            response_headers: dict[str, str] = {}
            received = False

            async def receive():
                nonlocal received
                if received:
                    await asyncio.sleep(0)
                    return {"type": "http.disconnect"}
                received = True
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                nonlocal response_status, response_headers
                if message["type"] == "http.response.start":
                    response_status = message["status"]
                    response_headers = {
                        key.decode("latin-1"): value.decode("latin-1")
                        for key, value in message.get("headers", [])
                    }
                elif message["type"] == "http.response.body":
                    body_parts.append(message.get("body", b""))

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "root_path": "",
                "headers": [(b"host", b"testserver")],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "app": main_module.app,
            }

            await main_module.app(scope, receive, send)
            return response_status, b"".join(body_parts).decode("utf-8"), response_headers

        return asyncio.run(run_request())

    def setUp(self) -> None:
        self.original_db_path = settings.db_path
        self.original_read_only_mode = settings.read_only_mode
        self.original_scheduler = main_module.scheduler
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db_path = Path(self.temp_dir.name) / "test.db"

        object.__setattr__(settings, "db_path", temp_db_path)
        object.__setattr__(settings, "read_only_mode", True)
        main_module.scheduler = None

        init_db()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO regulations (
                    id, title, type, authority, publication_date, effective_date, source_url,
                    summary, amendment_reason, category, department, severity,
                    relevance_reason, severity_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "Shared View Regulation",
                    "law",
                    "Seed Authority",
                    "2026-04-02",
                    "2026-05-01",
                    "https://example.com/regulations/1",
                    "Summary",
                    "Amendment reason",
                    json.dumps(["Category"]),
                    json.dumps(["Dept"]),
                    "high",
                    "Relevant",
                    "Important",
                    "2026-04-02T09:00:00+09:00",
                ),
            )

    def tearDown(self) -> None:
        object.__setattr__(settings, "db_path", self.original_db_path)
        object.__setattr__(settings, "read_only_mode", self.original_read_only_mode)
        main_module.scheduler = self.original_scheduler
        self.temp_dir.cleanup()

    def test_dashboard_hides_write_forms_in_read_only_mode(self) -> None:
        status_code, body, _ = self._request("GET", "/")

        self.assertEqual(status_code, 200)
        self.assertNotIn('action="/sync"', body)
        self.assertNotIn('action="/news/sync"', body)
        self.assertNotIn('action="/news/keywords"', body)
        self.assertNotIn("/news/1/feedback", body)

    def test_detail_page_hides_review_form_in_read_only_mode(self) -> None:
        status_code, body, _ = self._request("GET", "/regulations/1")

        self.assertEqual(status_code, 200)
        self.assertNotIn('action="/regulations/1/review"', body)

    def test_write_requests_are_blocked_in_read_only_mode(self) -> None:
        status_code, body, headers = self._request("POST", "/sync")

        self.assertEqual(status_code, 403)
        self.assertEqual(headers.get("content-type"), "application/json")
        self.assertEqual(
            json.loads(body),
            {"detail": "Read-only mode is enabled. Write operations are blocked."},
        )


if __name__ == "__main__":
    unittest.main()
