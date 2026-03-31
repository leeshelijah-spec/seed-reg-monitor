from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .sample_learning import SampleCase, load_sample_cases, similarity
from ..config import settings


CATEGORY_KEYWORDS = {
    "종자생산": ["종자", "채종", "생산", "재배", "증식", "무병화", "종자업", "종자검사"],
    "수입검역": ["검역", "수입", "식물방역", "병해충", "수출입", "열처리", "격리", "신고"],
    "품질관리": ["품질", "검정", "검사", "보증", "인증", "기준", "표준", "시료"],
    "품종보호": ["품종보호", "식물신품종", "보호품종", "육성자", "품종"],
    "표시광고": ["표시", "광고", "라벨", "가격표시", "포장", "용기"],
    "계약·거래": ["계약", "거래", "유통", "분쟁조정", "판매", "대리점", "약관"],
    "개인정보": ["개인정보", "정보보호", "정보통신망", "주민등록", "민감정보"],
    "환경안전": ["환경", "안전", "폐기물", "유해", "농약", "화학물질", "오염"],
    "일반컴플라이언스": ["의무", "신고", "등록", "허가", "처벌", "과태료", "제재", "행정처분", "준수"],
}

DEPARTMENT_BY_CATEGORY = {
    "종자생산": ["SCM", "연구"],
    "수입검역": ["SCM", "영업", "법무"],
    "품질관리": ["SCM", "연구"],
    "품종보호": ["연구", "법무"],
    "표시광고": ["영업", "법무"],
    "계약·거래": ["영업", "법무"],
    "개인정보": ["법무", "영업"],
    "환경안전": ["SCM", "법무", "연구"],
    "일반컴플라이언스": ["법무", "SCM"],
}

PENALTY_TERMS = ["과태료", "벌칙", "처벌", "행정처분", "징역", "벌금", "제재", "취소", "정지"]
OBLIGATION_TERMS = ["의무", "신고", "등록", "허가", "승인", "보고", "점검", "준수", "보관"]
OPERATIONAL_TERMS = ["기준", "절차", "표시", "라벨", "계약", "거래", "검사", "인증", "수입", "검역", "품질"]
LOW_SIGNAL_TERMS = ["지원", "협력", "원조", "정책방향", "참고", "운영규정"]
EXCLUSION_TERMS = ["직제", "정원", "인사", "복무", "공무국외출장", "위임전결", "청사", "관인", "보수", "수당"]


@dataclass
class ClassificationResult:
    category: list[str]
    department: list[str]
    severity: str
    relevance_reason: str
    severity_reason: str


class RegulationClassifier:
    def __init__(self) -> None:
        self.samples: list[SampleCase] = load_sample_cases(settings.sample_cases_dir)

    def classify(self, item: dict[str, Any]) -> ClassificationResult | None:
        title = item.get("title", "")
        if any(term in title for term in EXCLUSION_TERMS):
            return None

        text = "\n".join(
            [title, item.get("summary", ""), item.get("authority", ""), item.get("type", "")]
        )
        text_lower = text.lower()

        category_scores: dict[str, int] = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if score:
                category_scores[category] = score

        sample_match = self._find_sample_match(text)
        if sample_match and sample_match[1] >= 0.18:
            for category in sample_match[0].categories:
                category_scores[category] = category_scores.get(category, 0) + 2

        if not category_scores:
            return None

        categories = [
            category
            for category, score in sorted(category_scores.items(), key=lambda pair: (-pair[1], pair[0]))
            if score > 0
        ][:3]

        departments: list[str] = []
        for category in categories:
            for department in DEPARTMENT_BY_CATEGORY.get(category, []):
                if department not in departments:
                    departments.append(department)

        if sample_match and sample_match[1] >= 0.24:
            for department in sample_match[0].departments:
                if department not in departments:
                    departments.append(department)

        severity, severity_reason = self._determine_severity(item, text_lower, categories)
        relevance_reason = self._build_relevance_reason(categories, sample_match)

        return ClassificationResult(
            category=categories,
            department=departments or ["법무"],
            severity=severity,
            relevance_reason=relevance_reason,
            severity_reason=severity_reason,
        )

    def _find_sample_match(self, text: str) -> tuple[SampleCase, float] | None:
        text_tokens = set(re.findall(r"[가-힣A-Za-z]{2,}", text))
        best: tuple[SampleCase, float] | None = None
        for sample in self.samples:
            score = similarity(text_tokens, sample.tokens)
            if best is None or score > best[1]:
                best = (sample, score)
        return best

    def _determine_severity(self, item: dict[str, Any], text_lower: str, categories: list[str]) -> tuple[str, str]:
        penalty_hits = sum(term in text_lower for term in PENALTY_TERMS)
        obligation_hits = sum(term in text_lower for term in OBLIGATION_TERMS)
        operational_hits = sum(term in text_lower for term in OPERATIONAL_TERMS)
        low_signal_hits = sum(term in text_lower for term in LOW_SIGNAL_TERMS)

        effective_in_days = self._effective_in_days(item.get("effective_date"))
        is_legislative_notice = "입법예고" in item.get("type", "") or "입법예고" in item.get("title", "")

        if effective_in_days is not None and effective_in_days <= 30 and (penalty_hits or obligation_hits >= 2):
            severity = "긴급"
            reason = "시행일이 30일 이내이고 제재·의무성 표현이 확인되어 즉시 대응이 필요합니다."
        elif penalty_hits or obligation_hits >= 2 or ("수입검역" in categories and operational_hits):
            severity = "중요"
            reason = "운영 또는 준법 의무에 직접 영향을 줄 가능성이 높아 중요 건으로 분류했습니다."
        elif operational_hits or categories:
            severity = "검토필요"
            reason = "내부 프로세스, 표시, 검사, 계약 또는 부서 업무 영향 가능성이 있어 검토가 필요합니다."
        else:
            severity = "참고"
            reason = "직접 영향 신호가 약해 참고 수준으로 분류했습니다."

        if low_signal_hits >= 2 and severity in {"중요", "긴급"}:
            severity = "검토필요"
            reason = "정책·지원 성격이 강하고 직접 의무 영향이 불명확하여 보수적으로 한 단계 낮췄습니다."

        if is_legislative_notice:
            severity = self._downgrade(severity)
            reason = f"입법예고 단계 문서이므로 한 단계 낮춰 {severity}로 분류했습니다."

        return severity, reason

    def _build_relevance_reason(
        self,
        categories: list[str],
        sample_match: tuple[SampleCase, float] | None,
    ) -> str:
        base = f"{', '.join(categories)} 영역 키워드가 확인되어 종자 생산·수입·품질·품종보호 체계와의 연관성이 있습니다."
        if sample_match and sample_match[1] >= 0.18:
            sample = sample_match[0]
            return f"{base} 샘플 기준상 '{sample.title}' 사례와 유사도가 있어 관련 규제로 판단했습니다."
        return base

    def _effective_in_days(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            year, month, day = map(int, value.split("-"))
            return (date(year, month, day) - date.today()).days
        except ValueError:
            return None

    def _downgrade(self, severity: str) -> str:
        order = ["참고", "검토필요", "중요", "긴급"]
        idx = order.index(severity)
        return order[max(0, idx - 1)]
