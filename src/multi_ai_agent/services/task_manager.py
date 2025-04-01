"""任務管理器."""
import json
import time
import uuid
from typing import Dict, Any, Optional, Tuple


class TaskManager:
    """任務管理器，處理任務的創建和狀態更新."""
    
    def __init__(self, redis_client, connection_manager):
        """初始化任務管理器.
        
        Args:
            redis_client: Redis客戶端
            connection_manager: WebSocket連接管理器
        """
        self.redis = redis_client
        self.ws_manager = connection_manager
        
    async def create_task(self, user_id: str, task_type: str, params: Dict[str, Any], 
                        priority: int = 0) -> Tuple[Optional[str], str]:
        """創建新任務並添加到隊列.
        
        Args:
            user_id: 用戶ID
            task_type: 任務類型
            params: 任務參數
            priority: 任務優先級
            
        Returns:
            (task_id, message): 任務ID和消息
        """
        # 檢查用戶配額
        allowed, message = await self.check_user_task_quota(user_id)
        if not allowed:
            return None, message
            
        # 創建任務
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "progress": 0,
            "user_id": user_id,
            "params": json.dumps(params),
            "created_at": str(time.time()),
            "updated_at": str(time.time()),
            "timeout": "600"  # 10分鐘超時
        }
        
        # 存儲任務數據
        await self.redis.hset(f"task:{task_id}", mapping=task_data)
        
        # 添加到隊列
        await self.redis.zadd(f"tasks:queue:{task_type}", {task_id: priority})
        
        # 添加到用戶活動任務
        await self.redis.sadd(f"user:{user_id}:active_tasks", task_id)
        
        return task_id, "任務已創建"
        
    async def update_task_status(self, task_id: str, status: str, progress: Optional[int] = None, 
                               result: Optional[str] = None, error: Optional[str] = None) -> Tuple[bool, str]:
        """更新任務狀態並通知用戶.
        
        Args:
            task_id: 任務ID
            status: 任務狀態
            progress: 進度(0-100)
            result: 結果
            error: 錯誤信息
            
        Returns:
            (success, message): 成功與否和消息
        """
        # 獲取當前任務數據
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return False, "任務不存在"
            
        # 轉換數據格式
        if isinstance(task_data.get(b'user_id', None), bytes):
            user_id = task_data.get(b'user_id').decode('utf-8')
        else:
            user_id = task_data.get('user_id')
            
        # 更新狀態
        update_data = {
            "status": status,
            "updated_at": str(time.time())
        }
        
        if progress is not None:
            update_data["progress"] = str(progress)
            
        if result is not None:
            update_data["result"] = result
            
        if error is not None:
            update_data["error"] = error
            
        # 更新Redis
        await self.redis.hset(f"task:{task_id}", mapping=update_data)
        
        # 如果任務完成或失敗，從用戶活動任務中移除
        if status in ["completed", "failed", "cancelled"]:
            if user_id:
                await self.redis.srem(f"user:{user_id}:active_tasks", task_id)
                
        # 通知用戶
        if user_id:
            current_progress = update_data.get("progress")
            if current_progress is None:
                if isinstance(task_data.get(b'progress', 0), bytes):
                    current_progress = task_data.get(b'progress', b'0').decode('utf-8')
                else:
                    current_progress = task_data.get('progress', '0')
            
            await self.ws_manager.send_task_update(
                user_id,
                task_id,
                status,
                int(current_progress),
                error,
                result
            )
            
        return True, "任務狀態已更新"
        
    async def cancel_task(self, user_id: str, task_id: str) -> Tuple[bool, str]:
        """取消任務.
        
        Args:
            user_id: 用戶ID
            task_id: 任務ID
            
        Returns:
            (success, message): 成功與否和消息
        """
        # 檢查任務所有權
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return False, "任務不存在"
            
        # 轉換數據格式
        if isinstance(task_data.get(b'user_id', None), bytes):
            task_user_id = task_data.get(b'user_id').decode('utf-8')
        else:
            task_user_id = task_data.get('user_id')
            
        if task_user_id != user_id:
            return False, "無權操作此任務"
            
        # 檢查任務狀態
        if isinstance(task_data.get(b'status', None), bytes):
            status = task_data.get(b'status').decode('utf-8')
        else:
            status = task_data.get('status')
            
        if status in ["completed", "failed", "cancelled"]:
            return False, f"任務已{status}，無法取消"
            
        # 嘗試從隊列中移除
        if isinstance(task_data.get(b'type', None), bytes):
            task_type = task_data.get(b'type').decode('utf-8')
        else:
            task_type = task_data.get('type')
            
        await self.redis.zrem(f"tasks:queue:{task_type}", task_id)
        
        # 更新任務狀態
        await self.update_task_status(task_id, "cancelled", error="用戶取消任務")
        
        return True, "任務已取消"
        
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """獲取任務信息.
        
        Args:
            task_id: 任務ID
            
        Returns:
            任務數據
        """
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return None
            
        # 處理字節格式
        result = {}
        for key, value in task_data.items():
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            if isinstance(value, bytes):
                value = value.decode('utf-8')
                
            # 處理進度為整數
            if key == "progress":
                try:
                    result[key] = int(value)
                except:
                    result[key] = 0
            else:
                result[key] = value
            
        return result
        
    async def check_user_task_quota(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """檢查用戶是否超過任務數量限制.
        
        Args:
            user_id: 用戶ID
            
        Returns:
            (allowed, message): 是否允許和消息
        """
        # 獲取用戶當前活動任務數
        active_task_count = await self.redis.scard(f"user:{user_id}:active_tasks")
        active_task_count = int(active_task_count) if active_task_count else 0
        
        # 從系統中獲取用戶配額
        # 注意：這裡依賴於外部get_user_quota函數，實際使用時需要注入或重構
        from multi_ai_agent.app import get_user_quota
        quota = await get_user_quota(self.redis, user_id)
        max_concurrent_tasks = quota.get("concurrent_tasks", 1)
        
        if active_task_count >= max_concurrent_tasks:
            return False, f"已達到最大並發任務數限制 ({max_concurrent_tasks})"
            
        return True, None
