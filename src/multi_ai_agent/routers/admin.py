"""管理員相關的路由."""
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from multi_ai_agent.models.user import PlanUpdate, CustomQuota, UserUpdate
from multi_ai_agent.utils.dependencies import get_db, get_redis, get_admin_user
from multi_ai_agent.routers.auth import format_user

router = APIRouter(
    prefix="/api/admin",
    tags=["管理員"],
    responses={401: {"description": "認證失敗"}, 403: {"description": "權限不足"}},
)


# 獲取所有用戶
@router.get("/users/")
async def get_all_users(
    skip: int = 0, 
    limit: int = 100,
    search: Optional[str] = None,
    current_user=Depends(get_admin_user),
    db=Depends(get_db)
):
    """獲取所有用戶(管理員專用)."""
    query = {}
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}}
        ]
    
    users = await db.users.find(query).skip(skip).limit(limit).to_list(length=limit)
    count = await db.users.count_documents(query)
    
    return {
        "users": [format_user(user) for user in users],
        "total": count
    }


# 獲取特定用戶
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user=Depends(get_admin_user),
    db=Depends(get_db)
):
    """獲取特定用戶信息(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    return format_user(user)


# 更新用戶信息
@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user=Depends(get_admin_user),
    db=Depends(get_db)
):
    """更新用戶信息(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 準備更新數據
    update_data = {}
    
    if user_update.username is not None:
        # 檢查用戶名是否已存在
        if user_update.username != user.get("username"):
            existing = await db.users.find_one({"username": user_update.username})
            if existing:
                raise HTTPException(status_code=400, detail="用戶名已存在")
        update_data["username"] = user_update.username
    
    if user_update.email is not None:
        # 檢查郵箱是否已存在
        if user_update.email != user.get("email"):
            existing = await db.users.find_one({"email": user_update.email})
            if existing:
                raise HTTPException(status_code=400, detail="郵箱已存在")
        update_data["email"] = user_update.email
    
    if user_update.full_name is not None:
        update_data["full_name"] = user_update.full_name
    
    if user_update.disabled is not None:
        update_data["disabled"] = user_update.disabled
    
    if user_update.password is not None:
        from multi_ai_agent.utils.security import get_password_hash
        update_data["hashed_password"] = get_password_hash(user_update.password)
    
    # 更新用戶
    if update_data:
        update_data["updated_at"] = datetime.now()
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    
    # 返回更新後的用戶
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    return format_user(updated_user)


# 更新用戶計劃
@router.put("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    plan_update: PlanUpdate,
    current_user=Depends(get_admin_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """更新用戶計劃(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 更新用戶計劃
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "plan": plan_update.plan,
            "plan_expires_at": plan_update.expires_at,
            "updated_at": datetime.now()
        }}
    )
    
    # 清除用戶的API使用緩存
    await redis.delete(f"user:{user_id}:api_calls:daily")
    
    # 清除配額快取
    await redis.delete(f"user:{user_id}:quota")
    
    return {"message": "用戶計劃已更新"}


# 重置用戶API使用次數
@router.post("/users/{user_id}/reset-quota")
async def reset_user_quota(
    user_id: str,
    current_user=Depends(get_admin_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """重置用戶API使用次數(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 重置計數器
    await redis.delete(f"user:{user_id}:api_calls:daily")
    
    return {"message": "用戶API配額已重置"}


# 設置自定義配額
@router.put("/users/{user_id}/custom-quota")
async def set_custom_quota(
    user_id: str,
    quota: CustomQuota,
    current_user=Depends(get_admin_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """設置用戶自定義配額(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 設置自定義配額
    custom_quota = {}
    if quota.daily_api_limit is not None:
        custom_quota["daily_api_limit"] = quota.daily_api_limit
    if quota.concurrent_tasks is not None:
        custom_quota["concurrent_tasks"] = quota.concurrent_tasks
    if quota.max_messages_per_conversation is not None:
        custom_quota["max_messages_per_conversation"] = quota.max_messages_per_conversation
    if quota.max_conversations is not None:
        custom_quota["max_conversations"] = quota.max_conversations
    if quota.advanced_models is not None:
        custom_quota["advanced_models"] = quota.advanced_models
    
    custom_quota["expires_at"] = quota.expires_at
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "custom_quota": custom_quota,
            "updated_at": datetime.now()
        }}
    )
    
    # 清除配額快取
    await redis.delete(f"user:{user_id}:quota")
    
    return {"message": "已設置自定義配額"}


# 獲取用戶狀態和統計
@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    current_user=Depends(get_admin_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """獲取用戶統計信息(管理員專用)."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用戶不存在")
    
    # 獲取各種統計數據
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # API調用次數
    api_calls_key = f"user:{user_id}:api_calls:daily"
    api_calls_today = await redis.get(api_calls_key)
    api_calls_today = int(api_calls_today) if api_calls_today else 0
    
    # 查詢數據庫以獲取更多統計
    active_tasks = await redis.scard(f"user:{user_id}:active_tasks")
    active_tasks = int(active_tasks) if active_tasks else 0

    total_conversations = await db.conversations.count_documents({"user_id": ObjectId(user_id)})
    latest_conversations = await db.conversations.find(
        {"user_id": ObjectId(user_id)}
    ).sort("updated_at", -1).limit(5).to_list(length=5)
    
    # 格式化對話數據
    formatted_conversations = []
    for conv in latest_conversations:
        formatted_conversations.append({
            "id": str(conv["_id"]),
            "title": conv.get("title", "無標題對話"),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "message_count": len(conv.get("messages", []))
        })
    
    # 獲取使用記錄
    usage_logs = await db.api_logs.find(
        {"user_id": ObjectId(user_id)}
    ).sort("timestamp", -1).limit(100).to_list(length=100)
    
    # 格式化日誌
    formatted_logs = []
    for log in usage_logs:
        formatted_logs.append({
            "endpoint": log.get("endpoint"),
            "method": log.get("method"),
            "status_code": log.get("status_code"),
            "duration_ms": log.get("duration_ms"),
            "timestamp": log.get("timestamp")
        })

    # 獲取用戶配額
    from multi_ai_agent.utils.dependencies import get_user_quota
    quota = await get_user_quota(redis, user_id)
    
    return {
        "user": format_user(user),
        "stats": {
            "api_calls_today": api_calls_today,
            "active_tasks": active_tasks,
            "total_conversations": total_conversations,
            "quota": quota,
            "latest_conversations": formatted_conversations,
            "usage_logs": formatted_logs[:20]  # 只返回前20條日誌
        }
    }


# 系統概覽(管理員儀表板)
@router.get("/dashboard")
async def get_dashboard_stats(
    current_user=Depends(get_admin_user),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """獲取系統統計信息(管理員專用)."""
    # 用戶統計
    total_users = await db.users.count_documents({})
    new_users_today = await db.users.count_documents({
        "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    
    # 計劃統計
    plans = {}
    async for doc in db.users.aggregate([
        {"$group": {"_id": "$plan", "count": {"$sum": 1}}}
    ]):
        plans[doc["_id"]] = doc["count"]
    
    # 對話統計
    total_conversations = await db.conversations.count_documents({})
    conversations_today = await db.conversations.count_documents({
        "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    
    # API統計 - 匯總當日API使用量
    api_logs_today = await db.api_logs.count_documents({
        "timestamp": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    
    # 獲取所有活動任務數量(近似值)
    active_tasks_keys = await redis.keys("user:*:active_tasks")
    active_tasks_count = len(active_tasks_keys)
    
    # 返回統計數據
    return {
        "users": {
            "total": total_users,
            "new_today": new_users_today,
            "by_plan": plans
        },
        "conversations": {
            "total": total_conversations,
            "today": conversations_today
        },
        "api": {
            "calls_today": api_logs_today
        },
        "tasks": {
            "active": active_tasks_count
        },
        "timestamp": datetime.now()
    }
