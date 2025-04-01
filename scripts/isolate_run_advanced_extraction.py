#!/usr/bin/env python
"""
獨立測試腳本 - 進階 API 萃取功能
這個腳本測試使用 Firecrawl 的 Extract API 進行高級萃取。
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
def default_urls():
    return ["https://modelcontextprotocol.io", "https://modelcontextprotocol.io/docs"]

@pytest.fixture
def default_objective():
    return "提取關於 Model Context Protocol 的主要功能和用例"

@pytest.fixture
def default_entity():
    return "Model Context Protocol"

def test_advanced_extraction(default_urls, default_objective, default_entity):
    """測試進階 API 萃取功能"""
    urls = default_urls
    objective = default_objective
    entity = default_entity
    
    print(f"測試進階 API 萃取功能")
    print(f"URLs: {', '.join(urls)}")
    print(f"目標: {objective}")
    if entity:
        print(f"實體: {entity}")
    print("-" * 40)
    
    try:
        # 初始化 Firecrawl 客戶端
        client = FirecrawlClient()
        
        # 設置萃取服務
        client.set_extraction_service()
        
        # 執行進階萃取
        result = client.advanced_extract(urls, objective, entity)
        
        # 顯示結果
        if result:
            print("\n萃取結果：")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("\n✅ 測試成功!")
            assert result, "萃取結果不應為空"
            return True
        else:
            print(f"\n⚠️ 進階萃取未返回結果。")
            return False
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"測試失敗: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="測試進階 API 萃取功能")
    parser.add_argument("--urls", type=str, required=True, help="要萃取的 URL (逗號分隔)")
    parser.add_argument("--objective", type=str, required=True, help="萃取目標")
    parser.add_argument("--entity", type=str, help="相關實體 (例如公司名稱)")
    
    args = parser.parse_args()
    
    urls = args.urls.split(',')
    test_advanced_extraction(urls, args.objective, args.entity)
