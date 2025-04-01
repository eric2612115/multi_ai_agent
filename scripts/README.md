# Multi-AI Agent 測試腳本

這個目錄包含用於測試 Multi-AI Agent 各項功能的獨立腳本。這些腳本可以幫助您逐一測試和調試不同的組件，而不需要啟動完整的 MCP 伺服器。

## 環境設置

首先，確保已經設置好環境變數：

```bash
cp ../.env.example ../.env
# 然後編輯 .env 文件，添加必要的 API 密鑰
```

## 可用測試腳本

### 1. 執行所有測試

這個腳本會依次運行所有功能測試，以確保系統的每個部分都能正常工作：

```bash
python run_all_tests.py
```

### 2. 測試 Gemini 功能

```bash
# 測試文字生成
python test_gemini.py --mode generate --prompt "寫一首關於 AI 的詩"

# 指定模型
python test_gemini.py --mode generate --prompt "寫一首關於 AI 的詩" --model "gemini-2.0-flash"

# 測試網頁搜索
python test_gemini.py --mode search --prompt "什麼是 MCP 協議"
```

### 3. 測試 Claude 功能

```bash
# 測試文字生成
python test_claude.py --mode generate --prompt "寫一首關於 AI 的詩"

# 測試計算 Token
python test_claude.py --mode count --prompt "這是一段用來測試 token 計算功能的文字"
```

### 4. 測試基本網頁爬取功能

```bash
# 測試爬取網頁
python test_basic_scrape.py --mode scrape --url "https://example.com"

# 指定格式
python test_basic_scrape.py --mode scrape --url "https://example.com" --formats "markdown,html"

# 測試網站映射
python test_basic_scrape.py --mode map --url "https://example.com"

# 使用搜索詞進行映射
python test_basic_scrape.py --mode map --url "https://example.com" --search "產品"
```

### 5. 測試智能網頁萃取功能

```bash
# 基本智能萃取
python test_smart_extraction.py --url "https://example.com" --objective "公司的產品和服務"

# 使用進階模型
python test_smart_extraction.py --url "https://example.com" --objective "公司的產品和服務" --advanced
```

### 6. 測試進階 API 萃取功能

```bash
# 從多個 URL 萃取信息
python test_advanced_extraction.py --urls "https://example.com,https://example.org" --objective "比較兩家公司的產品"

# 指定實體
python test_advanced_extraction.py --urls "https://example.com" --objective "產品和定價" --entity "Example Corp"
```

### 7. 測試 MCP 客戶端功能

這些測試會啟動 MCP 伺服器並通過 MCP 協議與其通信：

```bash
# 測試資源功能
python test_mcp_client.py resources

# 測試生成文字
python test_mcp_client.py generate --prompt "寫一首關於春天的詩" --service gemini

# 測試網頁爬取
python test_mcp_client.py scrape --url "https://example.com"

# 測試智能萃取
python test_mcp_client.py extract --url "https://example.com" --objective "公司的主要產品"
```

## 常見問題解決

### API 密鑰錯誤

如果看到 API 密鑰相關的錯誤，請確保在 `.env` 文件中正確設置了以下環境變數：

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `FIRECRAWL_API_KEY`

### 網絡連接問題

某些測試（尤其是網頁爬取和萃取）需要穩定的網絡連接。如果遇到連接超時錯誤，可能是由於網絡問題或目標網站的限制。

### 進階模型限制

使用 `--advanced` 選項的測試需要在 `.env` 文件中設置 `ENABLE_ADVANCED_MODELS=true`，並且您的 API 密鑰需要有訪問高級模型的權限。

### 運行時錯誤

如果腳本運行時出現錯誤，請查看錯誤信息以獲取詳細信息。大多數腳本會顯示完整的錯誤追踪信息，以幫助診斷問題。
