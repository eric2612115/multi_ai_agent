"""多AI代理系統主入口."""
import os
import time
import json
import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import jwt
from motor.motor_asyncio import AsyncIOMotorClient
import aioredis
from bson import ObjectId

from multi_ai_agent.clients import GeminiClient, ClaudeClient, FirecrawlClient
from multi_ai_agent.services.ws_manager import WSConnectionManager
from multi_ai_agent.services.task_manager import TaskManager
from multi_ai_agent.utils.dependencies import check_api_limit

# 加載環境變量
load_dotenv()

# 環境變量配置
CONFIG = {
    "jwt_secret_key": os.getenv("JWT_SECRET_KEY"),
    "jwt_algorithm": "HS256",
    "access_token_expire_minutes": 60 * 24,  # 24小時
    "mongodb_uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
    "mongodb_db": os.getenv("MONGODB_DB", "multi_ai_agent"),
    "redis_uri": os.getenv("REDIS_URI", "redis://localhost:6379/0"),
    "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000"),
    "default_ai_service": os.getenv("DEFAULT_AI_SERVICE", "gemini"),
    "max_tokens": int(os.getenv("MAX_TOKENS", 1024)),
    "use_advanced_models": os.getenv("ENABLE_ADVANCED_MODELS", "false").lower() == "true"
}

# 全局應用實例
_app_instance = None


def get_app():
    """取得應用實例."""
    return _app_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理應用程序的生命週期"""
    global _app_instance
    _app_instance = app
    
    # 配置信息
    app.state.config = CONFIG
    
    # 創建 MongoDB 連接
    app.state.mongo_client = AsyncIOMotorClient(CONFIG["mongodb_uri"])
    app.state.db = app.state.mongo_client[CONFIG["mongodb_db"]]
    
    # 創建 Redis 連接
    app.state.redis = await aioredis.from_url(CONFIG["redis_uri"])
    
    # 初始化 WebSocket 連接管理器
    app.state.ws_manager = WSConnectionManager()
    
    # 初始化 AI 客戶端
    app.state.gemini = GeminiClient()
    app.state.claude = ClaudeClient()
    app.state.firecrawl = FirecrawlClient()
    
    # 設置提取服務
    app.state.firecrawl.set_extraction_service(gemini_client=app.state.gemini, claude_client=app.state.claude)
    
    # 初始化任務管理器
    app.state.task_manager = TaskManager(app.state.redis, app.state.ws_manager)
    
    # 初始化任務處理器
    app.state.task_processes = []
    
    # 創建索引
    await create_mongodb_indexes(app.state.db)
    
    # 啟動任務處理器
    from multi_ai_agent.services.task_processors import start_task_processors
    await start_task_processors(app)
    
    print("✅ 服務已初始化，正在運行...")
    
    yield
    
    # 清理資源
    for task in app.state.task_processes:
        task.cancel()
    
    await app.state.mongo_client.close()
    await app.state.redis.close()
    
    _app_instance = None
    print("🛑 服務已關閉")


# 創建 FastAPI 應用
app = FastAPI(
    title="多 AI 代理系統",
    description="集成多種 AI 服務的 API",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生產環境中應該限制來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API限制中間件
@app.middleware("http")
async def api_limiter(request: Request, call_next):
    # 跳過不需要限制的路徑
    exclude_paths = ["/api/auth/login", "/api/auth/register", "/docs", "/redoc"]
    if request.url.path in exclude_paths or request.url.path.startswith("/static/"):
        return await call_next(request)
    
    # 獲取用戶ID
    user_id = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, CONFIG["jwt_secret_key"], algorithms=[CONFIG["jwt_algorithm"]])
            user_id = payload.get("sub")
        except:
            pass
    
    # 未驗證用戶不做限制
    if not user_id:
        return await call_next(request)
    
    # 檢查限制
    allowed, message = await check_api_limit(request.app.state.redis, user_id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": message}
        )
    
    # 繼續處理請求
    return await call_next(request)


# 監控中間件
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    
    # 獲取當前用戶
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, CONFIG["jwt_secret_key"], algorithms=[CONFIG["jwt_algorithm"]])
            user_id = payload.get("sub")
        except:
            pass
    
    # 處理請求
    response = await call_next(request)
    
    # 計算處理時間
    duration = (time.time() - start_time) * 1000
    
    # 記錄 API 調用
    if user_id:
        asyncio.create_task(log_api_usage(
            request.app.state.db,
            user_id,
            request.url.path,
            request.method,
            response.status_code,
            duration
        ))
    
    return response


async def log_api_usage(db, user_id, endpoint, method, status_code, duration):
    """記錄API使用情況"""
    await db.api_logs.insert_one({
        "user_id": ObjectId(user_id),
        "endpoint": endpoint,
        "method": method, 
        "status_code": status_code,
        "duration_ms": duration,
        "timestamp": datetime.now()
    })


async def create_mongodb_indexes(db):
    """創建必要的數據庫索引"""
    # 用戶索引
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username")
    
    # 會話索引
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("last_active")
    
    # 對話索引
    await db.conversations.create_index("user_id")
    await db.conversations.create_index("session_id")
    await db.conversations.create_index([("updated_at", -1)])
    
    # API 日誌索引
    await db.api_logs.create_index("user_id")
    await db.api_logs.create_index("timestamp")
    await db.api_logs.create_index([("timestamp", -1)])
    
    # 使用記錄索引
    await db.usage_logs.create_index("user_id")
    await db.usage_logs.create_index([("timestamp", -1)])
    
    print("✅ 數據庫索引已創建")


# 包含路由器
from multi_ai_agent.routers import auth, admin, conversations, tasks, websocket

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(conversations.router)
app.include_router(tasks.router)
app.include_router(websocket.router)


# 添加對話消息的函數 (被多個模塊調用)
async def add_message_to_conversation(conversation_id, message, current_user):
    """添加消息到對話並實施長度限制"""
    global _app_instance
    if not _app_instance:
        raise RuntimeError("應用實例未初始化")
        
    app = _app_instance
    
    # 獲取用戶配額
    user_id = str(current_user["_id"])
    from multi_ai_agent.utils.dependencies import get_user_quota
    quota = await get_user_quota(app.state.redis, user_id)
    max_messages = quota.get("max_messages_per_conversation", 50)
    
    # 獲取當前對話
    conversation = await app.state.db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conversation:
        raise HTTPException(status_code=404, detail="對話不存在")
    
    # 檢查所有權
    if str(conversation["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="無權訪問此對話")
    
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
        if user_id in app.state.ws_manager.active_connections:
            await app.state.ws_manager.send_message(
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
    await app.state.db.conversations.update_one(
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


# 健康檢查端點
@app.get("/health")
async def health_check():
    """健康檢查端點."""
    return {
        "status": "ok",
        "version": app.version,
        "timestamp": datetime.now()
    }


# 根路徑
@app.get("/")
async def root():
    """API根端點，返回基本信息."""
    return {
        "name": "多 AI 代理系統",
        "version": app.version,
        "docs": "/docs",
        "status": "運行中"
    }
