"""Gemini AI 模型的函數調用（Function Calling）功能實現。

這個模塊擴展了 GeminiAI 類，添加了函數調用功能。
"""
import logging
import json
from typing import Dict, List, Any, Optional, Union

from ai.gemini import GeminiAI

logger = logging.getLogger(__name__)

async def function_call(self, messages: List[Dict[str, str]], 
                      functions: List[Dict[str, Any]], 
                      function_call: Optional[Union[str, Dict[str, str]]] = None, 
                      **kwargs) -> Dict[str, Any]:
    """使用 Gemini 實現函數調用(Function Calling)。
    
    Args:
        messages: 消息列表。
        functions: 函數定義列表。
        function_call: 可選的函數調用指定。
        **kwargs: 額外的參數。
        
    Returns:
        包含函數調用詳情的字典。
    """
    if not self.is_initialized and not self._initialize():
        raise RuntimeError("Gemini AI 未初始化")
        
    # 检查是否为不支持函数调用的实验性模型
    if "flash-thinking-exp" in self._model_name or "thinking-exp" in self._model_name:
        error_msg = f"Gemini实验性模型{self._model_name}不支持函数调用功能"
        logger.warning(error_msg)
        # 返回空结果而不是抛出错误，让程序能够继续执行
        return {"arguments": None, "name": None}
    
    try:
        # 確保客戶端初始化成功
        if not self.client:
            raise RuntimeError("Gemini 客戶端未初始化")
        
        # 如果可用，導入 genai 的類型
        try:
            from google.genai import types as genai_types
            from google.genai.types import FunctionDeclaration, Schema, Tool
        except ImportError:
            raise RuntimeError("未安裝 google-genai SDK 或無法導入所需類型")
        
        # 將函數定義轉換為 Gemini API 需要的格式
        tool_functions = []
        for func_def in functions:
            # 創建函數聲明
            function_declaration = FunctionDeclaration(
                name=func_def.get("name", ""),
                description=func_def.get("description", ""),
                parameters=Schema(
                    type="OBJECT",
                    properties=func_def.get("parameters", {}).get("properties", {}),
                    required=func_def.get("parameters", {}).get("required", [])
                )
            )
            tool_functions.append(function_declaration)
        
        # 創建工具
        tool = Tool(function_declarations=tool_functions)
        
        # 格式化消息
        formatted_contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                # 將系統消息設置為系統指令
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                # 用戶消息
                formatted_contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=msg["content"])]
                    )
                )
            elif msg["role"] == "assistant":
                # 助手消息
                formatted_contents.append(
                    genai_types.Content(
                        role="model",
                        parts=[genai_types.Part.from_text(text=msg["content"])]
                    )
                )
            elif msg["role"] == "function":
                # 函數響應消息
                function_name = msg.get("name", "")
                function_response = msg.get("content", "{}")
                
                formatted_contents.append(
                    genai_types.Content(
                        role="tool",
                        parts=[
                            genai_types.Part.from_function_response(
                                name=function_name,
                                response=json.loads(function_response) if isinstance(function_response, str) else function_response
                            )
                        ]
                    )
                )
        
        # 構建生成配置
        config = genai_types.GenerateContentConfig(
            tools=[tool],
            temperature=kwargs.get("temperature", self.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.max_tokens)
        )
        
        # 如果有系統指令，添加到配置中
        if system_instruction:
            config.system_instruction = system_instruction
        
        # 如果指定了特定的函數調用
        if function_call:
            try:
                # 現在 Gemini 沒有直接指定函數調用的方式，但可以在提示中指定
                if isinstance(function_call, str):
                    # 添加一個指示消息要求模型調用特定函數
                    formatted_contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=f"請調用函數 {function_call}")]
                        )
                    )
                elif isinstance(function_call, dict) and "name" in function_call:
                    # 添加一個指示消息要求模型調用特定函數
                    formatted_contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=f"請調用函數 {function_call['name']}")]
                        )
                    )
            except Exception as e:
                logger.warning(f"指定函數調用時出錯: {e}")
        
        # 調用 API
        response = self.client.models.generate_content(
            model=self._model_name,
            contents=formatted_contents,
            config=config
        )
        
        # 處理回應中的函數調用
        function_calls = []
        
        # 檢查是否有函數調用
        if hasattr(response, "function_calls") and response.function_calls:
            function_calls = response.function_calls
        
        # 如果沒有找到函數調用但有原始回應，嘗試解析
        if not function_calls and response.text:
            try:
                # 嘗試解析 JSON
                json_result = json.loads(response.text)
                return {"arguments": json_result}
            except json.JSONDecodeError:
                # 不是 JSON，返回原始文本
                return {"arguments": response.text}
        
        # 如果找到函數調用，格式化結果
        if function_calls:
            result = {
                "name": function_calls[0].name,
                "arguments": function_calls[0].function_call.args
            }
            return result
        
        # 如果沒有函數調用，返回空結果
        return {"arguments": None}
        
    except Exception as e:
        error_msg = f"使用 Gemini 進行函數調用時出錯: {str(e)}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg)

# 將函數添加到 GeminiAI 類
GeminiAI.function_call = function_call
