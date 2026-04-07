from __future__ import annotations

import unittest

from app.services.sync_progress import SyncProgressService


class SyncProgressServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SyncProgressService()

    def test_begin_update_and_complete_flow(self) -> None:
        started = self.service.begin("regulation", message="준비 중입니다.", total=4)

        self.assertTrue(started)
        self.service.update("regulation", current=2, total=4, message="2건 처리 중입니다.")
        snapshot = self.service.snapshot("regulation")
        self.assertEqual(snapshot["status"], "running")
        self.assertEqual(snapshot["percent"], 50)
        self.assertEqual(snapshot["message"], "2건 처리 중입니다.")

        self.service.complete(
            "regulation",
            message="완료되었습니다.",
            result={"inserted_count": 3},
        )
        completed = self.service.snapshot("regulation")
        self.assertEqual(completed["status"], "success")
        self.assertEqual(completed["percent"], 100)
        self.assertEqual(completed["result"]["inserted_count"], 3)

    def test_begin_returns_false_while_running(self) -> None:
        self.assertTrue(self.service.begin("news", message="시작", total=3))
        self.assertFalse(self.service.begin("news", message="다시 시작", total=3))

    def test_fail_preserves_current_progress(self) -> None:
        self.service.begin("news", message="준비 중", total=5)
        self.service.update("news", current=3, total=5, message="3개 처리 중")

        self.service.fail("news", message="API 오류가 발생했습니다.")
        failed = self.service.snapshot("news")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["current"], 3)
        self.assertEqual(failed["percent"], 60)
        self.assertEqual(failed["message"], "API 오류가 발생했습니다.")


if __name__ == "__main__":
    unittest.main()
