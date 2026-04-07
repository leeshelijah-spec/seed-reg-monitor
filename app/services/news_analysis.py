from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TOPIC_RULES = {
    "규제/정책": ["법", "정책", "지침", "규제", "개정", "보호", "등록", "허가", "보조금"],
    "시장수급": ["가격", "수급", "공급", "생산량", "재배면적", "물량", "매출", "수요", "품절"],
    "경쟁사동향": ["출시", "신작", "투자", "법인", "파트너십", "인수", "브랜드", "기업"],
    "기술·품종": ["품종", "육종", "종자", "기술", "유전", "신품종", "채종", "육묘"],
    "수출입·검역": ["수출", "수입", "검역", "통관", "관세", "검사", "방역", "해외"],
    "기후·병해충": ["폭염", "한파", "가뭄", "병해충", "바이러스", "피해", "기후", "재해"],
    "소비트렌드": ["소비", "선호", "프리미엄", "간편식", "친환경", "온라인", "트렌드", "유통"],
    "평판리스크": ["리콜", "불매", "피해", "위반", "불만", "허위", "제재", "안전성"],
}

OWNER_BY_CATEGORY = {
    "규제/정책": "법무",
    "시장수급": "경영기획",
    "경쟁사동향": "영업",
    "기술·품종": "연구",
    "수출입·검역": "품질",
    "기후·병해충": "생산",
    "소비트렌드": "영업",
    "평판리스크": "경영기획",
}

IMMEDIATE_TERMS = ["철수", "중단", "금지", "리콜", "검출", "급등", "확산", "긴급", "비상"]
IMPORTANT_TERMS = ["영향", "품절", "위반", "부족", "차질", "강화", "투자", "수출", "수입"]
SEED_BUSINESS_TERMS = [
    "종자",
    "육묘",
    "채종",
    "품종",
    "채소",
    "검역",
    "병해충",
    "재배",
    "농가",
    "수출",
    "수입",
]
SPORTS_TERMS = [
    "스포츠",
    "축구",
    "야구",
    "농구",
    "배구",
    "골프",
    "리그",
    "개막전",
    "승리",
    "패배",
    "무승부",
    "득점",
    "결승골",
    "홈런",
    "투수",
    "타자",
    "선수",
    "감독",
    "구단",
    "경기",
    "라운드",
    "토너먼트",
    "챔피언십",
    "우승",
]

UNREVIEWED_STATUS = "미검토"
RELEVANT_STATUS = "관련"
NOISE_STATUS = "잡음"
URGENCY_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}


@dataclass
class NewsAnalysisResult:
    topic_category: str
    business_impact_level: str
    urgency_level: str
    relevance_score: int
    recommended_action: str
    owner_department: str
    review_status: str
    analysis_trace: dict[str, Any]


