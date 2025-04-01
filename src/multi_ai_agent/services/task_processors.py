"""任務處理器模組，用於處理異步任務."""
import asyncio
import json
import time
import random
from typing import Dict, Any, Callable, Optional
from bson import ObjectId

async def start_task_processors(app):
    """啟動任務處理器.
    
    Args:
        app: FastAPI應用實例
    """
    # 任務類型及其處理器
    task_processors = {
        "generate_text": process_generate_text,
        "scrape_url": process_scrape_url,
        "search_web": process_search_web,
        "smart_extract": process_smart_extract,
        "advanced_extract": process_advanced_extract
    }
    
    # 為每種任務類型創建處理器
    for task_type, processor in task_processors.items():
        app.state.task_processes.append(
            asyncio.create_task(
                run_task_processor(task_type, processor, app)
            )
        )
    
    # 任務監控器
    app.state.task_processes.append(
        asyncio.create_task(
            monitor_tasks(app)
        )
    )
    
    print(f"✅ 已啟動 {len(task_processors)} 個任務處理器和 1 個監控器")


async def run_task_processor(task_type: str, processor_func: Callable, app):
    """運行特定類型的任務處理器.
    
    Args:
        task_type: 任務類型
        processor_func: 處理函數
        app: FastAPI應用實例
    """
    redis = app.state.redis
    task_manager = app.state.task_manager
    
    while True:
        try:
            # 從隊列獲取任務
            tasks = await redis.zpopmax(f"tasks:queue:{task_type}", count=1)
            if not tasks:
                await asyncio.sleep(1)
                continue
                
            task_id = tasks[0][0].decode('utf-8') if isinstance(tasks[0][0], bytes) else tasks[0][0]
            
            # 嘗試獲取任務鎖
            lock_acquired = await redis.set(
                f"task:{task_id}:lock", 
                "worker", 
                nx=True, 
                ex=60
            )
            
            if not lock_acquired:
                continue  # 其他工作進程已獲取該任務
            
            # 獲取任務數據
            task_data = await task_manager.get_task(task_id)
            if not task_data:
                continue
                
            # 轉換格式
            task_params = json.loads(task_data.get('params', '{}'))
            
            # 更新狀態為運行中
            await task_manager.update_task_status(task_id, "running", progress=5)
            
            try:
                # 執行任務
                result = await processor_func(task_params, task_manager, task_id, app)
                
                # 更新任務結果
                await task_manager.update_task_status(
                    task_id, 
                    "completed", 
                    progress=100,
                    result=json.dumps(result)
                )
                
            except Exception as e:
                # 記錄錯誤
                await task_manager.update_task_status(
                    task_id, 
                    "failed", 
                    error=str(e)
                )
                # 記錄詳細錯誤信息
                print(f"任務 {task_id} 執行失敗: {str(e)}")
            
            # 釋放鎖
            await redis.delete(f"task:{task_id}:lock")
            
        except Exception as e:
            print(f"任務處理器 {task_type} 錯誤: {str(e)}")
            await asyncio.sleep(5)  # 發生錯誤時暫停一下


async def monitor_tasks(app):
    """監控任務的超時和死鎖.
    
    Args:
        app: FastAPI應用實例
    """
    redis = app.state.redis
    task_manager = app.state.task_manager
    
    while True:
        try:
            # 檢查所有活動的任務
            task_patterns = await redis.keys("task:*")
            
            for task_key in task_patterns:
                # 只處理主任務數據，不處理鎖
                if b":lock" in task_key:
                    continue
                    
                # 獲取任務ID
                task_id = task_key.decode('utf-8').split(":", 1)[1] if isinstance(task_key, bytes) else task_key.split(":", 1)[1]
                
                # 獲取任務數據
                task_data = await task_manager.get_task(task_id)
                if not task_data:
                    continue
                    
                # 檢查運行中的任務是否超時
                if task_data.get('status') == 'running':
                    updated_at = float(task_data.get('updated_at', 0))
                    timeout = int(task_data.get('timeout', 600))
                    
                    # 如果超過超時時間
                    if time.time() - updated_at > timeout:
                        # 檢查是否有鎖
                        lock_exists = await redis.exists(f"task:{task_id}:lock")
                        
                        if lock_exists:
                            # 清除鎖
                            await redis.delete(f"task:{task_id}:lock")
                            
                        # 將任務標記為失敗
                        await task_manager.update_task_status(
                            task_id,
                            "failed",
                            error=f"任務執行超時 (超過 {timeout} 秒)"
                        )
            
            # 每30秒檢查一次
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"任務監控錯誤: {str(e)}")
            await asyncio.sleep(10)


