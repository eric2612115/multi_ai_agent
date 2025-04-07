"""WebSocket處理器，用於實時思考過程互動。

這個模塊提供用於監控和引導AI思考過程的WebSocket端點。
"""
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from src.services.event_bus import EventBus
from src.common.config import get_settings
from src.api.websocket.chat.ws_connection_manager import chat_manager
from src.services.retrieval_service import RetrievalService

# 設置日誌
logger = logging.getLogger(__name__)

# 獲取設置
settings = get_settings()

# 創建路由
router = APIRouter(prefix="/ws/thinking", tags=["thinking-ws"])

# 思考控制器類
class ThinkingController:
    """思考過程控制器，允許用戶干預和引導思考。"""
    
    def __init__(self, user_id: str):
        """初始化思考控制器。
        
        Args:
            user_id: 用戶ID。
        """
        self.user_id = user_id
        self.guidances = []
        self.focus_history = []
        self.exploration_paths = []
        
        # 事件和狀態
        self.event_bus = EventBus()
        self.retrieval_service = None
        self.is_initialized = False
    
    async def initialize(self) -> bool:
        """初始化控制器和相關服務。
        
        Returns:
            初始化是否成功。
        """
        try:
            # 初始化檢索服務
            self.retrieval_service = RetrievalService()
            await self.retrieval_service.initialize()
            
            # 註冊事件監聽器
            self.event_bus.subscribe("thinking.pulse_emitted", self._handle_pulse_emitted)
            self.event_bus.subscribe("thinking.path_selected", self._handle_path_selected)
            
            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize thinking controller: {e}")
            return False
    
    async def close(self) -> None:
        """關閉控制器和釋放資源。"""
        try:
            # 取消事件訂閱
            self.event_bus.unsubscribe("thinking.pulse_emitted", self._handle_pulse_emitted)
            self.event_bus.unsubscribe("thinking.path_selected", self._handle_path_selected)
        except Exception as e:
            logger.error(f"Error closing thinking controller: {e}")
    
    def add_guidance(self, guidance: str) -> None:
        """添加用戶提供的思考指引。
        
        Args:
            guidance: 用戶提供的指引。
        """
        self.guidances.append({
            "timestamp": datetime.utcnow().isoformat(),
            "content": guidance
        })
        
        # 發布事件
        asyncio.create_task(self.event_bus.publish("thinking.guidance", {
            "user_id": self.user_id,
            "guidance": guidance,
            "timestamp": datetime.utcnow().isoformat()
        }))
    
    async def focus_on(self, concept: str) -> List[Dict[str, Any]]:
        """專注於特定概念，發射思考脈衝。
        
        Args:
            concept: 要專注的概念。
            
        Returns:
            檢測到的相關概念列表。
        """
        # 確保已初始化
        if not self.is_initialized:
            await self.initialize()
            
        # 記錄焦點歷史
        self.focus_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "concept": concept
        })
        
        # 使用檢索服務獲取相關概念
        try:
            detected = await self.retrieval_service.retrieve_relevant_context(
                user_id=self.user_id,
                query_text=concept,
                k=6,  # 獲取前6個相關結果
                min_similarity=0.65
            )
            
            # 生成可能的探索路徑
            paths = await self._generate_exploration_paths(concept, detected)
            self.exploration_paths = paths
            
            # 發布事件
            await self.event_bus.publish("thinking.focus", {
                "user_id": self.user_id,
                "focal_concept": concept,
                "detected_concepts": detected,
                "exploration_paths": paths
            })
            
            return detected
        except Exception as e:
            logger.error(f"Error focusing on concept: {e}")
            return []
    
    async def select_path(self, path_id: str) -> bool:
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
            return False
            
        # 發布路徑選擇事件
        await self.event_bus.publish("thinking.path_selected", {
            "user_id": self.user_id,
            "path_id": path_id,
            "path_data": selected_path
        })
        
        return True
    
    async def _handle_pulse_emitted(self, event_data: Dict[str, Any]) -> None:
        """處理思考脈衝發射事件。
        
        Args:
            event_data: 事件數據。
        """
        # 檢查是不是給當前用戶的事件
        if event_data.get("user_id") != self.user_id:
            return
            
        # 更新探索路徑
        if "exploration_paths" in event_data:
            self.exploration_paths = event_data["exploration_paths"]
    
    async def _handle_path_selected(self, event_data: Dict[str, Any]) -> None:
        """處理路徑選擇事件。
        
        Args:
            event_data: 事件數據。
        """
        # 檢查是不是給當前用戶的事件
        if event_data.get("user_id") != self.user_id:
            return
    
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
                "path_id": f"depth_first_{uuid.uuid4().hex[:8]}",
                "name": "深度優先探索",
                "description": "深入探索最相關概念",
                "nodes": similarity_groups["high"][:3]
            })
            
        # 創建廣度優先路徑
        if similarity_groups["medium"]:
            paths.append({
                "path_id": f"breadth_first_{uuid.uuid4().hex[:8]}",
                "name": "廣度優先探索",
                "description": "探索多個中度相關概念",
                "nodes": similarity_groups["medium"][:5]
            })
            
        # 創建關聯跳躍路徑
        if similarity_groups["adjacent"]:
            paths.append({
                "path_id": f"associative_leap_{uuid.uuid4().hex[:8]}",
                "name": "關聯跳躍",
                "description": "探索稍微相關的概念，可能發現意外連接",
                "nodes": similarity_groups["adjacent"][:3]
            })
            
        return paths


