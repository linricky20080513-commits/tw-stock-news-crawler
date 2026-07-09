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
import ssl
import sys
import urllib.parse
import urllib.request
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


def _fetch_quotes(codes: list[str]) -> dict:
    """用證交所 MIS 即時報價 API 取每檔的漲跌幅%。上市(tse)/上櫃(otc)都試。"""
    result: dict = {}
    hdr = {"User-Agent": "Mozilla/5.0", "Referer": "https://mis.twse.com.tw/stock/index.jsp"}
    # 證交所憑證缺 Subject Key Identifier,Python 嚴格驗證會拒;此為唯讀公開報價,關閉驗證
    sslctx = ssl.create_default_context()
    sslctx.check_hostname = False
    sslctx.verify_mode = ssl.CERT_NONE

    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    for i in range(0, len(codes), 40):
        chunk = codes[i:i + 40]
        ex = "|".join(f"tse_{c}.tw" for c in chunk) + "|" + "|".join(f"otc_{c}.tw" for c in chunk)
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?json=1&delay=0&ex_ch=" + urllib.parse.quote(ex, safe="|_.")
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=8, context=sslctx) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — 單批失敗不影響其他
            continue
        for m in data.get("msgArray", []):
            c = m.get("c")
            if not c or c in result:
                continue
            z = _num(m.get("z"))                        # 現價(無成交為 "-")
            if z is None:
                z = _num(m.get("o")) or _num(m.get("b"))  # 退開盤/買價
            y = _num(m.get("y"))                        # 昨收
            pct = round((z - y) / y * 100, 2) if (z is not None and y) else None
            result[c] = {"name": m.get("n", ""), "price": z, "prev": y, "pct": pct, "time": m.get("t", "")}
    return result


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
        if parsed.path == "/api/quote":
            return self._handle_quote(parsed)
        if parsed.path.startswith("/api/hsg/"):
            return self._handle_api(parsed)
        return super().do_GET()

    def _handle_quote(self, parsed) -> None:
        qs = urllib.parse.parse_qs(parsed.query)
        raw = (qs.get("codes") or [""])[0]
        codes = [c.strip() for c in raw.split(",") if c.strip().isdigit()][:200]
        if not codes:
            return self._json({"error": "缺少股號 codes"}, 200)
        try:
            return self._json(_fetch_quotes(codes))
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": f"報價失敗:{exc}"}, 200)

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


class _Server(ThreadingHTTPServer):
    # 獨占綁定:埠已被別的行程佔用時要真正失敗(Windows 預設會允許重複綁),
    # 這樣下方的自動跳埠才會生效。
    allow_reuse_address = False


def _make_server() -> _Server:
    """綁定 PORT;若被佔用則自動往後找可用埠(最多 20 個)。"""
    last_err = None
    for port in range(PORT, PORT + 20):
        try:
            srv = _Server(("", port), Handler)
            srv._chosen_port = port  # type: ignore[attr-defined]
            if port != PORT:
                print(f"⚠ 埠 {PORT} 已被佔用,改用 {port}。")
            return srv
        except OSError as exc:
            last_err = exc
            continue
    raise SystemExit(f"找不到可用埠({PORT}~{PORT + 19} 都被佔用):{last_err}")


def main() -> int:
    _force_utf8_console()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    srv = _make_server()
    port = srv._chosen_port  # type: ignore[attr-defined]
    print(f"看板 + HSG 搜尋 API 已啟動 → http://localhost:{port}")
    print(f"HSG_PATH = {HSG_PATH}")
    print("Ctrl+C 結束")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
