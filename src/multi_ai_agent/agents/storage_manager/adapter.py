#!/usr/bin/env python
"""
存儲管理器適配器 (StorageManager Adapter)

提供異步到同步的轉換適配器。
"""
import asyncio
from typing import Dict, Any, List, Optional, Tuple

from .base import StorageManager
from .async_mongodb import AsyncMongoDBStorageManager


class AsyncToSyncAdapter(StorageManager):
    """異步存儲管理器的同步適配器類"""
    
    def __init__(self, async_manager: AsyncMongoDBStorageManager):
        """
        初始化同步適配器
        
        Args:
            async_manager: 異步存儲管理器實例
        """
        self.async_manager = async_manager
    
    def save_report(self, report_content: str, metadata: Dict[str, Any]) -> str:
        """
        同步保存報告
        
        Args:
            report_content: 報告內容
            metadata: 報告元數據
            
        Returns:
            報告 ID
        """
        return self._run_async(self.async_manager.save_report(report_content, metadata))
    
    def save_image(self, image_path: str, metadata: Dict[str, Any]) -> str:
        """
        同步保存圖片
        
        Args:
            image_path: 圖片路徑
            metadata: 圖片元數據
            
        Returns:
            圖片 ID
        """
        return self._run_async(self.async_manager.save_image(image_path, metadata))
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        同步獲取報告
        
        Args:
            report_id: 報告 ID
            
        Returns:
            報告數據
        """
        return self._run_async(self.async_manager.get_report(report_id))
    
    def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        同步列出報告
        
        Args:
            limit: 最大數量
            topic_filter: 主題過濾條件
            
        Returns:
            報告列表
        """
        return self._run_async(self.async_manager.list_reports(limit, topic_filter))
    
    def get_image(self, image_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        同步獲取圖片
        
        Args:
            image_id: 圖片 ID
            
        Returns:
            (圖片數據, 圖片元數據) 的元組
        """
        return self._run_async(self.async_manager.get_image(image_id))
    
    def _run_async(self, coroutine):
        """執行異步方法並返回同步結果"""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()
