#!/usr/bin/env python
"""
存儲管理器模組 (Storage Manager Module)

提供不同的存儲後端，用於保存研究報告及相關數據。
"""
import os
from typing import Optional, Dict, Any

from .base import StorageManager
from .filesystem import FileSystemStorageManager

# 檢查 pymongo 和 motor 可用性
try:
    import pymongo
    from .mongodb import MongoDBStorageManager
    MONGODB_AVAILABLE = True
    print(f"成功檢測到 PyMongo 版本: {pymongo.__version__}")
except ImportError as e:
    MONGODB_AVAILABLE = False
    print(f"無法載入 PyMongo: {str(e)}\n若要使用MongoDB功能，請執行: pip install pymongo")

try:
    import motor.motor_asyncio
    from .async_mongodb import AsyncMongoDBStorageManager
    from .adapter import AsyncToSyncAdapter
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False


def get_storage_manager(storage_type: str, async_mode: bool = False, **kwargs) -> StorageManager:
    """
    獲取存儲管理器實例
    
    Args:
        storage_type: 存儲類型 ('mongodb', 'mongodb_async' 或 'filesystem')
        async_mode: 是否使用異步模式（僅對 MongoDB 有效）
        **kwargs: 傳遞給存儲管理器的其他參數
        
    Returns:
        存儲管理器實例
        
    Raises:
        ImportError: 當請求的存儲類型需要的依賴未安裝時
        ConnectionError: 當無法連接到 MongoDB 時
        ValueError: 當提供的存儲類型無效時
    """
    storage_type = storage_type.lower()
    
    # MongoDB 異步模式
    if (storage_type == 'mongodb_async' or (storage_type == 'mongodb' and async_mode)):
        # 檢查是否安裝了異步MongoDB依賴
        if not MOTOR_AVAILABLE:
            raise ImportError("無法使用異步MongoDB存儲。請安裝必要依賴: pip install motor")
            
        # 嘗試連接
        async_mongo_kwargs = {
            k: v for k, v in kwargs.items() 
            if k in ['mongodb_uri', 'mongodb_db', 'mongodb_collection']
        }
        print("使用異步 MongoDB 存儲管理器")
        async_manager = AsyncMongoDBStorageManager(**async_mongo_kwargs)
        if async_mode:
            # 直接返回異步管理器
            return async_manager
        else:
            # 返回同步適配器包裝的異步管理器
            print("包裝為同步接口")
            return AsyncToSyncAdapter(async_manager)
    
    # MongoDB 同步模式
    if storage_type == 'mongodb':
        # 檢查是否安裝了PyMongo
        if not MONGODB_AVAILABLE:
            raise ImportError("無法使用MongoDB存儲。請安裝必要依賴: pip install pymongo")
            
        # 顯示更詳細的連接訊息
        mongodb_uri = kwargs.get('mongodb_uri') or os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
        mongodb_db = kwargs.get('mongodb_db', 'research_db')
        mongodb_collection = kwargs.get('mongodb_collection', 'research_reports')
        print(f"嘗試連接到 MongoDB: {mongodb_uri} (數據庫: {mongodb_db}, 集合: {mongodb_collection})")
        
        # 嘗試連接測試
        try:
            client = pymongo.MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            client.server_info()  # 測試連接
            print("使用同步 MongoDB 存儲管理器 - 連接測試成功")
            
            # 過濾參數，只保留 MongoDBStorageManager 支援的參數
            mongo_kwargs = {
                k: v for k, v in kwargs.items() 
                if k in ['mongodb_uri', 'mongodb_db', 'mongodb_collection']
            }
            return MongoDBStorageManager(**mongo_kwargs)
        except Exception as e:
            # 如果要求使用MongoDB但無法連接，應該失敗而不是回退
            raise ConnectionError(f"無法連接到MongoDB服務器: {e}\n請確認服務器已啟動並可以連接")
    
    # 文件系統模式
    if storage_type == 'filesystem':
        # 移除 MongoDB 特定的參數
        fs_kwargs = {k: v for k, v in kwargs.items() 
                    if k not in ['mongodb_uri', 'mongodb_db', 'mongodb_collection']}
        print("使用文件系統存儲管理器")
        return FileSystemStorageManager(**fs_kwargs)
    
    # 無效的存儲類型
    raise ValueError(f"無效的存儲管理器類型: '{storage_type}'。支援的類型為: 'mongodb', 'mongodb_async', 'filesystem'")


# 導出主要類和函數
__all__ = [
    'StorageManager',
    'FileSystemStorageManager',
    'get_storage_manager',
]

# 根據可用性添加導出
if MONGODB_AVAILABLE:
    __all__.append('MongoDBStorageManager')
if MOTOR_AVAILABLE:
    __all__.extend(['AsyncMongoDBStorageManager', 'AsyncToSyncAdapter'])
