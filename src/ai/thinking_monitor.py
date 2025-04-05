"""AI 思考過程監控器。

這個模塊提供了監控和報告 AI 思考過程的功能，將思考步驟實時推送到前端。
"""
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class ThinkingMonitor:
    """AI 思考過程監控器。"""
    
    def __init__(self, user_id: str, thinking_interval: float = 1.0):
        """初始化思考監控器。
        
        Args:
            user_id: 用戶 ID。
            thinking_interval: 思考步驟發送間隔（秒）。
        """
        self.user_id = user_id
        self.thinking_interval = thinking_interval
        self.thinking_steps: List[str] = []
        self.is_monitoring = False
        self._monitor_task = None
        self._callback = None
    
    async def start(self, callback: Callable[[str, List[str]], None]) -> None:
        """開始監控 AI 思考過程。
        
        Args:
            callback: 當有新思考步驟時調用的回調函數，參數為用戶ID和思考步驟列表。
        """
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.thinking_steps = []
        self._callback = callback
        self._monitor_task = asyncio.create_task(self._send_thinking_updates())
        logger.info(f"Started thinking monitor for user {self.user_id}")
    
    async def stop(self) -> None:
        """停止監控 AI 思考過程。"""
        self.is_monitoring = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped thinking monitor for user {self.user_id}")
    
    def add_thinking_step(self, step: str) -> None:
        """添加思考步驟。
        
        Args:
            step: 思考步驟文本。
        """
        self.thinking_steps.append(step)
    
    async def _send_thinking_updates(self) -> None:
        """發送思考更新到前端。"""
        try:
            last_step_count = 0
            while self.is_monitoring:
                current_step_count = len(self.thinking_steps)
                
                # 只有在有新步驟時才發送更新
                if current_step_count > last_step_count and self._callback:
                    await self._callback(self.user_id, self.thinking_steps)
                    last_step_count = current_step_count
                
                # 等待下一次更新
                await asyncio.sleep(self.thinking_interval)
        except asyncio.CancelledError:
            logger.debug(f"Thinking monitor task for {self.user_id} cancelled")
        except Exception as e:
            logger.error(f"Error in thinking monitor for {self.user_id}: {str(e)}")