# 存儲活動的思考控制器
thinking_controllers: Dict[str, ThinkingController] = {}

# 清理不活躍控制器的任務
cleanup_task = None

async def cleanup_inactive_controllers():
    """清理不活躍的思考控制器。"""
    try:
        while True:
            await asyncio.sleep(300)  # 每5分鐘檢查一次
            
            # 暫時不實現清理邏輯，因為我們沒有跟踪最後活躍時間
            # 實際實現中，應該清除長時間不活躍的控制器
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in thinking controller cleanup: {e}")


# WebSocket端點
@router.websocket("/{user_id}")
async def thinking_websocket(websocket: WebSocket, user_id: str):
    """思考過程WebSocket端點。
    
    允許用戶實時接收和引導思考過程。
    
    Args:
        websocket: WebSocket連接。
        user_id: 用戶ID。
    """
    # 啟動清理任務
    global cleanup_task
    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(cleanup_inactive_controllers())
    
    # 獲取或創建控制器
    controller = thinking_controllers.get(user_id)
    if not controller:
        controller = ThinkingController(user_id)
        thinking_controllers[user_id] = controller
        await controller.initialize()
    
    # 接受WebSocket連接
    await websocket.accept()
    
    # 構建事件處理器
    async def event_handler(event_type: str, event_data: Dict[str, Any]):
        """處理事件並發送到WebSocket。"""
        # 檢查事件是否與此用戶相關
        if event_data.get("user_id") != user_id:
            return
            
        # 發送到WebSocket
        try:
            await websocket.send_text(json.dumps({
                "type": event_type,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error sending event to WebSocket: {e}")
    
    # 註冊事件處理器
    event_bus = EventBus()
    
    # 訂閱事件
    event_bus.subscribe("thinking.pulse_emitted", lambda data: event_handler("pulse_emitted", data))
    event_bus.subscribe("thinking.progress", lambda data: event_handler("thinking_progress", data))
    event_bus.subscribe("thinking.path_selected", lambda data: event_handler("path_selected", data))
    event_bus.subscribe("thinking.focus", lambda data: event_handler("focus", data))
    
    try:
        # 發送連接建立消息
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "思考控制器WebSocket連接已建立"
        }))
        
        # 監聽用戶命令
        while True:
            # 接收用戶命令
            data = await websocket.receive_text()
            command = json.loads(data)
            
            if command["type"] == "guidance":
                # 用戶提供的思考指引
                guidance = command.get("content", "")
                
                # 將指引添加到思考控制器
                controller.add_guidance(guidance)
                
                # 確認收到
                await websocket.send_text(json.dumps({
                    "type": "confirmation",
                    "content": f"已接收思考指引: {guidance}",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
            elif command["type"] == "focus":
                # 用戶要求關注特定概念
                focus_concept = command.get("concept", "")
                
                if not focus_concept:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "content": "缺少概念名稱",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    continue
                
                # 發射思考脈衝探測相關概念
                detected = await controller.focus_on(focus_concept)
                
                # 返回探測結果
                await websocket.send_text(json.dumps({
                    "type": "detection_result",
                    "focal_concept": focus_concept,
                    "detected_count": len(detected),
                    "detected_concepts": [
                        {"id": d.get("node_id"), "label": d.get("label", ""), 
                         "similarity": d.get("similarity_score", 0)}
                        for d in detected[:5]  # 只返回前5個
                    ],
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
            elif command["type"] == "select_path":
                # 用戶選擇特定探索路徑
                path_id = command.get("path_id")
                
                if not path_id:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "content": "缺少路徑ID",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    continue
                
                # 將系統引導到該路徑
                success = await controller.select_path(path_id)
                
                # 確認路徑選擇
                await websocket.send_text(json.dumps({
                    "type": "path_selected",
                    "success": success,
                    "path_id": path_id,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
            elif command["type"] == "ping":
                # 心跳檢測
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
    
    except WebSocketDisconnect:
        # 可能的清理操作
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Error in thinking WebSocket: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    finally:
        # 取消事件訂閱
        event_bus.unsubscribe("thinking.pulse_emitted", lambda data: event_handler("pulse_emitted", data))
        event_bus.unsubscribe("thinking.progress", lambda data: event_handler("thinking_progress", data))
        event_bus.unsubscribe("thinking.path_selected", lambda data: event_handler("path_selected", data))
        event_bus.unsubscribe("thinking.focus", lambda data: event_handler("focus", data))