# 台股即時新聞爬蟲 (tw-stock-news-crawler)

爬取台股即時新聞的 Python 專案。從多個公開來源抓取最新新聞,自動去重,
支援**單次抓取**與**輪詢即時監控**,並可依關鍵字過濾、輸出成 JSON / CSV。

## 新聞來源

| 代號 | 來源 | 方式 | 說明 |
|------|------|------|------|
| `cnyes`   | 鉅亨網   | JSON API | 主來源,結構化、含發布時間與相關個股代號 |
| `cna`     | 中央社   | RSS | 財經新聞 |
| `ettoday` | ETtoday  | RSS | 財經新聞 |
| `ltn`     | 自由財經 | RSS | 自由時報財經即時新聞 |
| `udn`     | 經濟日報 (要聞) | RSS | 財經新聞 |
| `technews`| 科技新報 | RSS | 科技/產業新聞 |
| `mirror`  | 鏡週刊財經 | RSS | 財經深度/時事 |
| `udnstock`| 經濟日報 股市 | RSS | 台股盤勢、個股 |
| `udnmacro`| 經濟日報 總經 | RSS | 產業‧總體經濟 |
| `udnbiz`  | 聯合財經 | RSS | 聯合新聞網財經 |
| `yahootw` | Yahoo 股市 | RSS | Yahoo 奇摩股市/財經 |
| `financetech`| 財經新報 | RSS | 科技新報財經站 |
| **美股** (`--market us`) | CNBC(市場/財經/頭條/科技)、MarketWatch、Yahoo Finance、Investing.com、NYT Business、WSJ Markets、Business Insider、Motley Fool | RSS | 共 11 個來源,輸出到 `news_us.json` |

> 台股 RSS 來源會自動從「名稱(股號)」格式擷取股號(如 台積電(2330));部分只寫公司名的來源不一定有股號。
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

# 抓美股新聞 (CNBC / MarketWatch)，存到 data/news_us.json
python run.py --market us

# 指定輸出目錄
python run.py --data-dir my_data
```

### 參數

| `--source`   | `all` | 台股來源,可多選:`cnyes` `cna` `ettoday` `ltn` `udn` `technews` `all` |
| `--watch`    | 關閉  | 持續輪詢的即時監控模式 |
| `--interval` | `60`  | 輪詢間隔秒數 |
| `--keywords` | 無    | 只保留標題/摘要含這些關鍵字的新聞 |
| `--data-dir` | `data`| 輸出目錄 |

## 輸出

- `data/news.json` — 完整結構化資料 (UTF-8),每次執行**累積合併**並依時間新到舊排序。
- `data/news.csv` — 同內容的試算表 (UTF-8 BOM,可直接用 Excel 開)。
- `data/stocks.json` — 全市場**股號→名稱**對照表 (上市+上櫃),供看板把股號旁顯示股票名稱。
  由 `crawler/stocks.py` 從證交所/櫃買 OpenAPI 抓取,**每 12 小時**才更新一次 (自帶節流)。
- `data/news_us.json` / `news_us.csv` — **美股**新聞 (`--market us`),格式同台股。看板右上角可一鍵切換台股/美股。

每則新聞欄位:發布時間、來源、標題、相關個股、網址、摘要。
跨執行去重:已抓過的網址 (以 MD5 為 `uid`) 不會重複寫入或重複顯示。

## 前端看板

根目錄的 `index.html` 是一個零依賴的單檔視覺化看板,直接讀取 `data/news.json`。
在專案根目錄起一個本機 HTTP 伺服器再開啟即可 (不要直接雙擊,`file://` 會被瀏覽器擋住 fetch):

```powershell
python -m http.server 8000
# 開啟 http://localhost:8000
```

> 想在看板上用**網路搜尋 (HSG)** 功能,請改用 `python serve.py`(見下方「網路搜尋」),
> 它同時提供看板與 HSG 搜尋 API;純看看板則 `http.server` 即可。

功能:統計卡片、**來源分布甜甜圈圖 (含則數與百分比)**、熱門個股前 10、
**來源 × 時間趨勢堆疊柱狀圖**、關鍵字搜尋、來源/個股/時間範圍篩選與排序。
爬蟲跑完後按看板上的「↻ 重新整理」即可載入最新資料。

### 自選股清單

看板可只顯示你關注的股票的新聞:

- **`★ 只看自選`**:切換只看自選股相關新聞(與其他篩選 AND 疊加)。
- **`⚙ 自選股`**:開啟管理面板,輸入**股號或名稱**(例如 `2330` 或 `台積電`,可空白/逗號一次多筆)按 Enter 加入;也可還原預設或清空。
- 每則新聞的個股標籤旁有 **☆/★** 可快速加入/移出。
- 清單來源:`data/watchlist.json`(股號陣列,進版控當**預設種子**)+ **瀏覽器 localStorage**(你在看板上的增刪會覆蓋預設)。

### 新聞重點整理

**`🧾 重點整理`** 切換一個面板,依**目前篩選結果**自動歸納。面板上方可切換三種分組:

