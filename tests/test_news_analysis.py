from __future__ import annotations

import unittest

from app.services.news_analysis import NewsAnalysisService


class NewsAnalysisServiceTest(unittest.TestCase):
    def test_regulatory_article_is_classified_with_high_impact(self) -> None:
        result = NewsAnalysisService().analyze(
            {
                "title": "종자 수입 검역 강화로 통관 검사 확대",
                "summary": "검역 강화와 검사 확대가 발표되며 수입 일정 차질 가능성이 제기됐다.",
            },
            matched_keywords=["종자 수입"],
        )

        self.assertEqual(result.topic_category, "수출입·검역")
        self.assertIn(result.business_impact_level, {"중요", "즉시조치"})
        self.assertGreaterEqual(result.relevance_score, 60)
        self.assertEqual(result.owner_department, "품질")

    def test_feedback_action_is_reflected_in_recommended_action(self) -> None:
        service = NewsAnalysisService()
        updated_action = service.apply_feedback_to_action(
            base_action="품질에서 기사 원문을 검토하세요.",
            review_status="관련",
            owner_department="품질",
            impact_level="중요",
            urgency_level="high",
            comment="수입 일정 영향 여부를 주간회의에서 검토",
        )

        self.assertIn("관련 기사로 확인", updated_action)
        self.assertIn("피드백 조치사항: 수입 일정 영향 여부를 주간회의에서 검토", updated_action)


if __name__ == "__main__":
    unittest.main()
