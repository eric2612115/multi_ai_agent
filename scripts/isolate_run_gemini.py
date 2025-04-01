#!/usr/bin/env python
"""
獨立測試腳本 - Gemini 文字生成
這個腳本直接測試 Gemini 客戶端的功能，不需要啟動 MCP 伺服器。
"""
import os
import sys
import argparse
import pytest
from dotenv import load_dotenv, find_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import GeminiClient

@pytest.fixture
def default_prompt():
    return "寫一首關於台灣的短詩"

@pytest.fixture
def default_query():
    return "台灣最高的山是什麼?"

def test_gemini_text_generation(default_prompt, model=None, max_tokens=1024):
    """測試 Gemini 文字生成功能"""
    prompt = default_prompt
    print(f"測試 Gemini 文字生成功能")
    print(f"提示詞: {prompt}")
    print(f"模型: {model or '預設'}")
    print(f"最大 Token 數: {max_tokens}")
    print("-" * 40)
    
    try:
        # 初始化 Gemini 客戶端
        client = GeminiClient()
        
        if model:
            client.set_model(model)
            
        # 生成文字
        response = client.generate_text(prompt, max_tokens)
        
        print("\n生成結果：")
        print(response)
        
        print("\n✅ 測試成功!")
        assert response, "生成的回應不應該為空"
        return True
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        pytest.fail(f"測試失敗: {str(e)}")
        
def test_gemini_search(default_query):
    """測試 Gemini 搜尋功能"""
    query = default_query
    print(f"測試 Gemini 網頁搜尋功能")
    print(f"搜尋詞: {query}")
    print("-" * 40)
    
    try:
        # 初始化 Gemini 客戶端
        client = GeminiClient()
        
        # 執行搜尋
        response = client.search_web(query)
        
        print("\n搜尋結果：")
        print(response)
        
        print("\n✅ 測試成功!")
        assert response, "搜尋的回應不應該為空"
        return True
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        pytest.fail(f"測試失敗: {str(e)}")

if __name__ == "__main__":
    load_dotenv(find_dotenv())
    
    parser = argparse.ArgumentParser(description="測試 Gemini 功能")
    parser.add_argument("--mode", choices=["generate", "search"], default="generate", help="測試模式")
    parser.add_argument("--prompt", type=str, default="寫一首短詩", help="提示詞")
    parser.add_argument("--model", type=str, help="模型名稱 (例如 gemini-2.0-flash)")
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大生成 token 數")
    
    args = parser.parse_args()
    
    if args.mode == "generate":
        test_gemini_text_generation(args.prompt, args.model, args.max_tokens)
    elif args.mode == "search":
        test_gemini_search(args.prompt)
