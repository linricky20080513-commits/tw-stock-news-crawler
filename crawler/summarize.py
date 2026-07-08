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
import re
import sys

from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"

# 輸入預清理:先去掉最常見的記者署名/套語,省 token 也讓模型更專注在事實
_BOILER = [
    re.compile(r"[（(]\s*中央社[^）)]*[）)]"),          # (中央社記者○○○台北○日電)
    re.compile(r"[（(]\s*[^）)]{0,12}[／/][^）)]{0,8}報導\s*[）)]"),  # (記者○○/台北報導)
    re.compile(r"(綜合外電報導|綜合報導|編譯[^，。]{0,6}報導|路透社?|彭博資訊?|法新社|美聯社)"),
    re.compile(r"(本文|以上)?(內容|資訊)?不構成(任何)?投資(建議|參考)[^。]*。?"),
    re.compile(r"(投資人應|投資人須|讀者應)[^。]*自行(判斷|評估)[^。]*。?"),
    re.compile(r"更多[^。]{0,20}(請見|詳見|內容)[^。]*。?"),
]


def _strip_boiler(text: str) -> str:
    t = text or ""
    for rx in _BOILER:
        t = rx.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


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


def _compact(items: list[dict], snippet: int = 140) -> str:
    """把新聞壓成精簡清單(含內容摘要),供模型融合、去重、去廢話。"""
    lines = []
    for it in items:
        stocks = "、".join(it.get("stocks") or [])
        title = (it.get("title") or "").strip()
        src = it.get("source") or ""
        when = it.get("published_str") or it.get("published_at") or ""
        tag = f" 〔{stocks}〕" if stocks else ""
        body = _strip_boiler(it.get("summary") or "")
        if body:
            if len(body) > snippet:
                body = body[:snippet] + "…"
            lines.append(f"- [{when}] ({src}){tag} {title}｜{body}")
        else:
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
            "你是台股新聞分析助理。以下是近期台股新聞清單(時間、來源、相關個股股號、標題與內容摘要,"
            "以「｜」分隔標題與內容):\n\n"
            f"{compact}\n\n"
            "請閱讀這些新聞的『內容』,用繁體中文依 JSON schema 輸出三部分。核心要求:\n"
            "• **融合同一股號/同一事件跨來源的新聞內容**,把重複的資訊合併成一次陳述。\n"
            "• **去掉廢話與套語**——省略記者署名、消息來源、免責聲明、「據悉/據了解/值得注意的是/整體而言」"
            "等贅詞;只保留具體事實、數字、原因與影響。\n"
            "• 用精煉、資訊密度高的句子,不要開場白、不要條列符號。\n\n"
            "1. overall:120~200 字的今日市場重點(焦點主軸、最受關注個股、風險提示)。\n"
            "2. stocks:最多 10 檔最重要的個股。code 用清單中的『股號』(如 2330);"
            "points 用 1~2 句融合該股所有新聞內容後的精華重點(去重、去廢話,含關鍵數字)。\n"
            "3. events:把講同一件事的新聞聚成最多 6 個事件。title 簡短;"
            "summary 用 1~2 句融合該事件所有新聞內容的精華(去重、去廢話);stocks 列出相關股號。"
        )
    return (
        "You are a US-equities news analyst. Below is a list of recent US market news "
        "(time, source, related tickers, headline and content snippet, headline and snippet "
        "separated by '｜'):\n\n"
        f"{compact}\n\n"
        "Read the news CONTENT and output three parts per the JSON schema, in English. Core rules:\n"
        "• **Merge news about the same ticker / same event across sources**, collapsing repeated "
        "information into a single statement.\n"
        "• **Strip fluff and boilerplate** — drop bylines, source attributions, disclaimers, and "
        "filler ('reportedly', 'it is worth noting', 'overall'); keep only concrete facts, numbers, "
        "causes and effects.\n"
        "• Use tight, information-dense sentences; no preamble, no bullet characters.\n\n"
        "1. overall: a 120-200 word market summary (themes, notable tickers, risks).\n"
        "2. stocks: up to 10 most important tickers. code = the ticker as shown; points = 1-2 "
        "sentences of deduped, fluff-free key points synthesizing that ticker's news (keep numbers).\n"
        "3. events: cluster the news into up to 6 events. Short title; summary = 1-2 sentences "
        "merging that event's news (deduped, fluff-free); stocks = related tickers."
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
