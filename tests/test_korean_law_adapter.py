from __future__ import annotations

import unittest

from app.services.korean_law_adapter import FALLBACK_LOOKBACK_DAYS, KoreanLawAdapter


class _FallbackAdapter(KoreanLawAdapter):
    def __init__(self) -> None:
        self.calls: list[int] = []

    def _collect_recent_items(self, lookback_days: int) -> list[dict]:
        self.calls.append(lookback_days)
        if len(self.calls) == 1:
            return []
        return [{"source_url": "https://example.com/reg-1"}]


class _NoFallbackAdapter(KoreanLawAdapter):
    def __init__(self) -> None:
        self.calls: list[int] = []

    def _collect_recent_items(self, lookback_days: int) -> list[dict]:
        self.calls.append(lookback_days)
        return [{"source_url": "https://example.com/reg-1"}]


class KoreanLawAdapterFallbackTest(unittest.TestCase):
    def test_extends_lookback_when_initial_window_has_no_results(self) -> None:
        adapter = _FallbackAdapter()

        items = adapter.fetch_recent_items(lookback_days=14)

        self.assertEqual(len(items), 1)
        self.assertEqual(adapter.calls, [14, FALLBACK_LOOKBACK_DAYS])

    def test_keeps_single_pass_when_results_exist(self) -> None:
        adapter = _NoFallbackAdapter()

        items = adapter.fetch_recent_items(lookback_days=14)

        self.assertEqual(len(items), 1)
        self.assertEqual(adapter.calls, [14])


if __name__ == "__main__":
    unittest.main()
