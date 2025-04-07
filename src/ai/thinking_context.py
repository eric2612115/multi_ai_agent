"""AI 思考上下文管理器。

這個模塊提供了在執行 AI 思考過程中使用的上下文管理器，
支持思考脈衝/聲納檢測模式，用於實現更自然的思維流程展示和可視化。
"""
import logging
import asyncio
from typing import List, Callable, Any, Optional, Dict
from functools import wraps

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
                thinking_interval: float = 1.0, enable_pulse: bool = False):
        """初始化思考上下文。
        
        Args:
            user_id: 用戶 ID。
            callback: 當有新思考步驟時調用的回調函數，參數為用戶ID和思考步驟列表。
            thinking_interval: 思考步驟發送間隔（秒）。
            enable_pulse: 是否啟用思考脈衝/聲納檢測模式。
        """
        self.monitor = ThinkingMonitor(user_id, thinking_interval)
        self.callback = callback
        self.enable_pulse = enable_pulse
    
    async def __aenter__(self) -> ThinkingMonitor:
        """進入上下文。
        
        Returns:
            思考監控器實例。
        """
        await self.monitor.start(self.callback)
        
        # 如果啟用脈衝檢測，初始化脈衝記錄
        if self.enable_pulse:
            self.monitor.start_pulse_recording()
            
        return self.monitor
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文。
        
        Args:
            exc_type: 異常類型。
            exc_val: 異常值。
            exc_tb: 異常追踪。
        """
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
        
        # 如果啟用了脈衝檢測，執行脈衝分析
        if self.enable_pulse:
            try:
                pulse_analysis = await self.monitor.analyze_pulses()
                self.monitor.add_thinking_step(f"思考脈衝分析: {pulse_analysis.get('summary', '無摘要')}")
            except Exception as e:
                logger.error(f"Error analyzing thinking pulses: {e}")
        
        # 停止監控
        await self.monitor.stop()


class PulseThinkingContext(ThinkingContext):
    """增強版思考上下文管理器，實現思考脈衝/聲納檢測模式。
    
    用於在 with 語句中監控 AI 思考過程並執行脈衝檢測。
    例如：
        async with PulseThinkingContext(user_id="user123", callback=send_to_user) as ctx:
            await ctx.emit_pulse("關鍵概念")
            ctx.add_thinking_step("分析問題...")
            # 進行處理
            await ctx.emit_pulse("另一個概念")
            ctx.add_thinking_step("生成回應...")
            # 繼續處理
    """
    
    def __init__(self, user_id: str, callback: Callable[[str, List[str]], Any], 
                thinking_interval: float = 0.5, pulse_radius: int = 3, 
                detection_threshold: float = 0.65):
        """初始化脈衝思考上下文。
        
        Args:
            user_id: 用戶 ID。
            callback: 當有新思考步驟時調用的回調函數，參數為用戶ID和思考步驟列表。
            thinking_interval: 思考步驟發送間隔（秒）。
            pulse_radius: 脈衝檢測半徑（考慮的相關節點範圍）。
            detection_threshold: 相關性檢測閾值。
        """
        super().__init__(user_id, callback, thinking_interval, enable_pulse=True)
        self.pulse_radius = pulse_radius
        self.detection_threshold = detection_threshold
    
    async def __aenter__(self) -> ThinkingMonitor:
        """進入上下文。
        
        Returns:
            思考監控器實例。
        """
        monitor = await super().__aenter__()
        monitor.enable_pulse_detection(self.pulse_radius, self.detection_threshold)
        return monitor
    
    async def emit_pulse(self, focal_concept: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """發送思考脈衝，探測相關概念。
        
        這是一個便捷方法，直接調用監控器的脈衝方法。
        
        Args:
            focal_concept: 焦點概念（發射源）。
            context: 可選的上下文信息。
            
        Returns:
            檢測到的相關概念列表。
        """
        return await self.monitor.emit_pulse(focal_concept, context)


def pulse_thinking(radius: int = 3, threshold: float = 0.65):
    """裝飾器：為方法添加思考脈衝/聲納檢測能力。
    
    用於裝飾 AI 代理的思考方法，使其在執行過程中自動進行脈衝檢測。
    
    Args:
        radius: 脈衝檢測半徑（考慮的相關節點範圍）。
        threshold: 相關性檢測閾值。
        
    Returns:
        裝飾後的方法。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # 提取方法的關鍵詞以用作焦點概念
            focal_concept = kwargs.get("query_text", kwargs.get("prompt", ""))
            if not focal_concept and args:
                focal_concept = args[0]
                
            # 在原始思考方法執行前啟動脈衝記錄
            if hasattr(self, 'thinking_context'):
                # 如果思考上下文已經存在，使用現有的
                if isinstance(self.thinking_context.monitor, ThinkingMonitor):
                    self.thinking_context.monitor.enable_pulse_detection(radius, threshold)
                    
                    # 發射初始脈衝
                    if focal_concept:
                        await self.thinking_context.monitor.emit_pulse(focal_concept)
            
            # 執行原始思考方法
            result = await func(self, *args, **kwargs)
            
            # 在原始思考方法執行後進行脈衝分析
            if hasattr(self, 'thinking_context'):
                try:
                    pulse_analysis = await self.thinking_context.monitor.analyze_pulses()
                    # 將結果附加到原始結果
                    if isinstance(result, dict):
                        result['pulse_analysis'] = pulse_analysis
                except Exception as e:
                    logger.error(f"Error processing thinking pulse analysis: {e}")
                    
            return result
        return wrapper
    return decorator
