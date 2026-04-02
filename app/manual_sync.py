from __future__ import annotations

from .database import init_db
from .services.ingestion import IngestionService
from .services.news_ingestion import NewsIngestionService


def main() -> None:
    init_db()
    print({"regulations": IngestionService().run(lookback_days=5)})
    news_service = NewsIngestionService()
    if news_service.is_configured():
        print({"news": news_service.run(run_type="manual")})
    else:
        print({"news": "skipped: NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not configured"})


if __name__ == "__main__":
    main()
