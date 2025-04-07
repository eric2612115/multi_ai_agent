"""AI 思考過程監控器。

這個模塊提供了監控和報告 AI 思考過程的功能，將思考步驟實時推送到前端。
支持思考脈衝/聲納檢測模式，實現更自然的思維流程展示和交互式思考引導。
"""
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Union, Set
from datetime import datetime
from enum import Enum

from src.services.event_bus import EventBus

logger = logging.getLogger(__name__)

class ThinkingPulseType(Enum):
    """思考脈衝類型。"""
    FOCUS = "focus"             # 專注於特定概念
    ASSOCIATION = "association"  # 聯想相關概念
    REFLECTION = "reflection"    # 對當前思考路徑的反思
    SHIFT = "shift"             # 思考方向轉變
    INSIGHT = "insight"         # 突發洞察
    QUESTION = "question"       # 提出問題
    ANALYSIS = "analysis"       # 分析解構

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
        
        # 思考脈衝/聲納檢測相關屬性
        self.pulse_enabled = False
        self.pulse_radius = 3  # 默認脈衝檢測半徑
        self.detection_threshold = 0.65  # 默認相關性檢測閾值
        self.detected_concepts: List[Dict[str, Any]] = []
        self.pulse_history: List[Dict[str, Any]] = []
        self.current_focal_concept: Optional[str] = None
        self.exploration_paths: List[Dict[str, Any]] = []
        self.selected_path_id: Optional[str] = None
        self.user_guidance: List[Dict[str, Any]] = []
        
        # 每個脈衝的思考步驟分組
        self.pulse_segments: List[Dict[str, Any]] = []
        
        # 事件總線客戶端
        self.event_bus = EventBus()
    
    async def start(self, callback: Callable[[str, List[str]], Any]) -> None:
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
        
        # 如果啟用了脈衝檢測，將步驟添加到當前段
        if self.pulse_enabled and self.pulse_segments:
            self.pulse_segments[-1]["steps"].append(step)
    
    def enable_pulse_detection(self, radius: int = 3, threshold: float = 0.65) -> None:
        """啟用思考脈衝/聲納檢測模式。
        
        Args:
            radius: 脈衝檢測半徑（考慮的相關節點範圍）。
            threshold: 相關性檢測閾值。
        """
        self.pulse_enabled = True
        self.pulse_radius = radius
        self.detection_threshold = threshold
        logger.info(f"Enabled pulse detection for user {self.user_id} with radius={radius}, threshold={threshold}")
    
    def disable_pulse_detection(self) -> None:
        """禁用思考脈衝/聲納檢測模式。"""
        self.pulse_enabled = False
        logger.info(f"Disabled pulse detection for user {self.user_id}")
    
    async def emit_pulse(self, focal_concept: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """發送思考脈衝，探測相關概念。
        
        Args:
            focal_concept: 焦點概念（發射源）。
            context: 可選的上下文信息。
            
        Returns:
            檢測到的相關概念列表。
        """
        if not self.pulse_enabled:
            logger.warning(f"Pulse detection not enabled for user {self.user_id}")
            return []
            
        # 記錄脈衝事件
        pulse_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "focal_concept": focal_concept,
            "pulse_type": ThinkingPulseType.FOCUS.value,
            "detected_concepts": [],
            "context": context or {}
        }
        
        # 創建新的思考段
        segment = {
            "segment_id": f"pulse_{len(self.pulse_segments) + 1}",
            "focal_concept": focal_concept,
            "timestamp": datetime.utcnow().isoformat(),
            "steps": [],
            "detected_concepts": []
        }
        self.pulse_segments.append(segment)
        
        # 設置當前焦點概念
        self.current_focal_concept = focal_concept
        
        # 添加思考步驟
        self.add_thinking_step(f"思考脈衝: 探索「{focal_concept}」相關概念...")
        
        # 執行脈衝檢測
        # 注意：在實際實現中，這裡可能需要調用RetriealService或其他服務來獲取相關概念
        try:
            # 導入相關服務，避免循環導入
            from src.services.retrieval_service import RetrievalService
            
            # 創建檢索服務實例
            retrieval_service = RetrievalService()
            
            # 檢測相關概念
            detected = await retrieval_service.retrieve_relevant_context(
                user_id=self.user_id,
                query_text=focal_concept,
                k=self.pulse_radius * 2,
                min_similarity=self.detection_threshold
            )
            
            # 更新檢測結果
            pulse_event["detected_concepts"] = [item["node_id"] for item in detected]
            segment["detected_concepts"] = detected
            
            # 添加到歷史記錄
            self.pulse_history.append(pulse_event)
            
            # 更新思考步驟
            detected_names = ", ".join([item.get("label", "未命名節點") for item in detected[:3]])
            self.add_thinking_step(f"思考聲納: 檢測到相關概念「{detected_names}」等 {len(detected)} 個關聯")
            
            # 將檢測到的概念合併到總列表
            self.detected_concepts.extend(detected)
            
            # 生成可能的探索路徑
            paths = await self._generate_exploration_paths(focal_concept, detected)
            self.exploration_paths = paths
            
            # 發布事件
            await self.event_bus.publish("thinking.pulse_emitted", {
                "user_id": self.user_id,
                "focal_concept": focal_concept,
                "detected_concepts": detected,
                "exploration_paths": paths
            })
            
            return detected
            
        except Exception as e:
            logger.error(f"Error during pulse detection: {str(e)}")
            self.add_thinking_step(f"思考聲納: 檢測過程出錯 ({str(e)})")
            return []
    
    async def select_exploration_path(self, path_id: str) -> bool:
        """選擇特定探索路徑。
        
        Args:
            path_id: 探索路徑ID。
            
        Returns:
            是否成功選擇路徑。
        """
        # 查找對應的路徑
        selected_path = None
        for path in self.exploration_paths:
            if path.get("path_id") == path_id:
                selected_path = path
                break
                
        if not selected_path:
            logger.warning(f"Path {path_id} not found for user {self.user_id}")
            return False
            
        # 記錄選擇
        self.selected_path_id = path_id
        
        # 添加思考步驟
        self.add_thinking_step(f"思考路徑: 選擇「{selected_path.get('name')}」- {selected_path.get('description', '')}")
        
        # 發布事件
        await self.event_bus.publish("thinking.path_selected", {
            "user_id": self.user_id,
            "path_id": path_id,
            "path_data": selected_path
        })
        
        return True
    
    def add_user_guidance(self, guidance: str) -> None:
        """添加用戶提供的思考指引。
        
        Args:
            guidance: 用戶提供的指引。
        """
        self.user_guidance.append({
            "timestamp": datetime.utcnow().isoformat(),
            "content": guidance
        })
        
        # 記錄到思考步驟
        self.add_thinking_step(f"外部指引: {guidance}")
    
    async def analyze_pulses(self) -> Dict[str, Any]:
        """分析思考脈衝歷史，生成洞察。
        
        Returns:
            脈衝分析結果。
        """
        if not self.pulse_enabled or not self.pulse_history:
            return {
                "pulse_count": 0,
                "insights": [],
                "summary": "未啟用脈衝檢測或無脈衝歷史"
            }
            
        # 分析脈衝歷史和段落
        insight_count = len(self.pulse_history)
        concept_count = len(self.detected_concepts)
        
        # 找出最重要的概念（出現次數最多）
        concept_frequency = {}
        for pulse in self.pulse_history:
            for concept_id in pulse["detected_concepts"]:
                concept_frequency[concept_id] = concept_frequency.get(concept_id, 0) + 1
                
        # 按頻率排序
        sorted_concepts = sorted(concept_frequency.items(), key=lambda x: x[1], reverse=True)
        top_concepts = [c_id for c_id, _ in sorted_concepts[:5]]
        
        # 生成分析結果
        result = {
            "pulse_count": len(self.pulse_history),
            "segment_count": len(self.pulse_segments),
            "concept_count": concept_count,
            "top_concepts": top_concepts,
            "path_selections": self.selected_path_id,
            "user_guidance_count": len(self.user_guidance),
            "segments": self.pulse_segments,
            "insights": [
                "思考過程展現了多層次的關聯性探索",
                f"共探測到 {concept_count} 個相關概念",
                f"思考過程中有 {len(self.user_guidance)} 次外部指引"
            ]
        }
        
        # 生成摘要
        if not self.pulse_segments:
            result["summary"] = "思考脈衝分析未找到有效的思考段落"
        else:
            # 找出主要焦點
            focal_concepts = [seg["focal_concept"] for seg in self.pulse_segments]
            result["summary"] = f"思考過程圍繞 {', '.join(focal_concepts[:3])} 等概念展開，探索了多條思路，建立起豐富的概念網絡"
            
        return result
    
    async def _generate_exploration_paths(self, 
                                     concept: str, 
                                     detected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基於檢測結果生成可能的探索路徑。
        
        Args:
            concept: 焦點概念。
            detected: 檢測到的相關概念。
            
        Returns:
            可能的探索路徑列表。
        """
        paths = []
        
        # 根據相似度分組
        similarity_groups = {
            "high": [d for d in detected if d.get("similarity_score", 0) > 0.8],
            "medium": [d for d in detected if 0.7 <= d.get("similarity_score", 0) <= 0.8],
            "adjacent": [d for d in detected if 0.6 <= d.get("similarity_score", 0) < 0.7]
        }
        
        # 創建深度優先路徑
        if similarity_groups["high"]:
            paths.append({
                "path_id": "depth_first",
                "name": "深度優先探索",
                "description": "深入探索最相關概念",
                "nodes": similarity_groups["high"][:3]
            })
            
        # 創建廣度優先路徑
        if similarity_groups["medium"]:
            paths.append({
                "path_id": "breadth_first",
                "name": "廣度優先探索",
                "description": "探索多個中度相關概念",
                "nodes": similarity_groups["medium"][:5]
            })
            
        # 創建關聯跳躍路徑
        if similarity_groups["adjacent"]:
            paths.append({
                "path_id": "associative_leap",
                "name": "關聯跳躍",
                "description": "探索稍微相關的概念，可能發現意外連接",
                "nodes": similarity_groups["adjacent"][:3]
            })
            
        return paths
    
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
                    
                    # 如果啟用了脈衝檢測，也發送脈衝更新
                    if self.pulse_enabled and self.pulse_segments:
                        # 發布事件
                        await self.event_bus.publish("thinking.progress", {
                            "user_id": self.user_id,
                            "step_count": current_step_count,
                            "current_focal_concept": self.current_focal_concept,
                            "current_segment": self.pulse_segments[-1] if self.pulse_segments else None,
                            "exploration_paths": self.exploration_paths
                        })
                
                # 等待下一次更新
                await asyncio.sleep(self.thinking_interval)
        except asyncio.CancelledError:
            logger.debug(f"Thinking monitor task for {self.user_id} cancelled")
        except Exception as e:
            logger.error(f"Error in thinking monitor for {self.user_id}: {str(e)}")
            logger.exception("Thinking monitor error details")
    
    def start_pulse_recording(self) -> None:
        """開始記錄思考脈衝段落。"""
        if not self.pulse_enabled:
            self.enable_pulse_detection()
            
        # 創建默認段落
        if not self.pulse_segments:
            self.pulse_segments.append({
                "segment_id": "initial",
                "focal_concept": "起始思考",
                "timestamp": datetime.utcnow().isoformat(),
                "steps": [],
                "detected_concepts": []
            })
            
        # 記錄開始
        self.add_thinking_step("啟動思考脈衝記錄...")
    
    def get_current_segment(self) -> Optional[Dict[str, Any]]:
        """獲取當前思考段落。
        
        Returns:
            當前思考段落。
        """
        if not self.pulse_segments:
            return None
        return self.pulse_segments[-1]
