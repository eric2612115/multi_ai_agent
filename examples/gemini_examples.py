#!/usr/bin/env python
"""
Google Gemini API 使用範例

這個腳本展示如何使用 GeminiClient 進行各種操作:
1. 文字生成
2. 網頁搜尋
3. 多模態內容處理 (圖片分析)
4. 功能呼叫 (Function Calling)
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import GeminiClient

def example_text_generation():
    """展示基本文字生成功能"""
    client = GeminiClient()
    
    prompt = "用中文寫一段關於台灣文化的簡短介紹，約 100 字"
    
    print(f"\n== 基本文字生成 ==")
    print(f"提示詞: {prompt}")
    print("-" * 40)
    
    response = client.generate_text(prompt)
    print(response)
    

def example_web_search():
    """展示網頁搜尋功能"""
    client = GeminiClient()
    
    query = "台北 101 的高度是多少？建於什麼時候？"
    
    print(f"\n== 網頁搜尋 ==")
    print(f"搜尋詞: {query}")
    print("-" * 40)
    
    response = client.search_web(query)
    print(response)


def example_function_calling():
    """展示功能呼叫 (Function Calling)"""
    from google.genai import types
    
    client = GeminiClient()
    
    # 定義功能宣告
    function = types.FunctionDeclaration(
        name="get_weather",
        description="獲取指定城市的天氣資訊",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(
                    type="STRING",
                    description="城市名稱，例如：台北",
                ),
                "unit": types.Schema(
                    type="STRING",
                    description="溫度單位，攝氏(C)或華氏(F)",
                    enum=["C", "F"],
                ),
            },
            required=["location"],
        ),
    )
    
    tool = types.Tool(function_declarations=[function])
    
    print(f"\n== 功能呼叫 (Function Calling) ==")
    prompt = "今天台北的天氣怎麼樣？"
    print(f"提示詞: {prompt}")
    print("-" * 40)
    
    # 生成回應並獲取功能呼叫
    response = client.client.models.generate_content(
        model=client.model,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[tool]),
    )
    
    # 檢查是否有功能呼叫
    if hasattr(response, 'function_calls') and response.function_calls:
        func_call = response.function_calls[0]
        print(f"模型呼叫函數: {func_call.name}")
        print(f"參數: {json.dumps(func_call.function_call.args, indent=2, ensure_ascii=False)}")
        
        # 模擬函數執行
        print("\n執行函數並獲取結果...")
        
        # 在實際應用中，這裡會呼叫真正的天氣 API
        # 這裡使用模擬資料
        weather_result = {
            "temperature": 25,
            "unit": "C",
            "condition": "晴時多雲",
            "humidity": 70,
            "location": "台北"
        }
        
        # 將功能執行結果回傳給模型
        function_response_part = types.Part.from_function_response(
            name=func_call.name,
            response={"result": weather_result},
        )
        
        function_response = types.Content(
            role='tool', parts=[function_response_part]
        )
        
        # 將用戶問題、模型功能呼叫和功能回應一起傳給模型
        final_response = client.client.models.generate_content(
            model=client.model,
            contents=[
                types.Content(role='user', parts=[types.Part.from_text(prompt)]),
                response.candidates[0].content,
                function_response,
            ],
            config=types.GenerateContentConfig(tools=[tool]),
        )
        
        print("\n最終回應:")
        print(final_response.text)
    else:
        print("模型沒有呼叫函數，直接回應:")
        print(response.text)


def example_image_analysis():
    """展示圖片分析功能 (需要提供有效的圖片路徑)"""
    from google.genai import types
    
    client = GeminiClient()
    client.set_model("gemini-2.0-pro-vision")  # 設置支援圖片的模型
    
    # 請替換為實際的圖片路徑
    image_path = Path("examples/taipei_101.jpg")
    
    if not image_path.exists():
        print(f"\n== 圖片分析 ==")
        print(f"圖片不存在: {image_path}")
        print("請替換為有效的圖片路徑以測試此功能")
        return
    
    print(f"\n== 圖片分析 ==")
    print(f"圖片路徑: {image_path}")
    print("-" * 40)
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    # 創建圖片部分
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    
    # 將圖片和提示詞一起傳給模型
    prompt = "請描述這張圖片中的內容，並簡單介紹其背景知識"
    
    response = client.client.models.generate_content(
        model=client.model,
        contents=[prompt, image_part],
    )
    
    print(response.text)


if __name__ == "__main__":
    # 載入環境變數
    load_dotenv()
    
    # 執行範例
    example_text_generation()
    example_web_search()
    example_function_calling()
    example_image_analysis()
