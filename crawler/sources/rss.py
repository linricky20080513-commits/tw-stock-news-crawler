"""以 RSS 為基礎的新聞來源 (通用)。

RSS 穩定、不易被擋,適合作為鉅亨網 JSON API 之外的補充來源。
目前內建:
    中央社 (CNA) 財經
    ETtoday 財經
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import mktime

import feedparser

from ..models import NewsItem, TZ_TAIPEI

# 用瀏覽器 UA,部分站台會擋預設的 feedparser UA
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _parse_date(entry) -> datetime | None:
    """盡力從 RSS entry 解析出帶時區的發布時間。

    先用 feedparser 解析好的 struct_time;失敗時 (例如 ETtoday 的
    "Wed,10 Jun 2026 09:51:00  +0800" 格式不標準) 再退而手動解析字串。
    """
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm:
        try:
            return datetime.fromtimestamp(mktime(tm)).astimezone(TZ_TAIPEI)
        except (ValueError, OverflowError, OSError):
            pass  # 時間超出範圍 → 退而用下方字串解析

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
        feed = feedparser.parse(self.url, agent=_UA)

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


# 高信心:名稱（2330）、(2330)、（2330-TW） 等格式 → 直接取股號
_TW_CODE_RE = re.compile(
    r"[一-龥][（(]\s*(\d{4,6})(?:\s*[-‑]?\s*TW)?\s*[）)]"
    r"|[（(]\s*(\d{4,6})\s*[-‑]\s*TW\s*[）)]"
)
# 推測:公司名 + 附近有股市語境詞 → 反查股號
_STOCKS_PATH = Path(__file__).resolve().parents[2] / "data" / "stocks.json"
# 易與一般詞彙混淆的公司名 → 不做名稱比對(避免誤判)
_NAME_BLOCK = {"統一", "大同", "中興", "國建", "大成", "三商", "中華", "台灣", "中國",
               "第一", "國票", "全國", "大將", "農林", "唐鋒", "大魯閣", "力士"}
_CUE = re.compile(r"股|漲|跌|盤|成交|營收|法人|外資|投信|除息|填息|EPS|財報|目標價|評等|"
                  r"買超|賣超|市值|漲停|跌停|類股|掛牌|上市|上櫃|除權|概念|季報|月營收")
_NAME2CODE = None
_NAMES_SORTED: list[str] = []


def _load_names() -> None:
    global _NAME2CODE, _NAMES_SORTED
    if _NAME2CODE is not None:
        return
    _NAME2CODE = {}
    try:
        data = json.loads(_STOCKS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 沒有 stocks.json 就只靠 (股號) 格式
        data = {}
    for code, nm in data.items():
        if nm and 2 <= len(nm) <= 8 and nm not in _NAME_BLOCK:
            _NAME2CODE.setdefault(nm, code)
    _NAMES_SORTED = sorted(_NAME2CODE, key=len, reverse=True)  # 先比長名


class TWRSSSource(RSSSource):
    """台股 RSS 來源:除通用 RSS 外,擷取台股股號填入 stocks。

    1. 高信心:文字含「名稱(股號)」或「(股號-TW)」→ 直接取股號。
    2. 推測:公司名出現且附近有股市語境詞 → 反查股號(先比長名、不重疊、
       排除易混淆名稱),盡量降低誤判。
    """

    def fetch(self) -> list[NewsItem]:
        items = super().fetch()
        _load_names()
        for it in items:
            text = f"{it.title} {it.summary}"
            codes: list[str] = []
            for m in _TW_CODE_RE.finditer(text):
                c = m.group(1) or m.group(2)
                if c and c not in codes:
                    codes.append(c)
            spans: list[tuple[int, int]] = []
            for nm in _NAMES_SORTED:
                start = text.find(nm)
                if start < 0:
                    continue
                end = start + len(nm)
                if any(s < end and start < e for s, e in spans):
                    continue  # 落在已比對到的長名內 → 跳(避免子字串誤判)
                if not _CUE.search(text[max(0, start - 10):end + 10]):
                    continue  # 附近沒有股市語境 → 不算
                spans.append((start, end))
                c = _NAME2CODE[nm]
                if c not in codes:
                    codes.append(c)
            it.stocks = codes
        return items


class CnaSource(TWRSSSource):
    """中央社財經新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("中央社", "https://feeds.feedburner.com/rsscna/finance", limit)


class EttodaySource(TWRSSSource):
    """ETtoday 財經新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("ETtoday", "https://feeds.feedburner.com/ettoday/finance", limit)


class LtnSource(TWRSSSource):
    """自由財經 (自由時報財經) 新聞。"""

    def __init__(self, limit: int = 30):
        super().__init__("自由財經", "https://news.ltn.com.tw/rss/business.xml", limit)


class UdnMoneySource(TWRSSSource):
    """經濟日報 (要聞)。"""

    def __init__(self, limit: int = 30):
        super().__init__("經濟日報", "https://money.udn.com/rssfeed/news/1001/5590?ch=money", limit)


class TechNewsSource(TWRSSSource):
    """科技新報 (科技/產業新聞)。"""

    def __init__(self, limit: int = 30):
        super().__init__("科技新報", "https://technews.tw/feed/", limit)


# ── 新增台股來源 ─────────────────────────────────────

class MirrorFinanceSource(TWRSSSource):
    """鏡週刊 財經。"""

    def __init__(self, limit: int = 40):
        super().__init__("鏡週刊財經", "https://www.mirrormedia.mg/rss/finance.xml", limit)


class UdnStockSource(TWRSSSource):
    """經濟日報 股市。"""

    def __init__(self, limit: int = 30):
        super().__init__("經濟日報股市", "https://money.udn.com/rssfeed/news/1001/5591?ch=money", limit)


class UdnMacroSource(TWRSSSource):
    """經濟日報 產業‧總經。"""

    def __init__(self, limit: int = 30):
        super().__init__("經濟日報總經", "https://money.udn.com/rssfeed/news/1001/10846?ch=money", limit)


class UdnBizSource(TWRSSSource):
    """聯合新聞網 財經。"""

    def __init__(self, limit: int = 30):
        super().__init__("聯合財經", "https://udn.com/rssfeed/news/2/6644?ch=news", limit)


class YahooTwSource(TWRSSSource):
    """Yahoo 奇摩股市 / 財經。"""

    def __init__(self, limit: int = 30):
        super().__init__("Yahoo股市", "https://tw.news.yahoo.com/rss/finance", limit)


class FinanceTechNewsSource(TWRSSSource):
    """財經新報 (科技新報財經站)。"""

    def __init__(self, limit: int = 40):
        super().__init__("財經新報", "https://finance.technews.tw/feed/", limit)


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
