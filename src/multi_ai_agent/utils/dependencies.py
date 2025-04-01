"""依賴項和工具函數."""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import JWTError
from bson import ObjectId

from multi_ai_agent.config.plans import ROLES

# 安全常量
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

# OAuth2登錄端點
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


async def get_db(request: Request):
    """獲取數據庫連接."""
    return request.app.state.db


async def get_redis(request: Request):
    """獲取Redis連接."""
    return request.app.state.redis


async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    """獲取當前用戶."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證憑據",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception
        
    return user


async def get_admin_user(current_user=Depends(get_current_user)):
    """獲取管理員用戶."""
    if current_user.get("role", 0) < ROLES["admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_user_quota(redis, user_id: str):
    """獲取用戶配額."""
    import json
    from multi_ai_agent.config.plans import USER_PLANS
    
    # 嘗試從Redis快取獲取配額
    cache_key = f"user:{user_id}:quota"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 由於這個函數被多個模塊調用，我們不能依賴db依賴項
    # 嘗試獲取應用程序狀態來訪問數據庫
    import asyncio
    db = None
    
    # 由於我們不在app中，需要獲取運行時的app實例
    from multi_ai_agent.app import get_app
    app = get_app()
    if app and hasattr(app.state, "db"):
        db = app.state.db
    
    if db:
        # 查詢用戶資料
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            # 默認配額
            return USER_PLANS["free"]
        
        # 檢查用戶是否有自定義配額
        from datetime import datetime
        custom_quota = user.get("custom_quota")
        if custom_quota:
            # 檢查自定義配額是否過期
            expires_at = custom_quota.get("expires_at")
            if expires_at and datetime.now() > expires_at:
                # 自定義配額已過期，使用計劃配額
                quota = USER_PLANS[user.get("plan", "free")]
            else:
                # 使用自定義配額
                quota = custom_quota
        else:
            # 使用計劃配額
            quota = USER_PLANS[user.get("plan", "free")]
        
        # 快取配額
        await redis.set(cache_key, json.dumps(quota), ex=3600)  # 快取1小時
        
        return quota
    
    # 如果無法獲取用戶信息，返回免費計劃配額
    return USER_PLANS["free"]


async def check_api_limit(redis, user_id: str):
    """檢查用戶是否超過API調用限制."""
    # 獲取用戶配額
    quota = await get_user_quota(redis, user_id)
    daily_limit = quota.get("daily_api_limit", 50)
    
    # 獲取當前計數
    counter_key = f"user:{user_id}:api_calls:daily"
    count = await redis.get(counter_key)
    count = int(count) if count else 0
    
    if count >= daily_limit:
        return False, f"超過每日API調用限制 ({daily_limit})"
    
    # 增加計數
    from datetime import datetime, timedelta
    pipe = redis.pipeline()
    pipe.incr(counter_key)
    
    # 如果是新的一天，設置過期時間
    if count == 0:
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        seconds_until_reset = (tomorrow - datetime.now()).total_seconds()
        pipe.expire(counter_key, int(seconds_until_reset))
    
    await pipe.execute()
    return True, None
