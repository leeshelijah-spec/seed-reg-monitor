from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "대한", "관련", "기준", "운영", "규정", "법률", "시행령", "시행규칙", "고시", "일부개정", "전부개정",
    "개정", "당사", "관련성", "판단", "사유", "문서종류", "소관기관", "게시일", "시행일", "원문링크",
    "주요", "내용", "중요도", "등급", "관련", "부서", "카테고리", "입법예고", "공고",
}


@dataclass
class SampleCase:
    title: str
    categories: list[str]
    departments: list[str]
    severity: str
    relevant: bool
    body: str

    @property
    def tokens(self) -> set[str]:
        tokens = set(re.findall(r"[가-힣A-Za-z]{2,}", f"{self.title}\n{self.body}"))
        return {token for token in tokens if token not in STOPWORDS}


def _extract_heading_list(text: str, heading: str) -> list[str]:
    match = re.search(rf"## {re.escape(heading)}\s+(.*?)(?:\n## |\Z)", text, re.S)
    if not match:
        return []
    section = match.group(1)
    return [line.strip().lstrip("- ").strip() for line in section.splitlines() if line.strip().startswith("-")]


def load_sample_cases(sample_dir: Path) -> list[SampleCase]:
    samples: list[SampleCase] = []
    for path in sorted(sample_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = re.search(r"^#\s+(.+)$", text, re.M)
        severity = re.search(r"- 등급:\s*(.+)$", text, re.M)
        relevance = re.search(r"- 관련 여부:\s*(.+)$", text, re.M)
        if not title or not severity or not relevance:
            continue
        samples.append(
            SampleCase(
                title=title.group(1).strip(),
                categories=[item.split(" (")[0] for item in _extract_heading_list(text, "카테고리")],
                departments=[item.split(" (")[0] for item in _extract_heading_list(text, "관련 부서") if not item.startswith("없음")],
                severity=severity.group(1).strip(),
                relevant="있음" in relevance.group(1),
                body=text,
            )
        )
    return samples


def similarity(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)
