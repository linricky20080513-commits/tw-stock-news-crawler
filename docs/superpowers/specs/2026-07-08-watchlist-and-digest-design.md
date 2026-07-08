# 自選股篩選 + 新聞重點整理 — 設計文件

日期:2026-07-08
狀態:已與使用者確認,實作中

## 目標

在既有的零依賴單檔看板 `index.html` 上,新增兩個功能,**完全保留**原本新聞原文與所有現有功能(搜尋、來源/個股/時間篩選、排序、風險警示、個股彙整、台美股切換、雙語、主題)。

1. **自選股清單篩選**:只看使用者關注的股票的新聞。
2. **新聞重點整理**:自動歸納目前新聞的重點。

## 功能一:自選股清單篩選

### 資料來源(兩者並存)
- `data/watchlist.json`:股號字串陣列(TW 股號如 `"2330"`,US ticker 如 `"AAPL"`),進版控、當**預設種子**。首次上線為 `[]`。
- **看板內增刪**:存 `localStorage`(key:`dashWatch`)。生效清單 = localStorage 若存在則用它(覆蓋種子),否則用 `watchlist.json`。
- 輸入可打**股號或名稱**;名稱用 `stocks.json`(STOCK_MAP)反查為股號。

### 行為
- `state.watchOnly`(boolean,存 localStorage `dashWatchOnly`)。
- `applyFilters()` 增加一條:`watchOnly` 為真時,只留 `stocks` 命中生效清單股號的新聞。與所有現有篩選 AND 疊加。
- UI:
  - 控制列新增 `★ 只看自選` 切換鈕、`⚙ 自選股` 開啟管理面板鈕。
  - 管理面板:輸入框(股號/名稱 → Enter 加入)、目前清單 chips(各含 ✕ 移除)、清空、還原預設。
  - 新聞卡片的個股標籤旁加 `☆/★` 快速加入/移出。
  - `renderActiveFilters` 增加「只看自選」chip。
- `setMarket()` 切換市場時一併重置 `watchOnly`(比照現有清篩選邏輯)。清單本身跨市場共用(TW 股號與 US ticker 不互相命中,天然分離)。

## 功能二:新聞重點整理

### A 階段:規則式(純前端、零依賴、立即可用)
- 新增可折疊「重點整理」面板(`🧾 重點整理` 切換鈕,狀態存 localStorage `dashDigest`)。
- 依**目前篩選後**的新聞計算(所以「只看自選 + 重點整理」= 關注股票的重點):
  - **總覽**:則數、涵蓋個股數、來源數、時間範圍。
  - **個股重點表**:每檔股票一列 — 則數、最新標題(連回原文)、來源分布、命中風險關鍵字;依則數排序。
  - **熱門關鍵字**:目前新聞命中的風險/重點關鍵字次數 Top 10。
  - **風險提示**:接現有 `computeRiskStocks`(限縮到目前新聞)。
- **原文保留**:重點面板是附加視圖,新聞卡片與原文一字不動,重點內標題皆連回原文網址。

### B 階段:AI 生成式(接好但休眠,待金鑰啟用)
- `crawler/summarize.py`:讀 `data/news.json` / `news_us.json`,呼叫 **Claude**(`ANTHROPIC_API_KEY`)產生自然語句重點,輸出 `data/summary.json`:
  ```json
  { "tw": {"generated_at":"…","overall":"…","stocks":{"2330":"…"}},
    "us": {"generated_at":"…","overall":"…","stocks":{"AAPL":"…"}} }
  ```
- `.github/workflows/crawl.yml`:新增一步跑 `summarize.py`,**僅在 secret 存在時執行**(`if: env.ANTHROPIC_API_KEY != ''`),把 `summary.json` 一併 commit。
- 看板:載入時嘗試 fetch `data/summary.json`;有對應市場內容 → 於重點面板頂端顯示 AI 重點;**沒有就自動只顯示 A 階段規則式**。因此未設金鑰前一切照常、不會壞。會產生 API 費用。

## 版控 / 檔案
- `.gitignore` 例外納入 `data/watchlist.json`、`data/summary.json`。
- 動到的檔:`index.html`(主要)、`data/watchlist.json`(新)、`crawler/summarize.py`(新)、`.github/workflows/crawl.yml`、`.gitignore`、`README.md`。

## 驗證
- 無測試框架(既有專案亦無)。以下列方式驗證:
  1. `node --check` 對 `<script>` 內容做 JS 語法檢查。
  2. `python -m http.server` 起站,確認頁面載入、原有功能不回歸。
  3. 手動驗證:加自選股 → 只看自選過濾正確;重點面板數字與清單一致;無金鑰時 AI 區塊不出現且不報錯。
