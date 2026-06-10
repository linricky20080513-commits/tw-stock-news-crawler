"""新聞資料模型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

# 台北時區 (UTC+8)
TZ_TAIPEI = timezone(timedelta(hours=8))


@dataclass
class NewsItem:
    """單則新聞。"""

    title: str
    url: str
    source: str                 # 來源名稱，例如「鉅亨網」
    summary: str = ""
    published_at: datetime | None = None   # 發布時間 (帶時區)
    stocks: list[str] = field(default_factory=list)  # 相關個股代號/名稱

    @property
    def uid(self) -> str:
        """以網址為基礎產生穩定的唯一識別碼，用於去重。"""
        return hashlib.md5(self.url.encode("utf-8")).hexdigest()

    @property
    def published_str(self) -> str:
        if self.published_at is None:
            return "—"
        return self.published_at.astimezone(TZ_TAIPEI).strftime("%Y-%m-%d %H:%M")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return d
