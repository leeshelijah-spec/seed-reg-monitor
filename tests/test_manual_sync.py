from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from app.manual_sync import StartupSyncProgressReporter


class StartupSyncProgressReporterTest(unittest.TestCase):
    def test_regulation_progress_rewrites_single_line(self) -> None:
        reporter = StartupSyncProgressReporter()
        output = io.StringIO()

        with redirect_stdout(output):
            reporter.regulation_progress(2, 4, "규제 절반을 처리했습니다.")

        rendered = output.getvalue()
        self.assertTrue(rendered.startswith("\r[startup sync]"))
        self.assertIn("전체  25%", rendered)
        self.assertIn("규제  50%", rendered)
        self.assertIn("규제 절반을 처리했습니다.", rendered)
        self.assertFalse(rendered.endswith("\n"))

    def test_finish_line_adds_single_newline(self) -> None:
        reporter = StartupSyncProgressReporter()
        output = io.StringIO()

        with redirect_stdout(output):
            reporter.news_progress(3, 3, "뉴스 수집이 완료되었습니다.")
            reporter.finish_line()

        rendered = output.getvalue()
        self.assertIn("전체 100%", rendered)
        self.assertIn("뉴스 100%", rendered)
        self.assertTrue(rendered.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
