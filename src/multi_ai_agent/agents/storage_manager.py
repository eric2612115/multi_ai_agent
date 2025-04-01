#!/usr/bin/env python
"""
存儲管理器 (StorageManager)

這個模組現在是一個轉發模組，導入已移至 storage_manager/ 目錄下的模組結構中。
為了兼容性保留此文件。
"""
import os
import warnings

# 警告用戶這是一個已棄用的導入路徑
warnings.warn(
    "從 'storage_manager' 模組直接導入已被棄用，請改用 'storage_manager/' 包", 
    DeprecationWarning, 
    stacklevel=2
)

# 從包中重新導出所有內容
from .storage_manager.base import StorageManager
from .storage_manager.filesystem import FileSystemStorageManager
from .storage_manager.__init__ import get_storage_manager

# 有條件地導出 MongoDB 相關類
try:
    from .storage_manager.mongodb import MongoDBStorageManager
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

try:
    from .storage_manager.async_mongodb import AsyncMongoDBStorageManager
    from .storage_manager.adapter import AsyncToSyncAdapter
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

# 設置 __all__ 變數控制 from ... import * 行為
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
