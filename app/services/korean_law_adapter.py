from __future__ import annotations

import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

from ..config import settings


LAW_BASE_URL = "https://www.law.go.kr"
SEED_KEYWORDS = [
    "종자",
    "품종보호",
    "식물방역",
    "식물검역",
    "종자검사",
    "종자검정",
    "종자가격표시",
    "무병화",
    "농수산물 품질관리",
]

SECTOR_LAW_HINTS = [
    "종자",
    "품종",
    "식물방역",
    "검역",
    "식물검역",
    "농수산물 품질관리",
    "농약관리",
]
TRACKED_GENERAL_LAWS = {
    "개인정보 보호법",
    "개인정보 보호법 시행령",
    "개인정보 보호법 시행규칙",
    "표시·광고의 공정화에 관한 법률",
    "표시·광고의 공정화에 관한 법률 시행령",
    "독점규제 및 공정거래에 관한 법률",
    "독점규제 및 공정거래에 관한 법률 시행령",
    "약관의 규제에 관한 법률",
    "전자상거래 등에서의 소비자보호에 관한 법률",
}
LAW_TITLE_EXCLUSIONS = ["직제", "정원", "인사", "관인", "공무원", "수당", "청사", "행정기구"]
GENERIC_ADMIN_RULE_TERMS = ["기본운영규정", "운영규정", "관리규정", "운영세칙", "공무직근로자", "출장"]
CORE_ADMIN_RULE_TERMS = ["검사", "검정", "표시", "검역", "인증", "품질", "보호", "수입", "판매", "신고"]


