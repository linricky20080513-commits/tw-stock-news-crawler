#!/usr/bin/env python
"""本機看板伺服器 + HSG 搜尋 API。

同時提供:
  - 靜態看板 (index.html / data/*)  ← 取代 `python -m http.server`
  - HSG 搜尋/爬正文 API,給看板的「網路搜尋」面板呼叫

用法:
    python serve.py                    # http://localhost:8000
    set HSG_PATH=D:/path/to/HSG && python serve.py   # 指定 HSG 位置
    set PORT=8001 && python serve.py

API:
    GET /api/hsg/search?q=關鍵字&n=10          -> {query, results:[{title,url,snippet}]}
    GET /api/hsg/fetch?url=...&max_chars=4000  -> {url, title, text}

HSG 未安裝或路徑錯誤時,API 回 {"error": "..."},看板會顯示提示;
不影響看板其它功能(此搜尋功能僅在本機跑本檔時可用,GitHub Pages 無後端)。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# HSG 專案位置(可用環境變數 HSG_PATH 覆蓋)
HSG_PATH = os.environ.get("HSG_PATH", r"C:\Users\linch\Downloads\CLAUDE\HSG")
PORT = int(os.environ.get("PORT", "8000"))

_HSG = None
_HSG_ERR = None


def _force_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _load_hsg():
    """延遲載入 HSG;失敗只記錄一次,API 回傳友善錯誤。"""
    global _HSG, _HSG_ERR
    if _HSG is not None:
        return _HSG
    if _HSG_ERR is not None:
        raise RuntimeError(_HSG_ERR)
    try:
        if HSG_PATH and HSG_PATH not in sys.path:
            sys.path.insert(0, HSG_PATH)
        import hsg  # noqa: E402
        _HSG = hsg
        return hsg
    except Exception as exc:  # noqa: BLE001
        _HSG_ERR = (f"HSG 無法載入:{exc}。請確認 HSG_PATH={HSG_PATH!r} 正確、"
                    f"且已安裝依賴 (pip install ddgs httpx beautifulsoup4 lxml)。")
        raise RuntimeError(_HSG_ERR)


class Handler(SimpleHTTPRequestHandler):
    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/hsg/"):
            return self._handle_api(parsed)
        return super().do_GET()

    def _handle_api(self, parsed) -> None:
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            hsg = _load_hsg()
        except RuntimeError as exc:
            return self._json({"error": str(exc)}, 200)
        try:
            if parsed.path == "/api/hsg/search":
                q = (qs.get("q") or [""])[0].strip()
                n = max(1, min(20, int((qs.get("n") or ["10"])[0])))
                if not q:
                    return self._json({"error": "缺少搜尋關鍵字 q"}, 200)
                return self._json({"query": q, "results": hsg.search(q, n)})
            if parsed.path == "/api/hsg/fetch":
                url = (qs.get("url") or [""])[0]
                mc = max(200, min(20000, int((qs.get("max_chars") or ["4000"])[0])))
                if not url:
                    return self._json({"error": "缺少網址 url"}, 200)
                return self._json(hsg.fetch(url, mc))
            return self._json({"error": "未知的 API 路徑"}, 404)
        except Exception as exc:  # noqa: BLE001 — 抓取失敗回友善訊息
            return self._json({"error": f"HSG 執行失敗:{exc}"}, 200)

    def log_message(self, *args):  # 靜音存取日誌
        pass


def main() -> int:
    _force_utf8_console()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"看板 + HSG 搜尋 API 已啟動 → http://localhost:{PORT}")
    print(f"HSG_PATH = {HSG_PATH}")
    print("Ctrl+C 結束")
    try:
        ThreadingHTTPServer(("", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
