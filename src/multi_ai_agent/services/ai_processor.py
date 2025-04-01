"""AI查詢處理函數."""
from typing import Dict, Any, Optional


async def handle_ai_query(app, user_id: str, message_data: Dict[str, Any]) -> Optional[str]:
    """處理來自WebSocket的AI查詢請求.
    
    Args:
        app: FastAPI應用實例
        user_id: 用戶ID
        message_data: 消息數據
        
    Returns:
        任務ID
    """
    # 獲取任務管理器和Redis客戶端
    task_manager = app.state.task_manager
    
    # 獲取查詢類型
    query_type = message_data.get("query_type", "text")
    params = message_data.get("params", {})
    
    # 處理不同類型的查詢
    if query_type == "text":
        # 獲取參數
        prompt = params.get("prompt", "")
        model = params.get("model")
        service = params.get("service")
        max_tokens = params.get("max_tokens")
        conversation_id = params.get("conversation_id")
        
        # 驗證參數
        if not prompt:
            return None
            
        # 創建任務
        task_id, _ = await task_manager.create_task(
            user_id, 
            "generate_text", 
            {
                "prompt": prompt,
                "model": model,
                "service": service,
                "max_tokens": max_tokens,
                "conversation_id": conversation_id
            }
        )
        return task_id
        
    elif query_type == "web_search":
        # 獲取參數
        query = params.get("query", "")
        
        # 驗證參數
        if not query:
            return None
            
        # 創建任務
        task_id, _ = await task_manager.create_task(
            user_id, 
            "search_web", 
            {
                "query": query
            }
        )
        return task_id
        
    elif query_type == "scrape_url":
        # 獲取參數
        url = params.get("url", "")
        formats = params.get("formats", ["markdown"])
        
        # 驗證參數
        if not url:
            return None
            
        # 創建任務
        task_id, _ = await task_manager.create_task(
            user_id, 
            "scrape_url", 
            {
                "url": url,
                "formats": formats
            }
        )
        return task_id
        
    elif query_type == "smart_extract":
        # 獲取參數
        url = params.get("url", "")
        objective = params.get("objective", "")
        use_advanced_model = params.get("use_advanced_model", False)
        
        # 驗證參數
        if not url or not objective:
            return None
            
        # 創建任務
        task_id, _ = await task_manager.create_task(
            user_id, 
            "smart_extract", 
            {
                "url": url,
                "objective": objective,
                "use_advanced_model": use_advanced_model
            }
        )
        return task_id
        
    elif query_type == "advanced_extract":
        # 獲取參數
        urls = params.get("urls", [])
        objective = params.get("objective", "")
        entity = params.get("entity")
        
        # 驗證參數
        if not urls or not objective:
            return None
            
        # 創建任務
        task_id, _ = await task_manager.create_task(
            user_id, 
            "advanced_extract", 
            {
                "urls": urls,
                "objective": objective,
                "entity": entity
            }
        )
        return task_id
    
    return None
