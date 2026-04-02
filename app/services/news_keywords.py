from __future__ import annotations

import json
from dataclasses import dataclass

from ..config import settings
from ..database import get_connection
from .classifier import CATEGORY_KEYWORDS
from .news_utils import now_iso


@dataclass(frozen=True)
class KeywordSeed:
    keyword_group: str
    source_type: str
    keywords: list[str]


DEFAULT_INDUSTRY_KEYWORDS = [
    "종자산업",
    "종묘",
    "육종",
    "품종보호",
    "식물신품종",
    "종자 수출",
    "종자 수입",
    "검역",
    "병해충",
    "채소 종자",
]

DEFAULT_CROP_KEYWORDS = [
    "메론",
    "수박",
    "오이",
    "참외",
    "토마토",
    "배추",
    "시금치",
    "양배추",
    "양상추",
    "당근",
    "대파",
    "고추",
    "청경채",
    "상추",
    "브로콜리",
    "무",
]

REFERENCE_CATEGORY_KEYS = ("종자생산", "수입검역", "품종보호", "농자재·재배환경", "지식재산·육종권")


def _build_default_seeds() -> list[KeywordSeed]:
    regulation_reference = sorted(
        {
            keyword
            for category in REFERENCE_CATEGORY_KEYS
            for keyword in CATEGORY_KEYWORDS.get(category, [])
            if len(keyword.strip()) >= 2
        }
    )
    return [
        KeywordSeed(keyword_group="산업 핵심", source_type="seed", keywords=DEFAULT_INDUSTRY_KEYWORDS),
        KeywordSeed(keyword_group="주요 작물", source_type="seed", keywords=DEFAULT_CROP_KEYWORDS),
        KeywordSeed(keyword_group="기존 규제 분류 연계", source_type="regulation_reference", keywords=regulation_reference),
    ]


def _load_file_seeds() -> list[KeywordSeed]:
    path = settings.news_keywords_path
    if not path.exists():
        example_path = path.parent / "news-keywords.example.json"
        if not example_path.exists():
            return []
        path = example_path

    raw_data = json.loads(path.read_text(encoding="utf-8"))
    seeds: list[KeywordSeed] = []
    for row in raw_data:
        keyword_group = str(row.get("group", "사용자 정의")).strip() or "사용자 정의"
        source_type = str(row.get("source", "config")).strip() or "config"
        keywords = sorted({str(item).strip() for item in row.get("keywords", []) if str(item).strip()})
        if keywords:
            seeds.append(KeywordSeed(keyword_group=keyword_group, source_type=source_type, keywords=keywords))
    return seeds


class NewsKeywordService:
    def ensure_seed_data(self) -> None:
        with get_connection() as connection:
            existing_count = connection.execute("SELECT COUNT(*) FROM news_keywords").fetchone()[0]
            if existing_count:
                return

        seeds = _load_file_seeds() or _build_default_seeds()
        now = now_iso()
        with get_connection() as connection:
            for seed in seeds:
                for keyword in seed.keywords:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO news_keywords (
                            keyword, keyword_group, source_type, is_active, created_at, updated_at
                        ) VALUES (?, ?, ?, 1, ?, ?)
                        """,
                        (keyword, seed.keyword_group, seed.source_type, now, now),
                    )

    def list_keywords(self, include_inactive: bool = False) -> list[dict]:
        sql = """
            SELECT *
            FROM news_keywords
            {where_clause}
            ORDER BY is_active DESC, keyword_group, keyword
        """
        where_clause = "" if include_inactive else "WHERE is_active = 1"
        with get_connection() as connection:
            rows = connection.execute(sql.format(where_clause=where_clause)).fetchall()
        return [dict(row) for row in rows]

    def list_active_keywords(self) -> list[dict]:
        return self.list_keywords(include_inactive=False)

    def add_keyword(self, keyword: str, keyword_group: str, notes: str | None = None) -> None:
        cleaned_keyword = keyword.strip()
        cleaned_group = keyword_group.strip() or "사용자 정의"
        if not cleaned_keyword:
            raise ValueError("keyword is required")

        now = now_iso()
        with get_connection() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM news_keywords
                WHERE keyword = ? AND keyword_group = ?
                """,
                (cleaned_keyword, cleaned_group),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE news_keywords
                    SET is_active = 1, notes = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (notes or None, now, existing["id"]),
                )
                return

            connection.execute(
                """
                INSERT INTO news_keywords (
                    keyword, keyword_group, source_type, notes, is_active, created_at, updated_at
                ) VALUES (?, ?, 'manual', ?, 1, ?, ?)
                """,
                (cleaned_keyword, cleaned_group, notes or None, now, now),
            )

    def set_keyword_active(self, keyword_id: int, is_active: bool) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE news_keywords
                SET is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (1 if is_active else 0, now_iso(), keyword_id),
            )
