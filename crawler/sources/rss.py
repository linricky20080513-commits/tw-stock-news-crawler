"""以 RSS 為基礎的新聞來源 (通用)。

RSS 穩定、不易被擋,適合作為鉅亨網 JSON API 之外的補充來源。
目前內建:
    中央社 (CNA) 財經
    ETtoday 財經
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from time import mktime

import feedparser

from ..models import NewsItem, TZ_TAIPEI


def _parse_date(entry) -> datetime | None:
    """盡力從 RSS entry 解析出帶時區的發布時間。

    先用 feedparser 解析好的 struct_time;失敗時 (例如 ETtoday 的
    "Wed,10 Jun 2026 09:51:00  +0800" 格式不標準) 再退而手動解析字串。
    """
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm:
        return datetime.fromtimestamp(mktime(tm)).astimezone(TZ_TAIPEI)

    raw = entry.get("published") or entry.get("updated") or ""
    if not raw:
        return None
    # 修正常見的非標準格式:逗號後補空格、壓縮多餘空白
    cleaned = re.sub(r",(?=\S)", ", ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    try:
        return parsedate_to_datetime(cleaned).astimezone(TZ_TAIPEI)
    except (TypeError, ValueError):
        return None


class RSSSource:
    """通用 RSS 來源;給定來源名稱與 feed 網址即可。"""

    def __init__(self, name: str, url: str, limit: int = 30):
        self.name = name
        self.url = url
        self.limit = limit

    def fetch(self) -> list[NewsItem]:
        feed = feedparser.parse(self.url)

        items: list[NewsItem] = []
        for entry in feed.entries[: self.limit]:
            published = _parse_date(entry)

            items.append(
                NewsItem(
                    title=(entry.get("title") or "").strip(),
                    url=(entry.get("link") or "").strip(),
                    source=self.name,
                    summary=(entry.get("summary") or "").strip(),
                    published_at=published,
                )
            )
        return items


class CnaSource(RSSSource):
    """中央社財經新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("中央社", "https://feeds.feedburner.com/rsscna/finance", limit)


class EttodaySource(RSSSource):
    """ETtoday 財經新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("ETtoday", "https://feeds.feedburner.com/ettoday/finance", limit)


class LtnSource(RSSSource):
    """自由財經 (自由時報財經) 新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("自由財經", "https://news.ltn.com.tw/rss/business.xml", limit)
