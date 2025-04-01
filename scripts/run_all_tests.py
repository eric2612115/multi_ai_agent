#!/usr/bin/env python
"""
整合測試腳本 - 運行所有 AI 客戶端的測試

這個腳本會執行所有 AI 客戶端的測試功能，包括:
1. Gemini 文字生成和搜尋
2. Claude 文字生成和 Token 計算
3. Firecrawl 基本抓取和網站映射
4. 智能萃取和進階萃取
"""
import os
import sys
import argparse
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 引入測試腳本
from isolate_run_gemini import test_gemini_text_generation, test_gemini_search
from isolate_run_claude import test_claude_text_generation, test_claude_token_count
from isolate_run_basic_scrape import test_basic_scrape, test_map_website
from isolate_run_smart_extraction import test_smart_extraction
from isolate_run_advanced_extraction import test_advanced_extraction

def run_gemini_tests():
    """執行 Gemini 測試"""
    print("\n" + "=" * 60)
    print("執行 Gemini 測試")
    print("=" * 60)
    
    # 測試文字生成
    prompt = "用中文寫一首關於台灣的短詩"
    test_gemini_text_generation(prompt)
    
    # 測試搜尋
    query = "台灣最高的山是什麼？"
    test_gemini_search(query)

def run_claude_tests():
    """執行 Claude 測試"""
    print("\n" + "=" * 60)
    print("執行 Claude 測試")
    print("=" * 60)
    
    # 測試文字生成
    prompt = "用中文寫一段關於台灣的簡短介紹，約 100 字"
    test_claude_text_generation(prompt)
    
    # 測試 Token 計算
    text = "這是一段需要計算 token 數量的測試文字。它應該包含足夠的文字來測試 Claude 的 token 計算功能。"
    test_claude_token_count(text)

def run_firecrawl_tests():
    """執行 Firecrawl 測試"""
    print("\n" + "=" * 60)
    print("執行 Firecrawl 測試")
    print("=" * 60)
    
    # 測試基本抓取
    url = "https://modelcontextprotocol.io"
    formats = ["markdown"]
    test_basic_scrape(url, formats)
    
    # 測試網站映射
    test_map_website(url, search="python")

def run_extraction_tests():
    """執行智能萃取測試"""
    print("\n" + "=" * 60)
    print("執行智能萃取測試")
    print("=" * 60)
    
    # 測試智能萃取
    url = "https://www.taipei-101.com.tw"
    objective = "找出台北 101 的高度以及建造時間"
    test_smart_extraction(url, objective)
    
    # 測試進階萃取
    urls = ["https://modelcontextprotocol.io", "https://modelcontextprotocol.io/docs"]
    objective = "提取關於 Model Context Protocol 的主要功能和用例"
    entity = "Model Context Protocol"
    test_advanced_extraction(urls, objective, entity)

if __name__ == "__main__":
    # 載入環境變數
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="執行所有 AI 客戶端測試")
    parser.add_argument("--all", action="store_true", help="執行所有測試")
    parser.add_argument("--gemini", action="store_true", help="執行 Gemini 測試")
    parser.add_argument("--claude", action="store_true", help="執行 Claude 測試")
    parser.add_argument("--firecrawl", action="store_true", help="執行 Firecrawl 基本測試")
    parser.add_argument("--extraction", action="store_true", help="執行智能萃取測試")
    
    args = parser.parse_args()
    
    # 如果沒有指定任何選項，預設執行所有測試
    if not (args.all or args.gemini or args.claude or args.firecrawl or args.extraction):
        args.all = True
    
    if args.all or args.gemini:
        run_gemini_tests()
    
    if args.all or args.claude:
        run_claude_tests()
    
    if args.all or args.firecrawl:
        run_firecrawl_tests()
    
    if args.all or args.extraction:
        run_extraction_tests()
