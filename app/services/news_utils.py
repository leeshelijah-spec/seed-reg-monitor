from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

from ..config import settings


TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(ZoneInfo(settings.timezone)).isoformat()


def strip_html_markup(value: str | None) -> str:
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return MULTISPACE_RE.sub(" ", text).strip()


def normalize_link(link: str | None) -> str:
    if not link:
        return ""
    parsed = urlparse(link.strip())
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def build_duplicate_hash(original_link: str, title: str = "") -> str:
    base = original_link.strip().lower() or title.strip().lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def parse_naver_pub_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(ZoneInfo(settings.timezone)).isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def extract_source_title(original_link: str | None) -> str | None:
    if not original_link:
        return None
    parsed = urlparse(original_link)
    return parsed.netloc.lower() or None


def dumps_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)
