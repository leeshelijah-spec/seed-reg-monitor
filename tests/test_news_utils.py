from __future__ import annotations

import unittest

from app.services.news_utils import normalize_link, parse_naver_pub_date, strip_html_markup


class NewsUtilsTest(unittest.TestCase):
    def test_strip_html_markup_removes_b_tags(self) -> None:
        self.assertEqual(strip_html_markup("<b>종자</b> 수출 확대"), "종자 수출 확대")

    def test_normalize_link_keeps_scheme_host_path_and_query(self) -> None:
        self.assertEqual(
            normalize_link("HTTPS://Example.com/news?id=1#anchor"),
            "https://example.com/news?id=1",
        )

    def test_parse_naver_pub_date_returns_iso(self) -> None:
        parsed = parse_naver_pub_date("Wed, 02 Apr 2026 09:00:00 +0900")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.startswith("2026-04-02T09:00:00"))


if __name__ == "__main__":
    unittest.main()
