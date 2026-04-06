from __future__ import annotations

import unittest

from app.services.news_dashboard import NewsDashboardService


def _article(
    *,
    article_id: int,
    title: str,
    keyword: str,
    source_title: str,
    published_at: str,
    summary: str = "",
    topic_category: str = "수출입·검역",
    impact: str = "중요",
    urgency: str = "high",
    review_status: str = "미검토",
    relevance_score: int = 80,
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "keyword": keyword,
        "source_title": source_title,
        "summary": summary,
        "published_at": published_at,
        "collected_at": published_at,
        "matched_keywords": [keyword],
        "topic_category": topic_category,
        "business_impact_level": impact,
        "urgency_level": urgency,
        "review_status": review_status,
        "relevance_score": relevance_score,
        "recommended_action": "check",
        "original_link": f"https://example.com/{article_id}",
    }


class NewsDashboardGroupingTest(unittest.TestCase):
    def test_groups_related_articles_and_keeps_unrelated_separate(self) -> None:
        service = NewsDashboardService()
        groups = service._group_articles(
            [
                _article(
                    article_id=1,
                    title="종자산업 수출 확대 위해 검역 능력 강화",
                    keyword="종자산업",
                    source_title="news-a.example.com",
                    published_at="2026-04-06T12:00:00+09:00",
                ),
                _article(
                    article_id=2,
                    title="검역 능력 강화로 종자산업 수출 확대 기대",
                    keyword="종자산업",
                    source_title="news-b.example.com",
                    published_at="2026-04-06T11:30:00+09:00",
                    relevance_score=77,
                ),
                _article(
                    article_id=3,
                    title="토마토 가격 급등으로 외식 물가 부담 확대",
                    keyword="토마토",
                    source_title="news-c.example.com",
                    published_at="2026-04-06T10:00:00+09:00",
                    topic_category="시장수급",
                    impact="참고",
                    urgency="low",
                    relevance_score=51,
                ),
            ]
        )

        self.assertEqual(len(groups), 2)
        grouped = next(group for group in groups if set(group["article_ids"]) == {1, 2})
        solo = next(group for group in groups if group["article_ids"] == [3])

        self.assertEqual(grouped["related_count"], 1)
        self.assertEqual(grouped["total_count"], 2)
        self.assertEqual(grouped["source_count"], 2)
        self.assertEqual(grouped["matched_keywords"], ["종자산업"])
        self.assertEqual(solo["related_count"], 0)
        self.assertEqual(solo["total_count"], 1)

    def test_groups_same_issue_with_spacing_variants_and_summary_overlap(self) -> None:
        service = NewsDashboardService()
        groups = service._group_articles(
            [
                _article(
                    article_id=10,
                    title="유럽서도 AI 인체감염...\"가금류·길고양이 접촉 피해야\"",
                    keyword="검역",
                    source_title="news-a.example.com",
                    published_at="2026-04-06T12:00:00+09:00",
                    summary="유럽 AI 인체 감염 사례로 가금류와 길고양이 접촉을 자제해야 한다고 안내했다.",
                    topic_category="기후·병해충",
                    impact="검토필요",
                    urgency="medium",
                    relevance_score=60,
                ),
                _article(
                    article_id=11,
                    title="질병청 \"유럽서도 AI 인체 감염…가금류·길고양이 접촉 자제해야\"",
                    keyword="검역",
                    source_title="news-b.example.com",
                    published_at="2026-04-06T11:50:00+09:00",
                    summary="질병청은 가금류, 길고양이와 접촉을 줄이고 AI 인체감염 사례를 예의주시하라고 밝혔다.",
                    topic_category="수출입·검역",
                    impact="참고",
                    urgency="low",
                    relevance_score=59,
                ),
            ]
        )

        self.assertEqual(len(groups), 1)
        grouped = groups[0]
        self.assertEqual(set(grouped["article_ids"]), {10, 11})
        self.assertEqual(grouped["related_count"], 1)


if __name__ == "__main__":
    unittest.main()
