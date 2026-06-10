"""新聞來源。每個來源實作 fetch() -> list[NewsItem]。"""

from .cnyes import CnyesSource
from .rss import CnaSource, EttodaySource, LtnSource, RSSSource

# 預設啟用的來源清單
ALL_SOURCES = [CnyesSource, CnaSource, EttodaySource, LtnSource]
