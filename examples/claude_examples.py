#!/usr/bin/env python
"""
Anthropic Claude API 使用範例

這個腳本展示如何使用 ClaudeClient 進行各種操作:
1. 文字生成
2. Token 計算
3. 多輪對話 (模擬聊天)
"""
import os
import sys
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import ClaudeClient
from anthropic import Anthropic

def example_text_generation():
    """展示基本文字生成功能"""
    client = ClaudeClient()
    
    prompt = "用中文寫一段關於台灣文化的簡短介紹，約 100 字"
    
    print(f"\n== 基本文字生成 ==")
    print(f"提示詞: {prompt}")
    print("-" * 40)
    
    response = client.generate_text(prompt)
    print(response)
    
    # 使用更高級的模型
    print("\n== 使用進階模型 ==")
    client.set_model("claude-3-opus-20240229")
    
    prompt = "針對「永續發展」這個主題，用中文提供三個台灣可以實施的政策建議"
    print(f"提示詞: {prompt}")
    print("-" * 40)
    
    response = client.generate_text(prompt)
    print(response)

def example_token_count():
    """展示 Token 計算功能"""
    client = ClaudeClient()
    
    texts = [
        "這是一段簡短的文字",
        "這是一段稍微長一點的文字，包含了更多的詞彙和標點符號。",
        """這是一段較長的文字，包含多個句子和段落，以及數字1234和符號!@#$。
        
        這是第二段落，用來測試多段落的 token 計算。
        
        這是最後一段，讓我們看看會有多少 tokens。"""
    ]
    
    print(f"\n== Token 計算 ==")
    
    for i, text in enumerate(texts):
        token_count = client.count_tokens(text)
        print(f"\n範例 {i+1} ({len(text)} 字符):")
        print(f"文字: {text[:50]}..." if len(text) > 50 else f"文字: {text}")
        print(f"Token 數量: {token_count}")
    
def example_chat_conversation():
    """模擬多輪對話"""
    client = ClaudeClient().client  # 直接使用原始 Anthropic 客戶端
    
    print(f"\n== 模擬聊天對話 ==")
    print("-" * 40)
    
    # 創建完整的對話歷史
    messages = [
        {"role": "user", "content": "你好，請問你是誰？"},
    ]
    
    # 第一輪對話
    print("\n用戶: 你好，請問你是誰？")
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=messages,
    )
    assistant_response = response.content[0].text
    print(f"Claude: {assistant_response}")
    
    # 更新對話歷史
    messages.append({"role": "assistant", "content": assistant_response})
    messages.append({"role": "user", "content": "你能用中文介紹台灣嗎？"})
    
    # 第二輪對話
    print("\n用戶: 你能用中文介紹台灣嗎？")
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=messages,
    )
    assistant_response = response.content[0].text
    print(f"Claude: {assistant_response}")
    
    # 更新對話歷史
    messages.append({"role": "assistant", "content": assistant_response})
    messages.append({"role": "user", "content": "台灣有哪些著名的夜市？"})
    
    # 第三輪對話
    print("\n用戶: 台灣有哪些著名的夜市？")
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=messages,
    )
    assistant_response = response.content[0].text
    print(f"Claude: {assistant_response}")

def example_custom_api_call():
    """展示如何直接使用 Anthropic API 進行自定義呼叫"""
    # 直接使用 Anthropic SDK
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    
    print(f"\n== 自定義 API 呼叫 ==")
    print("-" * 40)
    
    # 設置系統提示詞
    system_prompt = "你是一位專業的旅遊顧問，專精於台灣旅遊建議。提供簡潔且實用的建議。"
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {"role": "user", "content": "我想去台灣旅遊5天，請給我一個行程建議。"}
        ],
        temperature=0.7,
    )
    
    print("系統提示詞:")
    print(system_prompt)
    print("\n用戶:")
    print("我想去台灣旅遊5天，請給我一個行程建議。")
    print("\n助手:")
    print(response.content[0].text)

if __name__ == "__main__":
    # 載入環境變數
    load_dotenv()
    
    # 執行範例
    example_text_generation()
    example_token_count()
    example_chat_conversation()
    example_custom_api_call()
