"""新聞來源。每個來源實作 fetch() -> list[NewsItem]。"""

from .cnyes import CnyesSource
from .rss import (
    CnaSource, EttodaySource, LtnSource, UdnMoneySource, TechNewsSource, RSSSource,
    CnbcMarketsSource, CnbcFinanceSource, MarketWatchSource,
    YahooFinanceSource, InvestingSource, NytBusinessSource, WsjMarketsSource,
    CnbcTopSource, CnbcTechSource, BusinessInsiderSource, MotleyFoolSource,
)

# 台股預設啟用的來源清單
ALL_SOURCES = [CnyesSource, CnaSource, EttodaySource, LtnSource, UdnMoneySource, TechNewsSource]
# 美股來源
US_SOURCES = [
    CnbcMarketsSource, CnbcFinanceSource, MarketWatchSource, YahooFinanceSource,
    InvestingSource, NytBusinessSource, WsjMarketsSource, CnbcTopSource,
    CnbcTechSource, BusinessInsiderSource, MotleyFoolSource,
]
