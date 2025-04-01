"""WebSocket相關路由."""
import json
from typing import Dict, Optional, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
import jwt

from multi_ai_agent.services.ai_processor import handle_ai_query
from multi_ai_agent.utils.dependencies import get_db

router = APIRouter(
    tags=["WebSocket"],
)


@router.websocket("/api/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str, request: Request):
    """WebSocket連接端點."""
    # 獲取應用配置
    SECRET_KEY = request.app.state.config.get("jwt_secret_key")
    ALGORITHM = request.app.state.config.get("jwt_algorithm", "HS256")
    
    # 驗證令牌
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except:
        await websocket.close(code=1008)
        return
    
    # 獲取WebSocket連接管理器
    manager = request.app.state.ws_manager
    
    # 連接客戶端
    success = await manager.connect(user_id, websocket, request.app.state.db)
    if not success:
        return  # 連接處理錯誤
    
    # 處理消息
    try:
        while True:
            data = await websocket.receive_text()
            try:
                # 解析JSON消息
                message_data = json.loads(data)
                message_type = message_data.get("type", "")
                
                # 處理不同類型的消息
                if message_type == "ping":
                    await manager.send_message(user_id, {"type": "pong"})
                    
                elif message_type == "query":
                    # 創建AI查詢任務
                    task_id = await handle_ai_query(request.app, user_id, message_data)
                    if task_id:
                        await manager.send_message(
                            user_id, 
                            {"type": "task_created", "task_id": task_id}
                        )
                    else:
                        await manager.send_message(
                            user_id,
                            {"type": "error", "message": "創建任務失敗，請檢查參數"}
                        )
                    
                elif message_type == "cancel_task":
                    task_id = message_data.get("task_id")
                    success, message = await request.app.state.task_manager.cancel_task(user_id, task_id)
                    await manager.send_message(
                        user_id,
                        {"type": "task_cancelled", "success": success, "message": message}
                    )
                
                elif message_type == "join_conversation":
                    conversation_id = message_data.get("conversation_id")
                    if conversation_id:
                        # 驗證會話存在且屬於該用戶
                        conversation = await request.app.state.db.conversations.find_one({
                            "_id": ObjectId(conversation_id),
                            "user_id": ObjectId(user_id)
                        })
                        if conversation:
                            await manager.send_message(
                                user_id,
                                {"type": "joined_conversation", "conversation_id": conversation_id}
                            )
                        else:
                            await manager.send_message(
                                user_id,
                                {"type": "error", "message": "對話不存在或您無權訪問"}
                            )
                    else:
                        await manager.send_message(
                            user_id,
                            {"type": "error", "message": "未提供對話ID"}
                        )
                    
                elif message_type == "leave_conversation":
                    await manager.send_message(
                        user_id,
                        {"type": "left_conversation"}
                    )
                    
                else:
                    await manager.send_message(
                        user_id,
                        {"type": "error", "message": "未知的消息類型"}
                    )
                    
            except json.JSONDecodeError:
                await manager.send_message(
                    user_id,
                    {"type": "error", "message": "無效的JSON格式"}
                )
    
    except WebSocketDisconnect:
        await manager.disconnect(user_id)
