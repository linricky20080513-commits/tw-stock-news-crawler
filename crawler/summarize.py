"""AI 新聞重點整理（B 階段,休眠功能）。

讀取 data/news.json / news_us.json,呼叫 Claude 產生自然語句的「重點整理」,
輸出到 data/summary.json,供前端看板顯示。

設計原則:
- **需要金鑰才會動作**。未設定 ANTHROPIC_API_KEY 時直接跳過(不寫檔、正常結束),
  因此在使用者設定 GitHub secret 之前,整條流程與看板都照常運作、不會壞。
- 每個市場只取最近數十則,壓成精簡清單餵給模型,控制 token 成本。

用法:
    python -m crawler.summarize            # 兩個市場都做
    ANTHROPIC_API_KEY=... python -m crawler.summarize

環境變數:
    ANTHROPIC_API_KEY   Anthropic 金鑰(必要,否則跳過)
    SUMMARY_MODEL       模型 ID(預設 claude-opus-4-8;想省錢可設 claude-haiku-4-5)
    SUMMARY_MAX_ITEMS   每個市場餵給模型的最新新聞則數(預設 40)
"""

from __future__ import annotations

import json
import os
import sys

from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"


def _load_items(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    # 依發布時間新到舊,取前 limit 則
    items.sort(key=lambda it: it.get("published_at") or "", reverse=True)
    return items[:limit]


def _compact(items: list[dict]) -> str:
    """把新聞壓成精簡文字清單,節省 token。"""
    lines = []
    for it in items:
        stocks = "、".join(it.get("stocks") or [])
        title = it.get("title") or ""
        src = it.get("source") or ""
        when = it.get("published_str") or it.get("published_at") or ""
        tag = f" 〔{stocks}〕" if stocks else ""
        lines.append(f"- [{when}] ({src}){tag} {title}")
    return "\n".join(lines)


# 結構化輸出 schema:整體重點 + 每股重點 + 事件聚類
_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overall": {"type": "string"},
        "stocks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": {"type": "string"},
                    "points": {"type": "string"},
                },
                "required": ["code", "points"],
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "stocks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "summary", "stocks"],
            },
        },
    },
    "required": ["overall", "stocks", "events"],
}


def _prompt(market: str, compact: str) -> str:
    if market == "tw":
        return (
            "你是台股新聞分析助理。以下是近期台股新聞清單(時間、來源、相關個股股號、標題):\n\n"
            f"{compact}\n\n"
            "請用繁體中文,依 JSON schema 輸出三部分:\n"
            "1. overall:一段 120~200 字的今日市場重點(焦點主軸、最受關注個股、風險提示;通順段落,不條列、不開場白、不免責聲明)。\n"
            "2. stocks:最多 10 檔被最多提及或最重要的個股,每檔 code 用清單中出現的『股號』(如 2330),"
            "points 用 1~2 句話彙整該股所有相關新聞的重點。\n"
            "3. events:把講同一件事的新聞聚成最多 6 個事件/主題,每個 title 簡短、summary 用 1~2 句話說明,"
            "stocks 列出相關股號。"
        )
    return (
        "You are a US-equities news analyst. Below is a list of recent US market news "
        "(time, source, related tickers, headline):\n\n"
        f"{compact}\n\n"
        "Output three parts per the JSON schema, in English:\n"
        "1. overall: a 120-200 word market summary (main themes, most notable tickers, risks; "
        "flowing prose, no bullets, no preamble, no disclaimer).\n"
        "2. stocks: up to 10 most-mentioned or most important tickers; code is the ticker as it "
        "appears in the list, points is a 1-2 sentence synthesis of that ticker's news.\n"
        "3. events: cluster the news into up to 6 distinct events/themes; each with a short title, "
        "a 1-2 sentence summary, and the related tickers in stocks."
    )


def summarize_market(client, model: str, market: str, items: list[dict]) -> dict | None:
    if not items:
        return None
    compact = _compact(items)
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": _prompt(market, compact)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        return None
    try:
        data = json.loads(text)  # output_config.format 保證是合法 JSON
    except json.JSONDecodeError:
        return None
    if not data.get("overall"):
        return None
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
        "model": model,
        "overall": data.get("overall", ""),
        "stocks": data.get("stocks", []),
        "events": data.get("events", []),
    }


def main(argv: list[str] | None = None) -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[summarize] 未設定 ANTHROPIC_API_KEY,略過 AI 重點整理。", file=sys.stderr)
        return 0

    try:
        import anthropic  # 延遲匯入:沒裝套件也不影響爬蟲主流程
    except ImportError:
        print("[summarize] 未安裝 anthropic 套件(pip install anthropic),略過。", file=sys.stderr)
        return 0

    model = os.environ.get("SUMMARY_MODEL", DEFAULT_MODEL)
    limit = int(os.environ.get("SUMMARY_MAX_ITEMS", "40"))
    data_dir = Path(os.environ.get("SUMMARY_DATA_DIR", "data"))

    client = anthropic.Anthropic(api_key=api_key)

    out: dict = {}
    for market, name in (("tw", "news"), ("us", "news_us")):
        items = _load_items(data_dir / f"{name}.json", limit)
        if not items:
            print(f"[summarize] {market}: 無新聞可整理,跳過。", file=sys.stderr)
            continue
        try:
            result = summarize_market(client, model, market, items)
        except Exception as exc:  # noqa: BLE001 — 單一市場失敗不影響另一個
            print(f"[summarize] {market}: 產生重點失敗: {exc}", file=sys.stderr)
            continue
        if result:
            out[market] = result
            print(f"[summarize] {market}: 已產生重點({len(items)} 則 → {len(result['overall'])} 字)", file=sys.stderr)

    if not out:
        print("[summarize] 沒有產生任何重點,不寫檔。", file=sys.stderr)
        return 0

    path = data_dir / "summary.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[summarize] 已寫入 {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
