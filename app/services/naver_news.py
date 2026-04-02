from __future__ import annotations

import time
from typing import Any

import requests

from ..config import settings


class NaverNewsClient:
    endpoint = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self) -> None:
        self.session = requests.Session()

    def is_configured(self) -> bool:
        return bool(settings.naver_client_id and settings.naver_client_secret)

    def search_news(
        self,
        keyword: str,
        display: int | None = None,
        start: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET are not configured")

        params = {
            "query": keyword,
            "display": max(1, min(display or settings.naver_news_display, 100)),
            "start": max(1, min(start, 1000)),
            "sort": sort or settings.naver_news_sort,
        }
        headers = {
            "X-Naver-Client-Id": settings.naver_client_id or "",
            "X-Naver-Client-Secret": settings.naver_client_secret or "",
        }

        last_error: Exception | None = None
        for attempt in range(1, settings.naver_news_max_retries + 1):
            try:
                response = self.session.get(
                    self.endpoint,
                    params=params,
                    headers=headers,
                    timeout=settings.naver_news_timeout,
                )
                response.raise_for_status()
                payload = response.json()
                payload["_meta"] = {
                    "http_status": response.status_code,
                    "retry_count": attempt - 1,
                }
                return payload
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= settings.naver_news_max_retries:
                    break
                time.sleep(0.8 * attempt)

        raise RuntimeError(f"Naver news API request failed: {last_error}") from last_error
