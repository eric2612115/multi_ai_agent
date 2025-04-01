"""對話相關的路由."""
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from bson import ObjectId

from multi_ai_agent.utils.dependencies import get_db, get_redis, get_current_user, get_user_quota

router = APIRouter(
    prefix="/api/conversations",
    tags=["對話"],
    responses={401: {"description": "認證失敗"}},
)


# 創建新對話
@router.post("")
async def create_conversation(
    request: Request,
    session_id: Optional[str] = None,
    title: Optional[str] = "新對話",
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """創建新的對話."""
    user_id = str(current_user["_id"])
    
    # 檢查用戶是否超過對話數量限制
    quota = await get_user_quota(redis, user_id)
    max_conversations = quota.get("max_conversations", 5)
    
    count = await db.conversations.count_documents({"user_id": ObjectId(user_id)})
    if count >= max_conversations:
        raise HTTPException(status_code=400, detail=f"已達到最大對話數量限制 ({max_conversations})")
    
    # 如果沒有提供會話ID，創建新會話
    if not session_id:
        session_result = await db.sessions.insert_one({
            "user_id": ObjectId(user_id),
            "created_at": datetime.now(),
            "last_active": datetime.now()
        })
        session_id = str(session_result.inserted_id)
    else:
        # 驗證會話存在且屬於該用戶
        session = await db.sessions.find_one({
            "_id": ObjectId(session_id),
            "user_id": ObjectId(user_id)
        })
        if not session:
            raise HTTPException(status_code=404, detail="會話不存在")
        
        # 更新會話活動時間
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"last_active": datetime.now()}}
        )
    
    # 創建新對話
    conversation_data = {
        "user_id": ObjectId(user_id),
        "session_id": ObjectId(session_id),
        "title": title,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "messages": [],
        "settings": {
            "default_ai_service": request.app.state.config.get("default_ai_service", "gemini"),
            "max_tokens": request.app.state.config.get("max_tokens", 1024),
            "use_advanced_models": request.app.state.config.get("use_advanced_models", False)
        }
    }
    
    result = await db.conversations.insert_one(conversation_data)
    
    return {
        "conversation_id": str(result.inserted_id),
        "session_id": session_id,
        "title": title,
        "created_at": conversation_data["created_at"]
    }


# 獲取用戶的所有對話
@router.get("")
async def get_conversations(
    session_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """獲取用戶的所有對話."""
    user_id = str(current_user["_id"])
    
    # 构建查询条件
    query = {"user_id": ObjectId(user_id)}
    if session_id:
        query["session_id"] = ObjectId(session_id)
    
    # 查詢對話
    conversations = await db.conversations.find(query).sort(
        "updated_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
    # 格式化输出
    formatted_conversations = []
    for conv in conversations:
        formatted_conversations.append({
            "id": str(conv["_id"]),
            "title": conv.get("title", "無標題對話"),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "session_id": str(conv["session_id"]),
            "message_count": len(conv.get("messages", [])),
            "settings": conv.get("settings", {})
        })
    
    return formatted_conversations


# 獲取特定對話
@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """獲取特定對話的詳細信息."""
    user_id = str(current_user["_id"])
    
    # 查詢對話
    conversation = await db.conversations.find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(user_id)
    })
    
    if not conversation:
        raise HTTPException(status_code=404, detail="對話不存在或您無權訪問")
    
    # 格式化输出
    return {
        "id": str(conversation["_id"]),
        "title": conversation.get("title", "無標題對話"),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "session_id": str(conversation.get("session_id")),
        "messages": conversation.get("messages", []),
        "settings": conversation.get("settings", {})
    }


# 添加消息到對話
@router.post("/{conversation_id}/messages")
async def add_message(
    conversation_id: str,
    message: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """添加消息到對話."""
    user_id = str(current_user["_id"])
    
    # 獲取用戶配額
    quota = await get_user_quota(redis, user_id)
    max_messages = quota.get("max_messages_per_conversation", 50)
    
    # 獲取當前對話
    conversation = await db.conversations.find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(user_id)
    })
    
    if not conversation:
        raise HTTPException(status_code=404, detail="對話不存在")
    
    # 添加新消息
    new_message = {
        "role": message["role"],
        "content": message["content"],
        "timestamp": datetime.now()
    }
    
    # 添加元數據（如果有）
    if "metadata" in message:
        new_message["metadata"] = message["metadata"]
    
    # 獲取當前消息列表
    current_messages = conversation.get("messages", [])
    current_messages.append(new_message)
    
    # 檢查是否超出限制
    is_trimmed = False
    if len(current_messages) > max_messages:
        # 發送通知
        ws_manager = request.app.state.ws_manager
        if user_id in ws_manager.active_connections:
            await ws_manager.send_message(
                user_id,
                {
                    "type": "system_notification",
                    "content": f"此對話已達到消息上限 ({max_messages})。較早的消息已被修剪。",
                    "conversation_id": conversation_id
                }
            )
        
        # 修剪消息列表
        current_messages = current_messages[-max_messages:]
        is_trimmed = True
    
    # 更新對話
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {
                "messages": current_messages,
                "updated_at": datetime.now()
            }
        }
    )
    
    return {
        "message_added": True,
        "message_count": len(current_messages),
        "is_trimmed": is_trimmed
    }


# 更新對話設置
@router.put("/{conversation_id}/settings")
async def update_conversation_settings(
    conversation_id: str,
    settings: Dict[str, Any],
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """更新對話設置."""
    user_id = str(current_user["_id"])
    
    # 查詢對話
    conversation = await db.conversations.find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(user_id)
    })
    
    if not conversation:
        raise HTTPException(status_code=404, detail="對話不存在或您無權訪問")
    
    # 更新設置
    current_settings = conversation.get("settings", {})
    current_settings.update(settings)
    
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"settings": current_settings}}
    )
    
    return {"updated": True, "settings": current_settings}


# 刪除對話
@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """刪除對話."""
    user_id = str(current_user["_id"])
    
    # 查詢對話
    conversation = await db.conversations.find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(user_id)
    })
    
    if not conversation:
        raise HTTPException(status_code=404, detail="對話不存在或您無權訪問")
    
    # 刪除對話
    await db.conversations.delete_one({"_id": ObjectId(conversation_id)})
    
    return {"deleted": True}
