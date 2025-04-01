# Multi AI Agent

一個整合多種 AI 服務的代理框架，支援 Google Gemini、Anthropic Claude 和 Firecrawl 網頁抓取功能。

## 功能特色

- 支援多種 AI 客戶端：
  - **Google Gemini**: 文字生成、網頁搜尋、功能呼叫、多模態處理
  - **Anthropic Claude**: 文字生成、Token 計算、聊天對話
  - **Firecrawl**: 網頁抓取、網站地圖、智慧提取
- 智慧型網頁內容提取與分析
- 多模態輸入支援（文字、圖片）
- 標準化的客戶端介面，輕鬆切換不同 AI 服務

## 安裝步驟

1. 安裝相依套件:

```bash
pip install -r requirements.txt
```

2. 建立 `.env` 檔案並設置 API 金鑰:

```
# API Keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
SERP_API_KEY=your_serp_api_key_here  # Optional, used for advanced search

# Model Configuration
DEFAULT_AI_SERVICE=gemini  # Options: gemini, claude
MAX_TOKENS=1024
ENABLE_ADVANCED_MODELS=false  # Set to true to enable more expensive models

# Optional Advanced Gemini Configuration
GEMINI_STANDARD_MODEL=gemini-2.0-flash  # Standard model for most operations
GEMINI_PRO_MODEL=gemini-2.5-pro-exp-03-25  # Advanced model for complex tasks

# Optional Advanced Claude Configuration
CLAUDE_STANDARD_MODEL=claude-3-5-sonnet-20240620  # Standard model
CLAUDE_PRO_MODEL=claude-3-7-sonnet-20250219  # Advanced model for complex tasks
```

## 快速開始

### 使用多 AI 整合應用

```bash
python examples/multi_ai_integration.py
```

這個示範應用展示了如何整合 Gemini、Claude 和 Firecrawl 來執行複雜的資訊分析任務，包括:
- 網頁研究：使用多個 AI 服務研究特定主題
- 主題分析比較：比較 Gemini 和 Claude 對同一主題的分析結果
- 多模態分析：使用 Gemini 視覺模型分析圖片

### 使用 Google Gemini

```python
from src.multi_ai_agent.clients import GeminiClient

# 初始化客戶端
client = GeminiClient()

# 生成文字
response = client.generate_text("用中文寫一篇關於台灣的短文")
print(response)

# 網頁搜尋
search_result = client.search_web("台灣最高的山是什麼？")
print(search_result)
```

### 使用 Anthropic Claude

```python
from src.multi_ai_agent.clients import ClaudeClient

# 初始化客戶端
client = ClaudeClient()

# 生成文字
response = client.generate_text("說明台灣的地理特色")
print(response)

# 計算 Token
token_count = client.count_tokens("這是一段需要計算 token 數量的文字")
print(f"Token 數量: {token_count}")
```

### 使用 Firecrawl

```python
from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient

# 初始化客戶端
firecrawl = FirecrawlClient()
gemini = GeminiClient()

# 設置智慧提取服務
firecrawl.set_extraction_service(gemini_client=gemini)

# 抓取網頁
content = firecrawl.scrape_url("https://example.com")
print(content)

# 智慧資訊提取
data = firecrawl.smart_extract(
    url="https://www.taipei-101.com.tw",
    objective="找出台北 101 的高度以及建造時