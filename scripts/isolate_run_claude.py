#!/usr/bin/env python
"""
獨立測試腳本 - Claude 文字生成
這個腳本直接測試 Claude 客戶端的功能，不需要啟動 MCP 伺服器。
"""
import os
import sys
import argparse
import pytest
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import ClaudeClient

@pytest.fixture
def default_prompt():
    return "寫一首關於台灣的短詩"

@pytest.fixture
def default_text():
    return "這是一段需要計算 token 數量的測試文字。它應該包含足夠的文字來測試 Claude 的 token 計算功能。"

def test_claude_text_generation(default_prompt, model=None, max_tokens=1024):
    """測試 Claude 文字生成功能"""
    prompt = default_prompt
    print(f"測試 Claude 文字生成功能")
    print(f"提示詞: {prompt}")
    print(f"模型: {model or '預設'}")
    print(f"最大 Token 數: {max_tokens}")
    print("-" * 40)
    
    try:
        # 初始化 Claude 客戶端
        client = ClaudeClient()
        
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

def test_claude_token_count(default_text):
    """測試 Claude 計算 Token 功能"""
    text = default_text
    print(f"測試 Claude Token 計算功能")
    print(f"文字: {text if len(text) < 50 else text[:50] + '...'}")
    print("-" * 40)
    
    try:
        # 初始化 Claude 客戶端
        client = ClaudeClient()
        
        # 計算 Token
        token_count = client.count_tokens(text)
        
        print(f"\nToken 數量: {token_count}")
        
        print("\n✅ 測試成功!")
        assert token_count > 0, "Token 數量應該大於 0"
        return True
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        pytest.fail(f"測試失敗: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="測試 Claude 功能")
    parser.add_argument("--mode", choices=["generate", "count"], default="generate", help="測試模式")
    parser.add_argument("--prompt", type=str, default="寫一首短詩", help="提示詞或文字")
    parser.add_argument("--model", type=str, help="模型名稱 (例如 claude-3-5-sonnet-20240620)")
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大生成 token 數")
    
    args = parser.parse_args()
    
    if args.mode == "generate":
        test_claude_text_generation(args.prompt, args.model, args.max_tokens)
    elif args.mode == "count":
        test_claude_token_count(args.prompt)
