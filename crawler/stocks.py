"""台股代號 → 名稱對照表。

從證交所 (上市) 與櫃買中心 (上櫃) 的公開 OpenAPI 抓取全市場代號與名稱,
合併寫成 data/stocks.json,供前端看板把股號旁顯示股票名稱。

對照表變動很慢,故預設只在檔案不存在或超過 max_age_hours 才重新抓取。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

# 上市:每日收盤行情(含 Code / Name,涵蓋股票與 ETF)
TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
# 上櫃:主板每日收盤行情(含 SecuritiesCompanyCode / CompanyName)
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_stock_map() -> dict[str, str]:
    """抓取並合併上市 + 上櫃的 {代號: 名稱}。單一來源失敗不影響另一來源。"""
    mapping: dict[str, str] = {}

    try:
        r = requests.get(TWSE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        for row in r.json():
            code = (row.get("Code") or "").strip()
            name = (row.get("Name") or "").strip()
            if code and name:
                mapping[code] = name
        print(f"  [stocks] 上市 {len(mapping)} 檔", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — 容錯,單一來源失敗不中斷
        print(f"  [stocks] 上市抓取失敗: {exc}", file=sys.stderr)

    try:
        r = requests.get(TPEX_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        before = len(mapping)
        for row in r.json():
            code = (row.get("SecuritiesCompanyCode") or "").strip()
            name = (row.get("CompanyName") or "").strip()
            if code and name and code not in mapping:
                mapping[code] = name
        print(f"  [stocks] 上櫃 +{len(mapping) - before} 檔", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  [stocks] 上櫃抓取失敗: {exc}", file=sys.stderr)

    return mapping


def update_stock_map(data_dir: str | Path, max_age_hours: float = 12) -> int:
    """必要時更新 data/stocks.json。

    回傳寫入的檔數;若因檔案仍新鮮而略過則回傳 -1;抓取失敗回傳 0。
    """
    data_dir = Path(data_dir)
    path = data_dir / "stocks.json"

    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h < max_age_hours:
            return -1  # 仍新鮮,略過

    mapping = fetch_stock_map()
    if not mapping:
        return 0

    data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return len(mapping)
