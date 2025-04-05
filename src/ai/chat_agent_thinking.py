"""聊天代理思考功能擴展。

這個模塊擴展了 ChatAgent 類，添加實時思考過程推送功能。
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Union, Callable

from ai.chat_agent import ChatAgent
from ai.thinking_context import ThinkingContext
from api.websocket.chat.message_formatter import MessageFormatter
from api.websocket.chat.ws_connection_manager import chat_manager

logger = logging.getLogger(__name__)

async def process_thinking_message(self, message: str, **kwargs) -> str:
    """處理消息並顯示思考步驟。
    
    Args:
        message: 用戶消息。
        **kwargs: 其他參數。
        
    Returns:
        生成的回應。
    """
    # 定義發送思考步驟的回調函數
    async def send_thinking_steps(user_id: str, steps: List[str]) -> None:
        """發送思考步驟到前端。
        
        Args:
            user_id: 用戶 ID。
            steps: 思考步驟列表。
        """
        # 構建思考步驟消息
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        thinking_message = MessageFormatter.format_thinking(
            f"思考過程：\n{steps_text}",
            metadata={"thinking_steps": steps, "step_count": len(steps)}
        )
        
        # 發送給用戶
        await chat_manager.send_message(user_id, thinking_message)
    
    # 使用思考上下文
    async with ThinkingContext(self.user_id, send_thinking_steps) as thinking:
        try:
            start_time = time.time()
            
            # 記錄開始思考的步驟
            thinking.add_thinking_step("開始分析您的問題...")
            await asyncio.sleep(0.5)  # 小暫停使步驟顯示更自然
            
            # 第1步：分析問題
            thinking.add_thinking_step("識別問題的關鍵點...")
            
            # 準備提示詞，要求模型分步思考
            system_prompt = """
            你是一個會分步驟思考問題的AI助手。請先理解問題，然後一步一步地進行分析，最後給出答案。
            在回答過程中，請使用以下格式標記你的思考過程：
            
            思考步驟：
            1. [你的第一個思考步驟]
            2. [你的第二個思考步驟]
            ...
            
            結論：[你的最終答案]
            """
            
            # 向模型詢問初步分析
            initial_analysis = await self.text_model.generate_text(
                f"請分析以下問題並列出關鍵點：\n{message}",
                system_prompt=system_prompt
            )
            
            # 第2步：提取關鍵信息
            thinking.add_thinking_step("提取問題中的關鍵信息...")
            
            # 生成詳細分析
            thinking.add_thinking_step("為問題生成詳細分析方案...")
            await asyncio.sleep(0.5)
            
            # 第3步：獲取相關知識
            thinking.add_thinking_step("檢索相關背景知識...")
            
            # 第4步：制定回應策略
            thinking.add_thinking_step("確定最佳回應方式...")
            
            # 第5步：生成完整回應
            thinking.add_thinking_step("生成完整答案...")
            
            # 使用增強型提示詞格式請求最終答案
            enhanced_prompt = f"""
            請對以下問題給予深思熟慮的回答：
            
            問題：{message}
            
            在回答中，確保：
            1. 清晰地解釋所有必要的概念
            2. 提供具體的例子或證據
            3. 考慮不同的觀點
            4. 得出全面、平衡的結論
            """
            
            # 生成最終回應
            response = await self.text_model.generate_text(
                enhanced_prompt,
                system_prompt=system_prompt,
                max_tokens=kwargs.get("max_tokens", 1024)
            )
            
            # 步驟6：優化回應格式
            thinking.add_thinking_step("優化回應格式和結構...")
            
            # 步驟7：完成
            processing_time = time.time() - start_time
            thinking.add_thinking_step(f"回應已完成 (用時: {processing_time:.2f}秒)")
            
            return response
            
        except Exception as e:
            logger.exception(f"思考過程中出錯: {e}")
            return f"在處理您的請求時發生錯誤：{str(e)}。請稍後再試。"

# 將函數添加到 ChatAgent 類
ChatAgent.process_thinking_message = process_thinking_message