# === 具體的任務處理函數 ===

async def process_generate_text(params: Dict[str, Any], task_manager, task_id: str, app) -> Dict[str, Any]:
    """處理文本生成任務.
    
    Args:
        params: 任務參數
        task_manager: 任務管理器
        task_id: 任務ID
        app: FastAPI應用實例
        
    Returns:
        生成結果
    """
    await task_manager.update_task_status(task_id, "running", progress=10)
    
    # 獲取參數
    prompt = params.get("prompt", "")
    model = params.get("model")
    service = params.get("service", "gemini")
    max_tokens = params.get("max_tokens", 1024)
    conversation_id = params.get("conversation_id")
    
    await task_manager.update_task_status(task_id, "running", progress=20, 
                                        result=json.dumps({"partial_text": "正在處理..."}))
    
    # 選擇服務
    if service.lower() == "gemini":
        client = app.state.gemini
        if model:
            client.set_model(model)
    elif service.lower() == "claude":
        client = app.state.claude
        if model:
            client.set_model(model)
    else:
        raise ValueError(f"不支持的服務: {service}")
        
    # 生成文本
    await task_manager.update_task_status(task_id, "running", progress=40, 
                                        result=json.dumps({"partial_text": "正在生成回應..."}))
    
    text = client.generate_text(prompt, max_tokens=max_tokens)
    
    await task_manager.update_task_status(task_id, "running", progress=80, 
                                        result=json.dumps({"partial_text": text[:100] + "..."}))
    
    # 如果提供了conversation_id，將結果添加到對話中
    if conversation_id:
        # 獲取任務用戶ID
        task_data = await task_manager.get_task(task_id)
        user_id = task_data.get('user_id')
        
        # 獲取用戶信息
        user = await app.state.db.users.find_one({"_id": ObjectId(user_id)})
        
        # 添加消息到對話
        from multi_ai_agent.app import add_message_to_conversation
        await add_message_to_conversation(
            conversation_id,
            {
                "role": "assistant",
                "content": text,
                "metadata": {
                    "model": model or (client.model if hasattr(client, 'model') else "unknown"),
                    "service": service,
                    "task_id": task_id
                }
            },
            user
        )
    
    return {
        "text": text,
        "model": model or (client.model if hasattr(client, 'model') else "unknown"),
        "service": service,
        "tokens": len(text.split()) * 1.3  # 估算的token數量
    }


async def process_scrape_url(params: Dict[str, Any], task_manager, task_id: str, app) -> Dict[str, Any]:
    """處理URL抓取任務.
    
    Args:
        params: 任務參數
        task_manager: 任務管理器
        task_id: 任務ID
        app: FastAPI應用實例
        
    Returns:
        抓取結果
    """
    await task_manager.update_task_status(task_id, "running", progress=10)
    
    # 獲取參數
    url = params.get("url", "")
    formats = params.get("formats", ["markdown"])
    
    await task_manager.update_task_status(task_id, "running", progress=30, 
                                        result=json.dumps({"status": f"正在抓取 {url}..."}))
    
    # 抓取URL
    result = app.state.firecrawl.scrape_url(url, formats)
    
    await task_manager.update_task_status(task_id, "running", progress=90)
    
    return {
        "url": url,
        "content": result,
        "formats": formats
    }


async def process_search_web(params: Dict[str, Any], task_manager, task_id: str, app) -> Dict[str, Any]:
    """處理網絡搜索任務.
    
    Args:
        params: 任務參數
        task_manager: 任務管理器
        task_id: 任務ID
        app: FastAPI應用實例
        
    Returns:
        搜索結果
    """
    await task_manager.update_task_status(task_id, "running", progress=10)
    
    # 獲取參數
    query = params.get("query", "")
    
    await task_manager.update_task_status(task_id, "running", progress=30, 
                                        result=json.dumps({"status": f"正在搜索: {query}..."}))  
    
    # 搜索網絡
    result = app.state.gemini.search_web(query)
    
    await task_manager.update_task_status(task_id, "running", progress=90)
    
    return {
        "query": query,
        "result": result
    }


