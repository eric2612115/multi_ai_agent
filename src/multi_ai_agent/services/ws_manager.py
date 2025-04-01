"""WebSocket連接管理器."""
import json
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
from fastapi import WebSocket


class WSConnectionManager:
    """WebSocket連接管理器."""
    
    def __init__(self):
        self.active_connections = {}  # user_id -> websocket
        self.user_sessions = {}       # user_id -> session_id
        
    async def connect(self, user_id: str, websocket: WebSocket, db, session_id: Optional[str] = None) -> bool:
        """建立WebSocket連接."""
        # 驗證用戶和建立連接
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # 處理會話ID
        if session_id:
            # 驗證會話存在且屬於該用戶
            session = await db.sessions.find_one({
                "_id": ObjectId(session_id),
                "user_id": ObjectId(user_id)
            })
            if not session:
                await self.send_error(user_id, "會話不存在")
                return False
        else:
            # 創建新會話
            result = await db.sessions.insert_one({
                "user_id": ObjectId(user_id),
                "created_at": datetime.now(),
                "last_active": datetime.now()
            })
            session_id = str(result.inserted_id)
            
        self.user_sessions[user_id] = session_id
        
        # 更新會話活動時間
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"last_active": datetime.now()}}
        )
        
        # 發送歡迎消息
        await self.send_message(
            user_id,
            {
                "type": "system_message",
                "content": "已連接到多AI代理系統",
                "session_id": session_id
            }
        )
        
        return True
        
    async def disconnect(self, user_id: str):
        """斷開WebSocket連接."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            
    async def send_message(self, user_id: str, message: Dict[str, Any]):
        """向指定用戶發送消息."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def send_error(self, user_id: str, message: str):
        """向指定用戶發送錯誤消息."""
        await self.send_message(
            user_id,
            {
                "type": "error",
                "message": message
            }
        )
            
    async def send_task_update(self, user_id: str, task_id: str, status: str, 
                             progress: int, message: Optional[str] = None, 
                             result: Optional[Any] = None):
        """向指定用戶發送任務更新."""
        update = {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress
        }
        
        if message:
            update["message"] = message
            
        if result:
            update["result"] = result
            
        await self.send_message(user_id, update)
        
    async def broadcast(self, users: list, message: Dict[str, Any]):
        """向多個用戶廣播消息."""
        for user_id in users:
            if user_id in self.active_connections:
                await self.send_message(user_id, message)
