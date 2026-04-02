from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import init_db
from app.services.news_ingestion import NewsIngestionService


SAMPLE_PATH = BASE_DIR / "docs" / "samples" / "naver-news-sample.json"


def main() -> None:
    init_db()
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    service = NewsIngestionService()
    inserted_total = 0
    duplicate_total = 0
    for row in payload:
        inserted_count, duplicate_count = service.ingest_items(
            keyword=row["keyword"],
            items=row.get("items", []),
        )
        inserted_total += inserted_count
        duplicate_total += duplicate_count
    print({"inserted_count": inserted_total, "duplicate_count": duplicate_total})


if __name__ == "__main__":
    main()
