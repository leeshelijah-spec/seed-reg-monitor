from __future__ import annotations

import unittest

from app.services.news_analysis import NewsAnalysisService


class NewsAnalysisServiceTest(unittest.TestCase):
    def test_regulatory_article_is_classified_with_high_impact(self) -> None:
        result = NewsAnalysisService().analyze(
            {
                "title": "종자 수입 검역 강화로 통관 지연 우려",
                "summary": "검역 강화와 통관 지연 가능성이 발표되며 수입 일정 차질 가능성이 제기됐다.",
            },
            matched_keywords=["종자 수입"],
        )

        self.assertEqual(result.topic_category, "수출입·검역")
        self.assertIn(result.business_impact_level, {"중요", "즉시조치"})
        self.assertGreaterEqual(result.relevance_score, 60)
        self.assertEqual(result.owner_department, "품질")
        self.assertEqual(result.review_status, "미검토")

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

    def test_sports_article_is_classified_as_noise(self) -> None:
        result = NewsAnalysisService().analyze(
            {
                "title": "프로축구 개막전, 토마토 구단 3대2 승리",
                "summary": "선수 득점과 감독 인터뷰가 화제가 된 경기 기사다.",
            },
            matched_keywords=["토마토"],
        )

        self.assertEqual(result.review_status, "잡음")
        self.assertEqual(result.relevance_score, 0)
        self.assertEqual(result.urgency_level, "low")
        self.assertTrue(result.analysis_trace["sports_noise"])
        self.assertIn("자동 제외", result.recommended_action)


if __name__ == "__main__":
    unittest.main()
