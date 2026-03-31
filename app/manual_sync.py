from __future__ import annotations

from .database import init_db
from .services.ingestion import IngestionService


def main() -> None:
    init_db()
    print(IngestionService().run(lookback_days=5))


if __name__ == "__main__":
    main()
