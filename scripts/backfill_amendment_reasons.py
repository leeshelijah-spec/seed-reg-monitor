from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import get_connection
from app.services.korean_law_adapter import KoreanLawAdapter


def extract_reason(adapter: KoreanLawAdapter, source_url: str) -> str | None:
    parsed = urlparse(source_url)
    params = parse_qs(parsed.query)
    target = (params.get("target") or [""])[0]

    if target == "law":
        mst = (params.get("MST") or [""])[0]
        ef_yd = (params.get("efYd") or [""])[0]
        if not mst:
            return None
        payload = adapter._fetch_law_text(mst, ef_yd or None)
        return adapter._extract_law_amendment_reason(payload)

    if target == "admrul":
        rule_id = (params.get("ID") or [""])[0]
        if not rule_id:
            return None
        detail = adapter._fetch_admin_rule(rule_id)
        return detail.get("amendment_reason")

    return None


def main() -> None:
    adapter = KoreanLawAdapter()
    updated = 0

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, source_url, amendment_reason
            FROM regulations
            ORDER BY id
            """
        ).fetchall()

        for row in rows:
            current_reason = row["amendment_reason"] or ""
            refreshed_reason = extract_reason(adapter, row["source_url"])
            if not refreshed_reason:
                continue
            if len(refreshed_reason.strip()) <= len(current_reason.strip()):
                continue

            connection.execute(
                "UPDATE regulations SET amendment_reason = ? WHERE id = ?",
                (refreshed_reason, row["id"]),
            )
            updated += 1

    print(f"updated={updated}")


if __name__ == "__main__":
    main()
