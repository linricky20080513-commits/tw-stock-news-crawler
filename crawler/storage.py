"""新聞儲存:JSON / CSV 輸出與去重狀態管理。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import NewsItem


class Store:
    """負責把新聞落地，並記錄已看過的 uid 以避免重複。"""

    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.data_dir / "news.json"
        self.csv_path = self.data_dir / "news.csv"
        self._seen: set[str] = set()
        self._items: list[NewsItem] = []
        self._load()

    def _load(self) -> None:
        """載入既有 news.json，恢復去重狀態。"""
        if not self.json_path.exists():
            return
        try:
            raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for d in raw:
            uid = d.get("uid")
            if uid:
                self._seen.add(uid)

    def filter_new(self, items: list[NewsItem]) -> list[NewsItem]:
        """回傳尚未看過的新聞 (同一批內也去重)。"""
        fresh: list[NewsItem] = []
        batch_seen: set[str] = set()
        for item in items:
            if not item.url or item.uid in self._seen or item.uid in batch_seen:
                continue
            batch_seen.add(item.uid)
            fresh.append(item)
        return fresh

    def add(self, items: list[NewsItem]) -> None:
        """標記為已看過並累積到記憶體。"""
        for item in items:
            self._seen.add(item.uid)
            self._items.append(item)

    def flush(self) -> None:
        """把目前累積的所有新聞寫入 JSON 與 CSV (依發布時間新到舊排序)。"""
        # 合併既有 JSON 內容，避免覆蓋掉先前的紀錄
        existing: list[dict] = []
        if self.json_path.exists():
            try:
                existing = json.loads(self.json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []

        existing_uids = {d.get("uid") for d in existing}
        merged = existing + [
            it.to_dict() for it in self._items if it.uid not in existing_uids
        ]

        merged.sort(key=lambda d: d.get("published_at") or "", reverse=True)

        self.json_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with self.csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["發布時間", "來源", "標題", "相關個股", "網址", "摘要"])
            for d in merged:
                writer.writerow([
                    d.get("published_at") or "",
                    d.get("source", ""),
                    d.get("title", ""),
                    " ".join(d.get("stocks", []) or []),
                    d.get("url", ""),
                    d.get("summary", ""),
                ])

        self._items.clear()