async def process_smart_extract(params: Dict[str, Any], task_manager, task_id: str, app) -> Dict[str, Any]:
    """處理智能提取任務.
    
    Args:
        params: 任務參數
        task_manager: 任務管理器
        task_id: 任務ID
        app: FastAPI應用實例
        
    Returns:
        提取結果
    """
    await task_manager.update_task_status(task_id, "running", progress=10)
    
    # 獲取參數
    url = params.get("url", "")
    objective = params.get("objective", "")
    use_advanced_model = params.get("use_advanced_model", False)
    
    await task_manager.update_task_status(task_id, "running", progress=20, 
                                        result=json.dumps({"status": f"正在分析網站: {url}..."}))  
    
    # 檢查用戶權限
    if use_advanced_model:
        # 獲取任務用戶ID
        task_data = await task_manager.get_task(task_id)
        user_id = task_data.get('user_id')
        
        # 獲取用戶配額
        from multi_ai_agent.app import get_user_quota
        quota = await get_user_quota(app.state.redis, user_id)
        
        # 檢查是否可以使用高級模型
        if not quota.get("advanced_models", False):
            await task_manager.update_task_status(task_id, "running", progress=25, 
                                              result=json.dumps({"status": "高級模型不可用，使用標準模型..."}))  
            use_advanced_model = False
            
    # 智能提取
    await task_manager.update_task_status(task_id, "running", progress=40, 
                                       result=json.dumps({"status": "正在提取相關信息..."}))  
    
    result = app.state.firecrawl.smart_extract(
        url=url,
        objective=objective,
        use_advanced_model=use_advanced_model
    )
    
    if not result:
        return {
            "success": False,
            "message": "無法找到符合目標的信息。請嘗試重新定義目標或使用不同的網站。"
        }
    
    await task_manager.update_task_status(task_id, "running", progress=90)
    
    return {
        "success": True,
        "url": url,
        "objective": objective,
        "data": result,
        "used_advanced_model": use_advanced_model
    }


async def process_advanced_extract(params: Dict[str, Any], task_manager, task_id: str, app) -> Dict[str, Any]:
    """處理高級提取任務.
    
    Args:
        params: 任務參數
        task_manager: 任務管理器
        task_id: 任務ID
        app: FastAPI應用實例
        
    Returns:
        提取結果
    """
    await task_manager.update_task_status(task_id, "running", progress=10)
    
    # 獲取參數
    urls = params.get("urls", [])
    objective = params.get("objective", "")
    entity = params.get("entity")
    
    if not urls:
        return {
            "success": False,
            "message": "沒有提供URL"
        }
    
    # 獲取任務用戶ID
    task_data = await task_manager.get_task(task_id)
    user_id = task_data.get('user_id')
    
    # 獲取用戶配額
    from multi_ai_agent.app import get_user_quota
    quota = await get_user_quota(app.state.redis, user_id)
    
    # 檢查是否可以使用高級提取
    if not quota.get("advanced_models", False):
        return {
            "success": False,
            "message": "您的帳戶未啟用高級提取功能。請升級您的計劃。"
        }
    
    await task_manager.update_task_status(task_id, "running", progress=20, 
                                       result=json.dumps({"status": f"正在處理 {len(urls)} 個URL..."}))  
    
    # 高級提取
    await task_manager.update_task_status(task_id, "running", progress=30, 
                                       result=json.dumps({"status": "正在提取詳細信息..."}))  
    
    result = app.state.firecrawl.advanced_extract(
        urls=urls,
        prompt=objective,
        entity=entity
    )
    
    if not result:
        return {
            "success": False,
            "message": "高級提取失敗。請檢查您的URL和目標，或稍後再試。"
        }
    
    await task_manager.update_task_status(task_id, "running", progress=90)
    
    return {
        "success": True,
        "urls": urls,
        "objective": objective,
        "entity": entity,
        "data": result
    }
