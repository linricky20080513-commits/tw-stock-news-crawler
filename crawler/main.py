"""台股即時新聞爬蟲 — 命令列進入點。

範例:
    # 單次抓取，印出並存檔
    python -m crawler.main

    # 每 60 秒輪詢一次，即時監控新新聞 (Ctrl+C 結束)
    python -m crawler.main --watch --interval 60

    # 只看包含特定關鍵字的新聞 (例如台積電、AI)
    python -m crawler.main --watch --keywords 台積電 AI 聯發科

    # 只用鉅亨網來源
    python -m crawler.main --source cnyes
"""

from __future__ import annotations

import argparse
import sys
import time

from datetime import datetime

from .models import NewsItem, TZ_TAIPEI
from .sources import CnyesSource, CnaSource, EttodaySource, LtnSource
from .storage import Store

SOURCE_MAP = {
    "cnyes": CnyesSource,
    "cna": CnaSource,
    "ettoday": EttodaySource,
    "ltn": LtnSource,
}


def _force_utf8_console() -> None:
    """確保在預設非 UTF-8 的 Windows console (如 cp950) 印中文不會 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def build_sources(names: list[str]) -> list:
    if not names or "all" in names:
        return [cls() for cls in SOURCE_MAP.values()]
    return [SOURCE_MAP[n]() for n in names if n in SOURCE_MAP]


def collect(sources: list) -> list[NewsItem]:
    """從所有來源抓取，個別來源失敗不影響其他來源。"""
    items: list[NewsItem] = []
    for src in sources:
        try:
            fetched = src.fetch()
            items.extend(fetched)
            print(f"  [{src.name}] 取得 {len(fetched)} 則", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — 單一來源故障要能容錯
            print(f"  [{src.name}] 抓取失敗: {exc}", file=sys.stderr)
    return items


def match_keywords(item: NewsItem, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{item.title} {item.summary}"
    return any(kw in text for kw in keywords)


def print_item(item: NewsItem) -> None:
    stocks = f" 〔{' '.join(item.stocks)}〕" if item.stocks else ""
    print(f"\n[{item.published_str}] ({item.source}){stocks}")
    print(f"  {item.title}")
    print(f"  {item.url}")


def run_once(sources, store: Store, keywords: list[str]) -> int:
    raw = collect(sources)
    fresh = [it for it in store.filter_new(raw) if match_keywords(it, keywords)]
    # 依發布時間舊到新排序;沒有時間的排在最前面 (用最小時間當預設值)
    fresh.sort(key=lambda it: it.published_at or datetime.min.replace(tzinfo=TZ_TAIPEI))

    for item in fresh:
        print_item(item)
    store.add(fresh)
    store.flush()
    return len(fresh)


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = argparse.ArgumentParser(description="台股即時新聞爬蟲")
    parser.add_argument(
        "--source", nargs="+", default=["all"],
        choices=["all", "cnyes", "cna", "ettoday", "ltn"], help="新聞來源 (預設全部)",
    )
    parser.add_argument("--watch", action="store_true", help="持續輪詢監控模式")
    parser.add_argument("--interval", type=int, default=60, help="輪詢間隔秒數 (預設 60)")
    parser.add_argument("--keywords", nargs="+", default=[], help="只保留含這些關鍵字的新聞")
    parser.add_argument("--data-dir", default="data", help="輸出目錄 (預設 data/)")
    args = parser.parse_args(argv)

    sources = build_sources(args.source)
    store = Store(args.data_dir)

    if not args.watch:
        print("=== 單次抓取台股新聞 ===", file=sys.stderr)
        n = run_once(sources, store, args.keywords)
        print(f"\n本次新增 {n} 則，已存檔至 {store.json_path} / {store.csv_path}",
              file=sys.stderr)
        return 0

    print(f"=== 即時監控模式 (每 {args.interval} 秒)，Ctrl+C 結束 ===", file=sys.stderr)
    try:
        while True:
            n = run_once(sources, store, args.keywords)
            if n:
                print(f"  -> 新增 {n} 則", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已停止。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
