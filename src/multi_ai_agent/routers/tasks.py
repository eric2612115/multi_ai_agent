"""任務相關的路由."""
from typing import Dict, List, Optional, Any, Union
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId

from multi_ai_agent.utils.dependencies import get_db, get_redis, get_current_user

router = APIRouter(
    prefix="/api/tasks",
    tags=["任務"],
    responses={401: {"description": "認證失敗"}},
)


# 獲取任務信息
@router.get("/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    """獲取任務信息."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 獲取任務
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")
    
    # 檢查任務所有權
    task_user_id = task.get('user_id')
    if task_user_id != user_id:
        raise HTTPException(status_code=403, detail="無權訪問此任務")
    
    # 處理結果和錯誤
    result = task.get('result')
    if result:
        try:
            task['result'] = json.loads(result)
        except:
            pass
    
    error = task.get('error')
    if error:
        task['error'] = error
    
    return task


# 獲取用戶的活動任務
@router.get("")
async def get_active_tasks(
    request: Request,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    redis=Depends(get_redis)
):
    """獲取用戶的活動任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 獲取用戶活動任務ID
    task_ids = await redis.smembers(f"user:{user_id}:active_tasks")
    task_ids = [task_id.decode('utf-8') if isinstance(task_id, bytes) else task_id for task_id in task_ids]
    
    # 獲取任務詳情
    tasks = []
    for task_id in task_ids:
        task = await task_manager.get_task(task_id)
        if task:
            # 過濾狀態
            if status and task.get('status') != status:
                continue
                
            # 簡化結果
            if 'result' in task:
                task.pop('result')
            tasks.append(task)
    
    return {"tasks": tasks}


# 取消任務
@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    """取消任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 取消任務
    success, message = await task_manager.cancel_task(user_id, task_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


# 創建文本生成任務
@router.post("/generate-text")
async def create_text_generation_task(
    params: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user)
):
    """創建文本生成任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 驗證參數
    if "prompt" not in params:
        raise HTTPException(status_code=400, detail="未提供提示文本")
    
    # 創建任務
    task_id, message = await task_manager.create_task(
        user_id, 
        "generate_text", 
        params
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail=message)
    
    return {"task_id": task_id, "message": "文本生成任務已創建"}


# 創建網頁抓取任務
@router.post("/scrape-url")
async def create_scrape_task(
    params: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user)
):
    """創建網頁抓取任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 驗證參數
    if "url" not in params:
        raise HTTPException(status_code=400, detail="未提供URL")
    
    # 創建任務
    task_id, message = await task_manager.create_task(
        user_id, 
        "scrape_url", 
        params
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail=message)
    
    return {"task_id": task_id, "message": "網頁抓取任務已創建"}


# 創建網絡搜索任務
@router.post("/search-web")
async def create_search_task(
    params: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user)
):
    """創建網絡搜索任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 驗證參數
    if "query" not in params:
        raise HTTPException(status_code=400, detail="未提供搜索查詢")
    
    # 創建任務
    task_id, message = await task_manager.create_task(
        user_id, 
        "search_web", 
        params
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail=message)
    
    return {"task_id": task_id, "message": "網絡搜索任務已創建"}


# 創建智能提取任務
@router.post("/smart-extract")
async def create_extract_task(
    params: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user)
):
    """創建智能提取任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 驗證參數
    if "url" not in params:
        raise HTTPException(status_code=400, detail="未提供URL")
    if "objective" not in params:
        raise HTTPException(status_code=400, detail="未提供提取目標")
    
    # 創建任務
    task_id, message = await task_manager.create_task(
        user_id, 
        "smart_extract", 
        params
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail=message)
    
    return {"task_id": task_id, "message": "智能提取任務已創建"}


# 創建高級提取任務
@router.post("/advanced-extract")
async def create_advanced_extract_task(
    params: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user),
    redis=Depends(get_redis)
):
    """創建高級提取任務."""
    user_id = str(current_user["_id"])
    
    # 獲取任務管理器
    task_manager = request.app.state.task_manager
    
    # 驗證參數
    if "urls" not in params or not params["urls"]:
        raise HTTPException(status_code=400, detail="未提供URLs")
    if "objective" not in params:
        raise HTTPException(status_code=400, detail="未提供提取目標")
    
    # 檢查用戶權限
    from multi_ai_agent.utils.dependencies import get_user_quota
    quota = await get_user_quota(redis, user_id)
    if not quota.get("advanced_models", False):
        raise HTTPException(status_code=403, detail="您的帳戶未啟用高級提取功能。請升級您的計劃。")
    
    # 創建任務
    task_id, message = await task_manager.create_task(
        user_id, 
        "advanced_extract", 
        params
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail=message)
    
    return {"task_id": task_id, "message": "高級提取任務已創建"}
