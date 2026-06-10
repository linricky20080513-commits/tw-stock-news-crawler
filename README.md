# 台股即時新聞爬蟲 (tw-stock-news-crawler)

爬取台股即時新聞的 Python 專案。從多個公開來源抓取最新新聞,自動去重,
支援**單次抓取**與**輪詢即時監控**,並可依關鍵字過濾、輸出成 JSON / CSV。

## 新聞來源

| 代號 | 來源 | 方式 | 說明 |
|------|------|------|------|
| `cnyes`   | 鉅亨網   | JSON API | 主來源,結構化、含發布時間與相關個股代號 |
| `cna`     | 中央社   | RSS | 財經新聞 |
| `ettoday` | ETtoday  | RSS | 財經新聞 |

> 原本規劃的 Yahoo 股市 RSS 已被官方擋掉 (HTTP 999),故改用中央社與 ETtoday。

## 安裝

需要 Python 3.10+。

```powershell
python -m pip install -r requirements.txt
```

> 若你用的是 Windows **embeddable** 版 Python (本機即是),pip 不在 PATH,
> 請改用 `python -m pip ...`;且務必透過根目錄的 `run.py` 啟動 (見下)。

## 使用

建議用根目錄的 `run.py` 啟動 (它會處理好模組路徑與 console 編碼):

```powershell
# 單次抓取所有來源,印出並存檔到 data/
python run.py

# 即時監控:每 60 秒輪詢一次,只顯示新出現的新聞 (Ctrl+C 結束)
python run.py --watch --interval 60

# 只看含特定關鍵字的新聞
python run.py --watch --keywords 台積電 AI 聯發科

# 只用鉅亨網來源
python run.py --source cnyes

# 指定輸出目錄
python run.py --data-dir my_data
```

### 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--source`   | `all` | 來源,可多選:`cnyes` `cna` `ettoday` `all` |
| `--watch`    | 關閉  | 持續輪詢的即時監控模式 |
| `--interval` | `60`  | 輪詢間隔秒數 |
| `--keywords` | 無    | 只保留標題/摘要含這些關鍵字的新聞 |
| `--data-dir` | `data`| 輸出目錄 |

## 輸出

- `data/news.json` — 完整結構化資料 (UTF-8),每次執行**累積合併**並依時間新到舊排序。
- `data/news.csv` — 同內容的試算表 (UTF-8 BOM,可直接用 Excel 開)。

每則新聞欄位:發布時間、來源、標題、相關個股、網址、摘要。
跨執行去重:已抓過的網址 (以 MD5 為 `uid`) 不會重複寫入或重複顯示。

## 專案結構

```
tw-stock-news-crawler/
├─ run.py                  # 啟動器 (處理 sys.path / 編碼)
├─ requirements.txt
├─ crawler/
│  ├─ main.py              # CLI 進入點:單次 / 監控、關鍵字過濾
│  ├─ models.py            # NewsItem 資料模型 (含去重 uid、台北時區)
│  ├─ storage.py           # JSON/CSV 落地 + 去重狀態
│  └─ sources/
│     ├─ cnyes.py          # 鉅亨網 JSON API
│     └─ rss.py            # 通用 RSS (中央社、ETtoday)
└─ data/                   # 輸出 (執行後產生)
```

## 擴充新來源

在 `crawler/sources/` 新增一個類別,實作 `name` 屬性與 `fetch() -> list[NewsItem]`,
再加進 `crawler/sources/__init__.py` 與 `crawler/main.py` 的 `SOURCE_MAP`。
RSS 來源可直接沿用 `RSSSource(name, url)`。

## 注意事項

- 請尊重各網站的使用條款與 `robots.txt`,輪詢間隔勿過短 (建議 ≥ 30 秒) 以免造成負擔。
- 抓到的新聞僅供研究參考,不構成投資建議。
- 單一來源若暫時失敗 (網路/改版),不會影響其他來源,程式會印出警告並繼續。
