"""用戶相關的數據模型."""
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    """用戶創建模型."""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    """用戶更新模型."""
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    disabled: Optional[bool] = None


class PlanUpdate(BaseModel):
    """用戶計劃更新模型."""
    plan: str
    expires_at: Optional[datetime] = None


class CustomQuota(BaseModel):
    """自定義配額模型."""
    daily_api_limit: Optional[int] = None
    concurrent_tasks: Optional[int] = None
    max_messages_per_conversation: Optional[int] = None
    max_conversations: Optional[int] = None
    advanced_models: Optional[bool] = None
    expires_at: Optional[datetime] = None


class User(BaseModel):
    """用戶模型."""
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    plan: str = "free"  # "free", "basic", "pro"
    role: int = 0  # 0: user, 10: manager, 20: admin, 30: superadmin
    auth_provider: Optional[str] = None  # "password", "google", etc.
    plan_expires_at: Optional[datetime] = None
    custom_quota: Optional[Dict] = None
