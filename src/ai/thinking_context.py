"""AI 思考上下文管理器。

這個模塊提供了在執行 AI 思考過程中使用的上下文管理器。
"""
import logging
import asyncio
from typing import List, Callable, Any, Optional

from .thinking_monitor import ThinkingMonitor

logger = logging.getLogger(__name__)

class ThinkingContext:
    """AI 思考上下文管理器。
    
    用於在 with 語句中監控 AI 思考過程。
    例如：
        async with ThinkingContext(user_id="user123", callback=send_to_user) as ctx:
            ctx.add_thinking_step("分析問題...")
            # 進行處理
            ctx.add_thinking_step("生成回應...")
            # 繼續處理
    """
    
    def __init__(self, user_id: str, callback: Callable[[str, List[str]], Any], 
                thinking_interval: float = 1.0):
        """初始化思考上下文。
        
        Args:
            user_id: 用戶 ID。
            callback: 當有新思考步驟時調用的回調函數，參數為用戶ID和思考步驟列表。
            thinking_interval: 思考步驟發送間隔（秒）。
        """
        self.monitor = ThinkingMonitor(user_id, thinking_interval)
        self.callback = callback
    
    async def __aenter__(self) -> ThinkingMonitor:
        """進入上下文。
        
        Returns:
            思考監控器實例。
        """
        await self.monitor.start(self.callback)
        return self.monitor
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文。
        
        Args:
            exc_type: 異常類型。
            exc_val: 異常值。
            exc_tb: 異常追踪。
        """
        await self.monitor.stop()
        
        # 如果有異常，記錄錯誤
        if exc_type is not None:
            logger.error(f"Error in thinking context: {exc_val}")
            
            # 添加錯誤步驟
            self.monitor.add_thinking_step(f"遇到錯誤: {exc_val}")
            
            # 最後執行一次回調以報告錯誤
            try:
                await self.callback(self.monitor.user_id, self.monitor.thinking_steps)
            except Exception as e:
                logger.error(f"Error sending final thinking update: {e}")
