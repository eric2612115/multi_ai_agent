#!/usr/bin/env python
"""
異步 MongoDB 存儲管理器 (AsyncMongoDBStorageManager)

使用 motor 實現非阻塞的 MongoDB 存儲管理器。
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .base import StorageManager

# 檢查 Motor 可用性
try:
    import motor.motor_asyncio
    from bson.objectid import ObjectId
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False


class AsyncMongoDBStorageManager(StorageManager):
    """MongoDB 存儲管理器（非阻塞版本）"""
    
    def __init__(self, 
                 mongodb_uri: Optional[str] = None,
                 mongodb_db: str = "research_db", 
                 mongodb_collection: str = "research_reports",
                 **kwargs):
        """
        初始化 MongoDB 存儲管理器（非阻塞版本）
        
        Args:
            mongodb_uri: MongoDB 連接字串，預設從環境變數 MONGODB_URI 讀取
            mongodb_db: MongoDB 資料庫名稱
            mongodb_collection: MongoDB 集合名稱
            **kwargs: 其他參數
        """
        if not MOTOR_AVAILABLE:
            raise ImportError("Motor 支援不可用。請安裝 motor: pip install motor")
            
        # 如果未指定，從環境變數取得 URI
        self.mongodb_uri = mongodb_uri or os.environ.get("MONGODB_URI")
        if not self.mongodb_uri:
            raise ValueError("未指定 MongoDB URI，請在參數中提供或設置 MONGODB_URI 環境變數")
        
        # 連接 MongoDB
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(self.mongodb_uri)
        self.mongo_db = self.mongo_client[mongodb_db]
        self.mongo_collection = self.mongo_db[mongodb_collection]
        
        # 初始化 GridFS 用於存儲圖片
        self.gridfs_bucket = motor.motor_asyncio.AsyncIOMotorGridFSBucket(self.mongo_db)
    
    async def save_report(self, report_content: str, metadata: Dict[str, Any]) -> str:
        """
        保存報告到 MongoDB（非阻塞版本）
        
        Args:
            report_content: 報告內容
            metadata: 報告元數據
            
        Returns:
            報告 ID
        """
        # 創建資料文件
        report_id = str(uuid.uuid4())
        now = datetime.now()
        
        # 準備資料文件
        document = {
            "_id": report_id,
            "topic": metadata.get("topic", "未知主題"),
            "format": metadata.get("format", "html"),
            "content": report_content,
            "summary": metadata.get("summary", ""),
            "created_at": now,
            "depth": metadata.get("depth", 3),
            "duration": metadata.get("duration", ""),
            "status": "completed"
        }
        
        # 添加其他元數據
        document.update({k: v for k, v in metadata.items() if k not in document})
        
        # 存入 MongoDB
        await self.mongo_collection.insert_one(document)
        
        return report_id
    
    async def save_image(self, image_path: str, metadata: Dict[str, Any]) -> str:
        """
        保存圖片到 MongoDB GridFS（非阻塞版本）
        
        Args:
            image_path: 圖片路徑
            metadata: 圖片元數據
            
        Returns:
            圖片 ID
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"圖片文件不存在: {image_path}")
        
        # 讀取圖片文件
        with open(image_path, "rb") as f:
            content = f.read()
            
        # 創建元數據
        image_metadata = {
            "topic": metadata.get("topic", "未知主題"),
            "created_at": datetime.now(),
            "original_path": image_path,
            "filename": os.path.basename(image_path)
        }
        image_metadata.update(metadata)
        
        # 保存到 GridFS
        file_id = await self.gridfs_bucket.upload_from_stream(
            filename=os.path.basename(image_path),
            source=content,
            metadata=image_metadata
        )
        
        return str(file_id)
    
    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        從 MongoDB 獲取報告（非阻塞版本）
        
        Args:
            report_id: 報告 ID
            
        Returns:
            報告數據
        """
        try:
            report = await self.mongo_collection.find_one({"_id": report_id})
            
            if report:
                # 分離內容和元數據
                content = report.pop("content", "")
                return {
                    "content": content,
                    "metadata": report
                }
                
            return None
        except Exception as e:
            print(f"從 MongoDB 獲取報告失敗: {str(e)}")
            return None
    
    async def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        從 MongoDB 列出報告（非阻塞版本）
        
        Args:
            limit: 最大數量
            topic_filter: 主題過濾條件
            
        Returns:
            報告列表
        """
        try:
            query = {}
            if topic_filter:
                query["topic"] = {"$regex": topic_filter, "$options": "i"}
                
            # 只回傳必要欄位，不包含內容（內容可能很大）
            cursor = self.mongo_collection.find(
                query, 
                {"content": 0}
            ).sort("created_at", -1).limit(limit)
            
            reports = await cursor.to_list(length=limit)
            return reports
            
        except Exception as e:
            print(f"從 MongoDB 列出報告失敗: {str(e)}")
            return []
    
    async def get_image(self, image_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        從 GridFS 獲取圖片（非阻塞版本）
        
        Args:
            image_id: 圖片 ID
            
        Returns:
            (圖片數據, 圖片元數據) 的元組
        """
        try:
            file_id = ObjectId(image_id)
            
            # 獲取圖片元數據
            grid_out = await self.gridfs_bucket.open_download_stream(file_id)
            metadata = grid_out.metadata or {}
            
            # 讀取圖片內容
            chunks = []
            while True:
                chunk = await grid_out.read(16384)  # 16KB 區塊
                if not chunk:
                    break
                chunks.append(chunk)
                
            return (b''.join(chunks), metadata)
                
        except Exception as e:
            print(f"從 GridFS 獲取圖片失敗: {str(e)}")
            return None
