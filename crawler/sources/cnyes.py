"""鉅亨網 (cnyes) 台股新聞來源。

使用鉅亨網公開的 JSON API，回傳結構化資料，穩定且適合即時抓取。
分類:
    tw_stock          台股
    tw_stock_news     台股新聞
    headline          頭條
"""

from __future__ import annotations

from datetime import datetime

import requests

from ..models import NewsItem, TZ_TAIPEI

API_URL = "https://api.cnyes.com/media/api/v1/newslist/category/{category}"
NEWS_URL = "https://news.cnyes.com/news/id/{news_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Origin": "https://news.cnyes.com",
    "Referer": "https://news.cnyes.com/",
}


class CnyesSource:
    name = "鉅亨網"

    def __init__(self, category: str = "tw_stock", limit: int = 30, timeout: int = 10):
        self.category = category
        self.limit = limit
        self.timeout = timeout

    def fetch(self) -> list[NewsItem]:
        resp = requests.get(
            API_URL.format(category=self.category),
            params={"limit": self.limit},
            headers=HEADERS,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        items: list[NewsItem] = []
        for d in payload.get("items", {}).get("data", []):
            news_id = d.get("newsId")
            if news_id is None:
                continue

            published = None
            ts = d.get("publishAt")
            if ts:
                published = datetime.fromtimestamp(ts, tz=TZ_TAIPEI)

            # 相關個股 (若 API 有提供)
            stocks = [
                s.get("symbol") or s.get("name", "")
                for s in d.get("market", []) or []
                if isinstance(s, dict)
            ]

            items.append(
                NewsItem(
                    title=(d.get("title") or "").strip(),
                    url=NEWS_URL.format(news_id=news_id),
                    source=self.name,
                    summary=(d.get("summary") or "").strip(),
                    published_at=published,
                    stocks=[s for s in stocks if s],
                )
            )
        return items
