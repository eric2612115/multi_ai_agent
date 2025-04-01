#!/usr/bin/env python
"""
Firecrawl API 使用範例

這個腳本展示如何使用 FirecrawlClient 進行各種操作:
1. 基本網頁抓取
2. 網站地圖生成
3. 智能資訊提取 (搭配 Gemini 或 Claude)
"""
import os
import sys
import json
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient, ClaudeClient

def example_basic_scrape():
    """展示基本網頁抓取功能"""
    client = FirecrawlClient()
    
    url = "https://news.ycombinator.com"
    
    print(f"\n== 基本網頁抓取 ==")
    print(f"網址: {url}")
    print("-" * 40)
    
    # 使用 markdown 格式抓取
    result = client.scrape_url(url, formats=["markdown"])
    
    # 輸出前 500 字符
    markdown_content = result.get("markdown", "無內容")
    print(markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content)
    
    # 使用 HTML 格式抓取
    print("\n== HTML 抓取示例 ==")
    result = client.scrape_url(url, formats=["html"])
    
    # 輸出前 200 字符
    html_content = result.get("html", "無內容")
    print(html_content[:200] + "..." if len(html_content) > 200 else html_content)

def example_site_mapping():
    """展示網站地圖功能"""
    client = FirecrawlClient()
    
    url = "https://www.wikipedia.org"
    search_term = "Taiwan"
    
    print(f"\n== 網站地圖生成 ==")
    print(f"網址: {url}")
    print(f"搜尋詞: {search_term}")
    print("-" * 40)
    
    # 使用搜尋詞過濾結果
    result = client.map_url(url, search=search_term)
    
    # 輸出前 10 個連結
    links = result.get("urls", []) or result.get("links", [])
    if not links and isinstance(result, list):
        links = result
        
    if links:
        print(f"找到 {len(links)} 個相關連結:")
        for i, link in enumerate(links[:10]):
            print(f"{i+1}. {link}")
        if len(links) > 10:
            print(f"... 還有 {len(links) - 10} 個連結")
    else:
        print("找不到相關連結")

def example_smart_extraction():
    """展示智能資訊提取功能 (需要 Gemini 或 Claude)"""
    firecrawl = FirecrawlClient()
    
    # 初始化 AI 客戶端
    try:
        gemini = GeminiClient()
        print("\n== 使用 Gemini 智能提取 ==")
        firecrawl.set_extraction_service(gemini_client=gemini)
        has_ai = True
    except Exception as e:
        print(f"\n無法初始化 Gemini: {str(e)}")
        try:
            claude = ClaudeClient()
            print("\n== 使用 Claude 智能提取 ==")
            firecrawl.set_extraction_service(claude_client=claude)
            has_ai = True
        except Exception as e:
            print(f"\n無法初始化 Claude: {str(e)}")
            has_ai = False
    
    if not has_ai:
        print("智能提取需要 Gemini 或 Claude 客戶端")
        return
    
    # 進行智能提取
    url = "https://www.taipei-101.com.tw"
    objective = "找出台北 101 的高度以及建造時間"
    
    print(f"網址: {url}")
    print(f"目標: {objective}")
    print("-" * 40)
    
    result = firecrawl.smart_extract(
        url=url, 
        objective=objective,
        use_advanced_model=False  # 設置為 True 使用進階模型
    )
    
    if result:
        print("\n提取結果:")
        if isinstance(result, dict):
            # 格式化輸出
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result)
    else:
        print("無法提取所需資訊")

if __name__ == "__main__":
    # 載入環境變數
    load_dotenv()
    
    # 執行範例
    example_basic_scrape()
    example_site_mapping()
    example_smart_extraction()
