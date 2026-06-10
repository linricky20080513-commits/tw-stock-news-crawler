"""新聞翻譯:為 news JSON 補上中英雙語欄位。

使用免費的 Google 翻譯端點 (client=gtx,免金鑰)。每則新聞補上
title_zh / title_en / summary_zh / summary_en 四個欄位:
同語言欄位直接放原文,另一語言則呼叫翻譯。

為避免一次發太多請求,每次執行最多翻譯 max_items 則尚缺翻譯的新聞;
搭配輪詢/排程,幾次之後就能把既有資料補齊。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def translate_text(text: str, target: str) -> str | None:
    """把 text 翻成 target 語言 (en / zh-TW)。失敗回傳 None。"""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        params = {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text}
        r = requests.get(_ENDPOINT, params=params, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception:  # noqa: BLE001 — 翻譯失敗不影響主流程
        return None


def translate_file(path: str | Path, source_lang: str, max_items: int = 25) -> int:
    """為 news JSON 補上雙語欄位。

    source_lang: 原文語言 'zh' 或 'en'。回傳本次實際翻譯的則數。
    """
    path = Path(path)
    if not path.exists():
        return 0
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    other = "en" if source_lang == "zh" else "zh"
    tl = "en" if other == "en" else "zh-TW"

    done = 0
    for it in items:
        if done >= max_items:
            break
        # 四個欄位都齊了就跳過
        if (it.get(f"title_{source_lang}") is not None
                and it.get(f"title_{other}") is not None):
            continue

        title = it.get("title", "") or ""
        summary = it.get("summary", "") or ""

        # 翻譯另一語言;失敗就略過這則 (保持缺欄,下次再補)
        t_other = translate_text(title, tl)
        if t_other is None:
            continue
        s_other = translate_text(summary, tl) if summary else ""
        if s_other is None:
            s_other = ""

        it[f"title_{source_lang}"] = title
        it[f"summary_{source_lang}"] = summary
        it[f"title_{other}"] = t_other
        it[f"summary_{other}"] = s_other
        done += 1
        time.sleep(0.12)

    if done:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [translate] 翻譯 {done} 則 -> {path.name}", file=sys.stderr)
    return done
