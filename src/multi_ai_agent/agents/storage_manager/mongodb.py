#!/usr/bin/env python
"""
MongoDB 存儲管理器 (MongoDBStorageManager)

使用 PyMongo 實現的同步 MongoDB 存儲管理器。
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .base import StorageManager

# 檢查 PyMongo 可用性
try:
    import pymongo
    from pymongo import MongoClient
    from bson.objectid import ObjectId
    from gridfs import GridFS
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False


class MongoDBStorageManager(StorageManager):
    """MongoDB 存儲管理器"""
    
    def __init__(self, 
                 mongodb_uri: Optional[str] = None,
                 mongodb_db: str = "research_db", 
                 mongodb_collection: str = "research_reports"):
        """
        初始化 MongoDB 存儲管理器
        
        Args:
            mongodb_uri: MongoDB 連接字串，預設從環境變數 MONGODB_URI 讀取
            mongodb_db: MongoDB 資料庫名稱
            mongodb_collection: MongoDB 集合名稱
        """
        if not MONGODB_AVAILABLE:
            raise ImportError("MongoDB 支援不可用。請安裝 pymongo: pip install pymongo")
            
        # 如果未指定，從環境變數取得 URI
        self.mongodb_uri = mongodb_uri or os.environ.get("MONGODB_URI")
        if not self.mongodb_uri:
            raise ValueError("未指定 MongoDB URI，請在參數中提供或設置 MONGODB_URI 環境變數")
        
        # 連接 MongoDB
        try:
            self.mongo_client = MongoClient(self.mongodb_uri, serverSelectionTimeoutMS=5000)
            # 測試連接
            self.mongo_client.server_info()  # 將測試是否可以連接到伺服器
            print(f"MongoDB 連接成功: {mongodb_db}.{mongodb_collection}")
        except Exception as e:
            raise ConnectionError(f"MongoDB 連接失敗: {str(e)}")
            
        self.mongo_db = self.mongo_client[mongodb_db]
        self.mongo_collection = self.mongo_db[mongodb_collection]
        
        # 初始化 GridFS 用於存儲圖片
        self.gridfs = GridFS(self.mongo_db)
        
        # 確保索引存在
        self.mongo_collection.create_index([("topic", pymongo.TEXT)])
        self.mongo_collection.create_index([("created_at", pymongo.DESCENDING)])
    
    def save_report(self, report_content: str, metadata: Dict[str, Any]) -> str:
        """
        保存報告到 MongoDB
        
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
        
        try:
            # 存入 MongoDB
            print(f"正在將報告存入 MongoDB: {self.mongo_db.name}.{self.mongo_collection.name} (主題: {document['topic']})")
            result = self.mongo_collection.insert_one(document)
            print(f"MongoDB 報告存入成功，內部ID: {result.inserted_id}")
            return report_id
        except Exception as e:
            print(f"MongoDB 存入報告失敗: {str(e)}")
            raise
    
    def save_image(self, image_path: str, metadata: Dict[str, Any]) -> str:
        """
        保存圖片到 MongoDB GridFS
        
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
            # 創建元數據
            image_metadata = {
                "topic": metadata.get("topic", "未知主題"),
                "created_at": datetime.now(),
                "original_path": image_path,
                "filename": os.path.basename(image_path)
            }
            image_metadata.update(metadata)
            
            # 保存到 GridFS
            image_id = self.gridfs.put(f.read(), **image_metadata)
            
        return str(image_id)
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        從 MongoDB 獲取報告
        
        Args:
            report_id: 報告 ID
            
        Returns:
            報告數據
        """
        try:
            report = self.mongo_collection.find_one({"_id": report_id})
            
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
    
    def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        從 MongoDB 列出報告
        
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
            reports = list(self.mongo_collection.find(
                query, 
                {"content": 0}
            ).sort("created_at", pymongo.DESCENDING).limit(limit))
            
            return reports
        except Exception as e:
            print(f"從 MongoDB 列出報告失敗: {str(e)}")
            return []
    
    def get_image(self, image_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        從 GridFS 獲取圖片
        
        Args:
            image_id: 圖片 ID
            
        Returns:
            (圖片數據, 圖片元數據) 的元組
        """
        try:
            grid_out = self.gridfs.get(ObjectId(image_id))
            
            if grid_out:
                metadata = {k: v for k, v in grid_out._file.items() if k != "_id"}
                return (grid_out.read(), metadata)
                
            return None
        except Exception as e:
            print(f"從 GridFS 獲取圖片失敗: {str(e)}")
            return None
