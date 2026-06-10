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


class UdnMoneySource(RSSSource):
    """經濟日報。"""

    def __init__(self, limit: int = 30):
        super().__init__("經濟日報", "https://money.udn.com/rssfeed/news/1001/5590?ch=money", limit)


class TechNewsSource(RSSSource):
    """科技新報 (科技/產業新聞)。"""

    def __init__(self, limit: int = 30):
        super().__init__("科技新報", "https://technews.tw/feed/", limit)


# ── 美股 ──────────────────────────────────────────────

# 從標題/摘要抓美股代號:$AAPL 或 (AAPL)
_US_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b|\(([A-Z]{1,5})\)")
# 常見的非代號縮寫,排除以降低雜訊
_US_STOP = {
    "AI", "CEO", "CFO", "COO", "US", "USA", "UK", "EU", "GDP", "CPI", "PCE", "FBI",
    "SEC", "FED", "ETF", "IPO", "NYSE", "AM", "PM", "EV", "OK", "IT", "PC", "TV",
    "AP", "EPS", "ESG", "API", "CES", "FAQ", "Q1", "Q2", "Q3", "Q4", "WSJ", "CNBC",
    "NEW", "ALL", "CEOS", "CES", "CHIP", "CHIPS", "CARS", "CASH", "CCP",
}


class USRSSSource(RSSSource):
    """美股 RSS 來源:沿用通用 RSS,額外從內文解析美股代號填入 stocks。"""

    def fetch(self) -> list[NewsItem]:
        items = super().fetch()
        for it in items:
            text = f"{it.title} {it.summary}"
            tickers: list[str] = []
            for m in _US_TICKER_RE.finditer(text):
                t = m.group(1) or m.group(2)
                if t and t not in _US_STOP and t not in tickers:
                    tickers.append(t)
            it.stocks = tickers
        return items


class CnbcMarketsSource(USRSSSource):
    """CNBC Markets。"""

    def __init__(self, limit: int = 30):
        super().__init__("CNBC Markets", "https://www.cnbc.com/id/15839135/device/rss/rss.html", limit)


class CnbcFinanceSource(USRSSSource):
    """CNBC Finance。"""

    def __init__(self, limit: int = 30):
        super().__init__("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html", limit)


class MarketWatchSource(USRSSSource):
    """MarketWatch 頭條。"""

    def __init__(self, limit: int = 30):
        super().__init__("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/", limit)


class YahooFinanceSource(USRSSSource):
    """Yahoo Finance。"""

    def __init__(self, limit: int = 30):
        super().__init__("Yahoo Finance", "https://finance.yahoo.com/news/rssindex", limit)


class InvestingSource(USRSSSource):
    """Investing.com。"""

    def __init__(self, limit: int = 30):
        super().__init__("Investing.com", "https://www.investing.com/rss/news.rss", limit)


class NytBusinessSource(USRSSSource):
    """New York Times — Business。"""

    def __init__(self, limit: int = 30):
        super().__init__("NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", limit)


class WsjMarketsSource(USRSSSource):
    """Wall Street Journal — Markets。"""

    def __init__(self, limit: int = 30):
        super().__init__("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", limit)


class CnbcTopSource(USRSSSource):
    """CNBC Top News。"""

    def __init__(self, limit: int = 30):
        super().__init__("CNBC Top", "https://www.cnbc.com/id/100003114/device/rss/rss.html", limit)


class CnbcTechSource(USRSSSource):
    """CNBC Technology。"""

    def __init__(self, limit: int = 30):
        super().__init__("CNBC Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html", limit)


class BusinessInsiderSource(USRSSSource):
    """Business Insider — Markets。"""

    def __init__(self, limit: int = 30):
        super().__init__("Business Insider", "https://markets.businessinsider.com/rss/news", limit)


class MotleyFoolSource(USRSSSource):
    """The Motley Fool。"""

    def __init__(self, limit: int = 30):
        super().__init__("Motley Fool", "https://www.fool.com/feeds/index.aspx", limit)
