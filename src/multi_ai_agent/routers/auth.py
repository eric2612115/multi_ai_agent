"""認證相關的路由."""
import os
from typing import Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from bson import ObjectId

from multi_ai_agent.models.user import UserCreate, User
from multi_ai_agent.utils.security import get_password_hash, create_access_token
from multi_ai_agent.utils.dependencies import get_db, get_current_user

router = APIRouter(
    prefix="/api/auth",
    tags=["認證"],
    responses={401: {"description": "認證失敗"}},
)


# 用戶註冊
@router.post("/register")
async def register_user(user: UserCreate, db=Depends(get_db)):
    """註冊新用戶."""
    # 檢查用戶是否已存在
    existing = await db.users.find_one({"$or": [{"email": user.email}, {"username": user.username}]})
    if existing:
        if existing.get("email") == user.email:
            raise HTTPException(status_code=400, detail="此電子郵件已註冊")
        else:
            raise HTTPException(status_code=400, detail="此用戶名已被使用")
        
    # 創建新用戶
    hashed_password = get_password_hash(user.password)
    user_data = {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": hashed_password,
        "plan": "free",
        "role": 0,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    result = await db.users.insert_one(user_data)
    
    return {"user_id": str(result.inserted_id)}


# 用戶登錄獲取token
@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    """用戶登錄獲取access token."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶名或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(
        data={"sub": str(user["_id"])}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user["_id"]),
        "username": user["username"],
        "plan": user["plan"]
    }


# 獲取當前用戶信息
@router.get("/me")
async def read_users_me(current_user=Depends(get_current_user)):
    """獲取當前登錄用戶的信息."""
    return format_user(current_user)


async def authenticate_user(db, username: str, password: str):
    """驗證用戶."""
    from multi_ai_agent.utils.security import verify_password
    
    user = await db.users.find_one({"$or": [{"username": username}, {"email": username}]})
    if not user:
        return False
    
    if not verify_password(password, user["hashed_password"]):
        return False
    
    return user


def format_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """格式化用戶信息."""
    if user:
        return {
            "id": str(user["_id"]) if "_id" in user else None,
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "plan": user.get("plan", "free"),
            "role": user.get("role", 0),
            "disabled": user.get("disabled", False),
            "created_at": user.get("created_at"),
            "plan_expires_at": user.get("plan_expires_at"),
            "auth_provider": user.get("auth_provider")
        }
    return None
