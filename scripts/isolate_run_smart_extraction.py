#!/usr/bin/env python
"""
獨立測試腳本 - 智能網頁萃取功能
這個腳本測試智能網頁萃取功能，使用 Firecrawl + Gemini 分析網頁內容。
"""
import os
import sys
import json
import argparse
import pytest
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient

@pytest.fixture
def default_url():
    return "https://modelcontextprotocol.io"

@pytest.fixture
def default_objective():
    return "什麼是 Model Context Protocol 及其主要特性"

def test_smart_extraction(default_url, default_objective, use_advanced_model=False):
    """測試智能網頁萃取功能"""
    url = default_url
    objective = default_objective
    
    print(f"測試智能網頁萃取功能")
    print(f"URL: {url}")
    print(f"目標: {objective}")
    print(f"使用進階模型: {'是' if use_advanced_model else '否'}")
    print("-" * 40)
    
    try:
        # 初始化客戶端
        firecrawl_client = FirecrawlClient()
        gemini_client = GeminiClient()
        
        # 設置萃取服務
        firecrawl_client.set_extraction_service(gemini_client=gemini_client)
        
        # 執行智能萃取
        result = firecrawl_client.smart_extract(url, objective, use_advanced_model)
        
        # 顯示結果
        if result:
            print("\n萃取結果：")
            print(f"來源 URL: {result.get('source_url', '未知')}")
            print(f"目標: {result.get('objective', objective)}")
            
            data = result.get('data')
            if data:
                print("\n萃取數據:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print("\n沒有找到數據。")
                
            print("\n✅ 測試成功!")
            assert result, "萃取結果不應為空"
            return True
        else:
            print(f"\n⚠️ 未能找到相關信息。")
            return False
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"測試失敗: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="測試智能網頁萃取功能")
    parser.add_argument("--url", type=str, default="https://modelcontextprotocol.io", help="網站 URL")
    parser.add_argument("--objective", type=str, default="什麼是 Model Context Protocol", help="萃取目標")
    parser.add_argument("--advanced", action="store_true", help="使用進階模型")
    
    args = parser.parse_args()
    
    test_smart_extraction(args.url, args.objective, args.advanced)
