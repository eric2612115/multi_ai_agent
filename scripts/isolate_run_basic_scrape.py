#!/usr/bin/env python
"""
獨立測試腳本 - Firecrawl 基本爬取功能
這個腳本直接測試 Firecrawl 客戶端的基本爬取功能，不需要啟動 MCP 伺服器。
"""
import os
import sys
import json
import argparse
import pytest
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import FirecrawlClient

@pytest.fixture
def default_url():
    return "https://modelcontextprotocol.io"

@pytest.fixture
def default_formats():
    return ['markdown']

@pytest.fixture
def default_search():
    return "python"

def test_basic_scrape(default_url, default_formats):
    """測試基本網頁爬取功能"""
    url = default_url
    formats = default_formats
        
    print(f"測試基本網頁爬取功能")
    print(f"URL: {url}")
    print(f"格式: {', '.join(formats)}")
    print("-" * 40)
    
    try:
        # 初始化 Firecrawl 客戶端
        client = FirecrawlClient()
        
        # 爬取網頁
        result = client.scrape_url(url, formats)
        
        # 顯示結果
        print("\n爬取結果：")
        if isinstance(result, dict):
            if 'formats' in result:
                for fmt in formats:
                    if fmt in result['formats']:
                        content = result['formats'][fmt]
                        if isinstance(content, str):
                            preview = content[:500] + "..." if len(content) > 500 else content
                            print(f"\n{fmt.upper()} 格式 (前 500 字元):")
                            print(preview)
                        else:
                            print(f"\n{fmt.upper()} 格式:")
                            print(json.dumps(content, indent=2)[:500] + "..." if len(json.dumps(content, indent=2)) > 500 else json.dumps(content, indent=2))
            elif fmt in result:
                content = result[fmt]
                if isinstance(content, str):
                    preview = content[:500] + "..." if len(content) > 500 else content
                    print(f"\n{fmt.upper()} 格式 (前 500 字元):")
                    print(preview)
                else:
                    print(f"\n{fmt.upper()} 格式:")
                    print(json.dumps(content, indent=2)[:500] + "..." if len(json.dumps(content, indent=2)) > 500 else json.dumps(content, indent=2))
        else:
            print("結果格式非預期:")
            print(str(result)[:500])
        
        print("\n✅ 測試成功!")
        assert result, "爬取結果不應為空"
        return True
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        pytest.fail(f"測試失敗: {str(e)}")

def test_map_website(default_url, default_search):
    """測試網站映射功能"""
    url = default_url
    search = default_search
    
    print(f"測試網站映射功能")
    print(f"URL: {url}")
    if search:
        print(f"搜尋詞: {search}")
    print("-" * 40)
    
    try:
        # 初始化 Firecrawl 客戶端
        client = FirecrawlClient()
        
        # 映射網站
        result = client.map_url(url, search)
        
        # 顯示結果
        print("\n映射結果：")
        
        if isinstance(result, dict) and 'urls' in result:
            urls = result['urls']
            print(f"找到 {len(urls)} 個 URL")
            for i, url in enumerate(urls[:10], 1):
                print(f"{i}. {url}")
            if len(urls) > 10:
                print(f"... 還有 {len(urls) - 10} 個 URL")
        else:
            print(json.dumps(result, indent=2)[:1000] + "..." if len(json.dumps(result, indent=2)) > 1000 else json.dumps(result, indent=2))
        
        print("\n✅ 測試成功!")
        assert result, "映射結果不應為空"
        return True
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        pytest.fail(f"測試失敗: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="測試 Firecrawl 基本功能")
    parser.add_argument("--mode", choices=["scrape", "map"], default="scrape", help="測試模式")
    parser.add_argument("--url", type=str, default="https://modelcontextprotocol.io", help="網頁 URL")
    parser.add_argument("--formats", type=str, help="爬取格式 (逗號分隔)")
    parser.add_argument("--search", type=str, help="映射搜尋詞")
    
    args = parser.parse_args()
    
    if args.mode == "scrape":
        formats = args.formats.split(',') if args.formats else ['markdown']
        test_basic_scrape(args.url, formats)
    elif args.mode == "map":
        test_map_website(args.url, args.search)