- **總覽**:總覽數字、個股重點表(則數/最新標題連回原文/來源/風險關鍵字)、熱門關鍵字、風險提示。
- **依個股**:把每支股票的新聞**依「日」分段**——每一天(今天/昨天/日期)先顯示一段 AI 寫的**簡短但詳細**重點(有金鑰時,融合當天新聞、去重去廢話、含關鍵數字),下方列出當日新聞標題(連回原文);未設金鑰時只顯示當日標題,不會空白。
- **依事件**:把講同一件事的新聞聚成事件/主題並摘要。有 `data/summary.json`(AI)時用 AI 事件聚類;否則用規則式關鍵詞聚類當後備。

**去重**:「依個股 / 依事件」的條列會把**同一件事被多家報導、標題幾乎相同**的新聞折成一則(標示合併來源數),讓重點更乾淨。**新聞列表本身不去重、原文完全保留**——重點面板只是附加視圖。

規則式重點是純前端、零依賴、免費即時。若要**AI 生成式**的自然語句重點(選用):

1. 在 GitHub repo 設 secret `ANTHROPIC_API_KEY`(Settings → Secrets and variables → Actions)。
2. 每小時的 Action 會跑 `crawler/summarize.py`,把新聞**內容**(不只標題)餵給 Claude,**融合同一股號/同一事件的跨來源新聞、去除重複資訊、濾掉套語與贅詞(記者署名、外電來源、免責聲明、「據悉/值得注意的是」等),只保留具體事實與數字**,產生 `data/summary.json`——含整體重點 `overall`、**每股每日重點 `stocks[].days[]`(依日期,每天一段簡短但詳細)**、**事件精華重點 `events[]`**。看板自動顯示(依個股卡片每日一段「✦ AI 重點」;依事件「✦ AI 事件精華重點」)。
   > `summarize.py` 也會在送出前先輕量去除記者署名等套語以節省 token;每個市場預設取最新 40 則(`SUMMARY_MAX_ITEMS` 可調)。
3. 想省錢可在 repo variables 設 `SUMMARY_MODEL=claude-haiku-4-5`(預設 `claude-opus-4-8`)。
4. **未設金鑰時一切照常**——AI 區塊不出現,看板只顯示規則式重點,不會壞。會產生 API 費用。

### 網路搜尋 (HSG)

看板上的 **`🔎 網路搜尋`** 面板可即時搜網路(HSG / DuckDuckGo,免金鑰),每筆結果可按「📄 爬正文」把該頁內容抽出來看。

因為看板是靜態頁、瀏覽器不能直接呼叫 Python,這個功能需要一個本機小後端:

```powershell
# 用 serve.py 取代 http.server(同時提供看板 + HSG API)
python serve.py
# 開啟 http://localhost:8000,點「🔎 網路搜尋」

# HSG 不在預設路徑時,用環境變數指定:
set HSG_PATH=D:/path/to/HSG && python serve.py
```

- 需先安裝 HSG 依賴:`python -m pip install ddgs httpx beautifulsoup4 lxml`。
- API:`GET /api/hsg/search?q=關鍵字&n=10`、`GET /api/hsg/fetch?url=...`。
- **僅本機可用**:公開的 GitHub Pages 沒有後端,面板會顯示提示、不影響其他功能。

## 每日自動更新 (GitHub Actions)

`.github/workflows/crawl.yml` 每天 **09:00 UTC(台北 17:00)** 自動抓台股+美股、更新 `data/*.json` 並 push,觸發 GitHub Pages 重建。也可到 Actions 頁面「Run workflow」手動觸發。改時間就編輯 `cron` 那行(UTC)。

## 專案結構

```
tw-stock-news-crawler/
├─ index.html              # 前端看板 (零依賴,讀 data/news.json)
├─ serve.py                # 本機看板伺服器 + HSG 網路搜尋 API (網路搜尋功能用)
├─ run.py                  # 啟動器 (處理 sys.path / 編碼)
├─ requirements.txt
├─ crawler/
│  ├─ main.py              # CLI 進入點:單次 / 監控、關鍵字過濾
│  ├─ models.py            # NewsItem 資料模型 (含去重 uid、台北時區)
│  ├─ stocks.py            # 股號→名稱對照表 (證交所/櫃買 OpenAPI → data/stocks.json)
│  ├─ storage.py           # JSON/CSV 落地 + 去重狀態
│  ├─ summarize.py         # AI 重點整理 (選用,需 ANTHROPIC_API_KEY → data/summary.json)
│  └─ sources/
│     ├─ cnyes.py          # 鉅亨網 JSON API
│     └─ rss.py            # 通用 RSS (中央社、ETtoday)
├─ data/                   # 輸出 (執行後產生)
│  ├─ watchlist.json       # 自選股種子 (股號陣列)
│  └─ summary.json         # AI 重點 (選用,summarize.py 產生)
└─ .github/workflows/
   └─ crawl.yml            # 每日自動抓取 + 發佈 GitHub Pages
```

## 擴充新來源

在 `crawler/sources/` 新增一個類別,實作 `name` 屬性與 `fetch() -> list[NewsItem]`,
再加進 `crawler/sources/__init__.py` 與 `crawler/main.py` 的 `SOURCE_MAP`。
RSS 來源可直接沿用 `RSSSource(name, url)`。

## 注意事項

- 請尊重各網站的使用條款與 `robots.txt`,輪詢間隔勿過短 (建議 ≥ 30 秒) 以免造成負擔。
- 抓到的新聞僅供研究參考,不構成投資建議。
- 單一來源若暫時失敗 (網路/改版),不會影響其他來源,程式會印出警告並繼續。