class NewsAnalysisService:
    def analyze(self, article: dict[str, Any], matched_keywords: list[str]) -> NewsAnalysisResult:
        title = article.get("title", "")
        summary = article.get("summary", "")
        full_text = f"{title}\n{summary}".lower()

        sports_noise, sports_hits, domain_hits = self._detect_sports_noise(full_text)
        if sports_noise:
            owner_department = OWNER_BY_CATEGORY["평판리스크"]
            return NewsAnalysisResult(
                topic_category="평판리스크",
                business_impact_level="참고",
                urgency_level="low",
                relevance_score=0,
                recommended_action=self.apply_feedback_to_action(
                    base_action="",
                    review_status=NOISE_STATUS,
                    owner_department=owner_department,
                    impact_level="참고",
                    urgency_level="low",
                    comment="스포츠 경기 기사로 판단되어 자동 제외되었습니다.",
                ),
                owner_department=owner_department,
                review_status=NOISE_STATUS,
                analysis_trace={
                    "rule_hits": {
                        "sports_hits": sports_hits,
                        "domain_hits": domain_hits,
                        "matched_keywords": matched_keywords,
                    },
                    "llm_refinement": self._llm_trace(),
                    "sports_noise": True,
                },
            )

        category_scores: dict[str, int] = {}
        for category, keywords in TOPIC_RULES.items():
            hits = sum(1 for keyword in keywords if keyword.lower() in full_text)
            if hits:
                category_scores[category] = hits

        if not category_scores:
            category_scores["시장수급"] = 1

        topic_category = sorted(category_scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
        impact_level, urgency_level, impact_hits = self._score_impact(full_text, topic_category)
        relevance_score = self._score_relevance(full_text, matched_keywords, category_scores[topic_category])
        owner_department = OWNER_BY_CATEGORY.get(topic_category, "경영기획")
        recommended_action = self._build_recommended_action(
            topic_category=topic_category,
            impact_level=impact_level,
            urgency_level=urgency_level,
            matched_keywords=matched_keywords,
            owner_department=owner_department,
        )

        analysis_trace = {
            "rule_hits": {
                "category_scores": category_scores,
                "impact_hits": impact_hits,
                "matched_keywords": matched_keywords,
            },
            "llm_refinement": self._llm_trace(),
            "sports_noise": False,
        }
        return NewsAnalysisResult(
            topic_category=topic_category,
            business_impact_level=impact_level,
            urgency_level=urgency_level,
            relevance_score=relevance_score,
            recommended_action=recommended_action,
            owner_department=owner_department,
            review_status=UNREVIEWED_STATUS,
            analysis_trace=analysis_trace,
        )

    def _score_impact(self, full_text: str, topic_category: str) -> tuple[str, str, dict[str, int]]:
        immediate_hits = sum(term in full_text for term in IMMEDIATE_TERMS)
        important_hits = sum(term in full_text for term in IMPORTANT_TERMS)
        category_bonus = 1 if topic_category in {"규제/정책", "수출입·검역", "기후·병해충"} else 0
        score = immediate_hits * 3 + important_hits * 2 + category_bonus

        if score >= 6:
            return "즉시조치", "high", {"immediate": immediate_hits, "important": important_hits, "score": score}
        if score >= 4:
            urgency = "high" if immediate_hits else "medium"
            return "중요", urgency, {"immediate": immediate_hits, "important": important_hits, "score": score}
        if score >= 2:
            return "검토필요", "medium", {"immediate": immediate_hits, "important": important_hits, "score": score}
        return "참고", "low", {"immediate": immediate_hits, "important": important_hits, "score": score}

    def _score_relevance(self, full_text: str, matched_keywords: list[str], category_score: int) -> int:
        domain_hits = sum(term in full_text for term in SEED_BUSINESS_TERMS)
        keyword_hits = sum(keyword.lower() in full_text for keyword in matched_keywords)
        score = 30 + domain_hits * 8 + keyword_hits * 12 + category_score * 10
        return max(0, min(score, 100))

    def _build_recommended_action(
        self,
        topic_category: str,
        impact_level: str,
        urgency_level: str,
        matched_keywords: list[str],
        owner_department: str,
    ) -> str:
        keywords_text = ", ".join(matched_keywords[:3]) or "해당 키워드"
        lines = [
            f"{owner_department}에서 {topic_category} 이슈 여부를 1차 확인하고 관련 기사 원문을 검토하세요.",
            f"{keywords_text} 기준으로 당사 품목, 공급 일정, 거래선 영향 범위를 점검하세요.",
        ]
        if impact_level in {"중요", "즉시조치"} or urgency_level == "high":
            lines.append("필요 시 경영진 보고 안건으로 상정하고 이번 주 실행 과제를 확정하세요.")
        else:
            lines.append("추가 기사 추이를 모니터링하고 주간 보고서에 반영하세요.")
        return "\n".join(lines)

    def apply_feedback_to_action(
        self,
        *,
        base_action: str,
        review_status: str,
        owner_department: str,
        impact_level: str,
        urgency_level: str,
        comment: str | None = None,
    ) -> str:
        if not review_status or review_status == UNREVIEWED_STATUS:
            return base_action

        lines: list[str] = []
        if review_status == NOISE_STATUS:
            lines.append("잡음으로 분류된 기사입니다. 대시보드 분석 집계와 보고 대상에서 제외하고 키워드 유지 여부를 재검토하세요.")
        elif review_status == RELEVANT_STATUS:
            lines.append(
                f"{owner_department}에서 관련 기사로 확인했습니다. 영향도 {impact_level}, 긴급도 {URGENCY_LABELS.get(urgency_level, urgency_level)} 기준으로 대응 우선순위를 반영하세요."
            )
        else:
            lines.append(f"{owner_department}에서 검토 결과({review_status})를 반영해 후속 조치 필요 여부를 다시 정리하세요.")

        if comment:
            lines.append(f"피드백 조치사항: {comment}")

        for line in (base_action or "").splitlines():
            normalized = line.strip()
            if normalized and normalized not in lines:
                lines.append(normalized)

        return "\n".join(lines)

    def _detect_sports_noise(self, full_text: str) -> tuple[bool, list[str], list[str]]:
        sports_hits = [term for term in SPORTS_TERMS if term.lower() in full_text]
        domain_hits = [term for term in SEED_BUSINESS_TERMS if term.lower() in full_text]
        return len(sports_hits) >= 2 and len(domain_hits) <= 1, sports_hits, domain_hits

    def _llm_trace(self) -> dict[str, Any]:
        return {"applied": False, "reason": "rule_based_only", "detail": "LLM 보정은 추후 API 재구성 시 확장 가능합니다."}