class KoreanLawAdapter:
    def __init__(self) -> None:
        self.fetcher_script = settings.base_dir / "scripts" / "korean_law_fetcher.mjs"
        self.mcp_dir = settings.korean_law_mcp_dir
        self.env = os.environ.copy()
        self.env["KOREAN_LAW_MCP_DIR"] = str(self.mcp_dir)
        self.env.setdefault("LAW_OC", self._read_law_oc())

    def fetch_recent_items(self, lookback_days: int = 7) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for target_date in self._recent_business_dates(lookback_days):
            for item in self._fetch_law_history_for_date(target_date):
                if item["source_url"] not in seen_urls:
                    items.append(item)
                    seen_urls.add(item["source_url"])

        for item in self._fetch_recent_admin_rules(lookback_days):
            if item["source_url"] not in seen_urls:
                items.append(item)
                seen_urls.add(item["source_url"])

        for item in self._fetch_legislative_notice_candidates(lookback_days):
            if item["source_url"] not in seen_urls:
                items.append(item)
                seen_urls.add(item["source_url"])

        return items

    def _fetch_law_history_for_date(self, target_date: date) -> list[dict[str, Any]]:
        payload = self._run_fetcher("law_history", {"regDt": target_date.strftime("%Y%m%d"), "display": 200})
        root = ET.fromstring(payload["raw"])
        results: list[dict[str, Any]] = []

        for node in root.findall("law"):
            law_type = self._xml_text(node, "법령구분명")
            if law_type not in {"법률", "대통령령", "총리령", "부령", "농림축산식품부령", "해양수산부령"}:
                continue

            title = self._xml_text(node, "법령명한글")
            if not (any(hint in title for hint in SECTOR_LAW_HINTS) or title in TRACKED_GENERAL_LAWS):
                continue
            if any(term in title for term in LAW_TITLE_EXCLUSIONS):
                continue

            mst = self._xml_text(node, "법령일련번호")
            effective_date_raw = self._xml_text(node, "시행일자")
            law_detail = self._fetch_law_text(mst, effective_date_raw)
            results.append(
                {
                    "title": title,
                    "type": law_type,
                    "authority": self._xml_text(node, "소관부처명"),
                    "publication_date": self._normalize_date(self._xml_text(node, "공포일자")),
                    "effective_date": self._normalize_date(effective_date_raw),
                    "source_url": urljoin(LAW_BASE_URL, self._xml_text(node, "법령상세링크")).replace("&amp;", "&"),
                    "summary": self._extract_law_summary(law_detail),
                    "amendment_reason": self._extract_law_amendment_reason(law_detail),
                }
            )
        return results

    def _fetch_recent_admin_rules(self, lookback_days: int) -> list[dict[str, Any]]:
        cutoff = date.today() - timedelta(days=lookback_days)
        results: list[dict[str, Any]] = []
        seen_seq: set[str] = set()

        for keyword in SEED_KEYWORDS:
            payload = self._run_fetcher("search_admin_rule", {"query": keyword, "display": 30})
            root = ET.fromstring(payload["raw"])
            for node in root.findall("admrul"):
                seq = self._xml_text(node, "행정규칙일련번호")
                if not seq or seq in seen_seq:
                    continue
                title = self._xml_text(node, "행정규칙명")
                if any(term in title for term in GENERIC_ADMIN_RULE_TERMS) and not any(
                    core in title for core in CORE_ADMIN_RULE_TERMS
                ):
                    continue

                publication_date = self._normalize_date(self._xml_text(node, "발령일자"))
                if not publication_date:
                    continue
                if datetime.strptime(publication_date, "%Y-%m-%d").date() < cutoff:
                    continue

                detail = self._fetch_admin_rule(seq)
                results.append(
                    {
                        "title": title,
                        "type": self._xml_text(node, "행정규칙종류") or "행정규칙",
                        "authority": self._xml_text(node, "소관부처명"),
                        "publication_date": publication_date,
                        "effective_date": publication_date,
                        "source_url": detail["source_url"],
                        "summary": detail["summary"],
                        "amendment_reason": detail["amendment_reason"],
                    }
                )
                seen_seq.add(seq)

        return results

    def _fetch_legislative_notice_candidates(self, lookback_days: int) -> list[dict[str, Any]]:
        cutoff = date.today() - timedelta(days=lookback_days)
        results: list[dict[str, Any]] = []
        search_url = "https://www.law.go.kr/lsSc.do?menuId=1&subMenuId=23&tabMenuId=123&query={query}"

        try:
            import requests
        except ImportError:
            return results

        for keyword in SEED_KEYWORDS[:5]:
            response = requests.get(search_url.format(query=f"{keyword} 입법예고"), timeout=20)
            html = response.text
            for match in re.finditer(r'href="(?P<href>/[^"]+)"[^>]*>(?P<title>[^<]*입법예고[^<]*)</a>', html):
                title = re.sub(r"\s+", " ", match.group("title")).strip()
                snippet = html[max(0, match.start() - 400):match.end() + 400]
                date_match = re.search(r"(20\d{2}[.-]\d{2}[.-]\d{2})", snippet)
                publication_date = date_match.group(1).replace(".", "-") if date_match else None
                if publication_date:
                    published = datetime.strptime(publication_date, "%Y-%m-%d").date()
                    if published < cutoff:
                        continue

                results.append(
                    {
                        "title": title,
                        "type": "입법예고",
                        "authority": "법제처/소관부처",
                        "publication_date": publication_date,
                        "effective_date": None,
                        "source_url": urljoin(LAW_BASE_URL, match.group("href")),
                        "summary": "법률안 또는 하위규정 입법예고 후보로 수집된 건입니다.",
                        "amendment_reason": "입법예고 단계 문서로, 제개정 이유는 원문 링크에서 추가 확인이 필요합니다.",
                    }
                )

        deduped: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in results:
            if item["source_url"] not in seen_urls:
                deduped.append(item)
                seen_urls.add(item["source_url"])
        return deduped

    def _fetch_law_text(self, mst: str, ef_yd: str | None) -> dict[str, Any]:
        payload = self._run_fetcher("law_text", {"mst": mst, "efYd": ef_yd})
        return json.loads(payload["raw"])

    def _fetch_admin_rule(self, rule_seq: str) -> dict[str, Any]:
        payload = self._run_fetcher("admin_rule_detail", {"id": rule_seq})
        root = ET.fromstring(payload["raw"])
        source_url = urljoin(LAW_BASE_URL, f"/DRF/lawService.do?target=admrul&ID={rule_seq}&type=HTML")

        summary_lines: list[str] = []
        for tag in ("조문내용", "부칙내용", "별표내용"):
            for node in root.findall(f".//{tag}"):
                text = (node.text or "").strip()
                if text:
                    summary_lines.extend(line.strip() for line in text.splitlines() if line.strip())
                if len(summary_lines) >= 4:
                    break
            if len(summary_lines) >= 4:
                break

        return {
            "source_url": source_url,
            "summary": " ".join(summary_lines[:4])[:800] if summary_lines else "행정규칙 본문 확인 필요",
            "amendment_reason": self._extract_admin_rule_amendment_reason(root),
        }

    def _extract_law_summary(self, law_json: dict[str, Any]) -> str:
        law = law_json.get("법령", {})
        lines: list[str] = []
        for key in ("개정문", "조문", "부칙"):
            block = law.get(key)
            if not block:
                continue
            serialized = json.dumps(block, ensure_ascii=False)
            candidates = re.findall(r"[가-힣A-Za-z0-9ㆍ·()\-]{4,}", serialized)
            for candidate in candidates:
                if candidate not in lines:
                    lines.append(candidate)
                if len(lines) >= 8:
                    break
            if len(lines) >= 8:
                break
        summary = " ".join(lines[:6]).strip()
        return summary[:800] if summary else "개정문 요약 추출 필요"

    def _extract_law_amendment_reason(self, law_json: dict[str, Any]) -> str:
        law = law_json.get("법령", law_json)
        reason_block = law.get("제개정이유") or law.get("개정문")
        if reason_block:
            reason_content = (
                reason_block.get("제개정이유내용")
                or reason_block.get("개정문내용")
                or reason_block
            )
            flattened = self._flatten_text_parts(reason_content)
            if flattened:
                return flattened

        matches = self._collect_values_for_keys(
            law,
            {"제개정이유", "개정이유", "이유", "개정문"},
        )
        if matches:
            return "\n".join(matches)
        return self._extract_law_summary(law_json)

    def _extract_admin_rule_amendment_reason(self, root: ET.Element) -> str:
        reasons: list[str] = []
        for node in root.iter():
            tag = re.sub(r"^\{.*\}", "", node.tag)
            if not any(keyword in tag for keyword in ("제개정이유", "개정이유", "이유")):
                continue
            text = "\n".join(part.strip() for part in node.itertext() if part.strip())
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if text and text not in reasons:
                reasons.append(text)
        if reasons:
            return "\n\n".join(reasons)
        return "행정규칙 본문 확인 필요"

    def _flatten_text_parts(self, value: Any) -> str:
        lines: list[str] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for nested in node.values():
                    _walk(nested)
                return
            if isinstance(node, list):
                for nested in node:
                    _walk(nested)
                return

            text = str(node).strip()
            if not text:
                return
            text = re.sub(r"[ \t]+", " ", text)
            if text not in lines:
                lines.append(text)

        _walk(value)
        return "\n".join(lines).strip()

    def _collect_values_for_keys(
        self,
        data: Any,
        keywords: set[str],
    ) -> list[str]:
        matches: list[str] = []

        def _walk(value: Any, current_key: str | None = None) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    _walk(nested, str(key))
                return
            if isinstance(value, list):
                for nested in value:
                    _walk(nested, current_key)
                return
            if current_key and any(keyword in current_key for keyword in keywords):
                text = re.sub(r"\s+", " ", str(value)).strip()
                if text and text not in matches:
                    matches.append(text)

        _walk(data)
        return matches

    def _run_fetcher(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        completed = subprocess.run(
            ["node", str(self.fetcher_script), action, json.dumps(payload, ensure_ascii=False)],
            cwd=settings.base_dir,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return json.loads(completed.stdout)

    def _read_law_oc(self) -> str:
        env_path = self.mcp_dir / ".env"
        if not env_path.exists():
            return ""
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("LAW_OC="):
                return line.split("=", 1)[1].strip()
        return ""

    def _recent_business_dates(self, count: int) -> list[date]:
        dates: list[date] = []
        cursor = date.today()
        while len(dates) < count:
            if cursor.weekday() < 5:
                dates.append(cursor)
            cursor -= timedelta(days=1)
        return dates

    def _normalize_date(self, raw: str | None) -> str | None:
        if not raw:
            return None
        digits = re.sub(r"[^0-9]", "", raw)
        if len(digits) != 8:
            return None
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"

    def _xml_text(self, node: ET.Element, tag: str) -> str:
        child = node.find(tag)
        return child.text.strip() if child is not None and child.text else ""
