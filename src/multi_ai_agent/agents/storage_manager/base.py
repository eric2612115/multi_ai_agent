#!/usr/bin/env python
"""
存儲管理器基類 (StorageManager Base Class)

定義了存儲管理器的基本接口。
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class StorageManager(ABC):
    """抽象存儲管理器基類"""
    
    @abstractmethod
    def save_report(self, report_content: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        保存報告內容
        
        Args:
            report_content: 報告內容
            metadata: 報告元數據
            
        Returns:
            報告ID或路徑
        """
        pass
    
    @abstractmethod
    def save_image(self, image_path: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        保存圖片
        
        Args:
            image_path: 圖片路徑
            metadata: 圖片元數據
            
        Returns:
            圖片ID或路徑
        """
        pass
    
    @abstractmethod
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取報告
        
        Args:
            report_id: 報告ID
            
        Returns:
            報告數據
        """
        pass
    
    @abstractmethod
    def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出報告
        
        Args:
            limit: 最大數量
            topic_filter: 主題過濾條件
            
        Returns:
            報告列表
        """
        pass
    
    def get_image(self, image_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        獲取圖片
        
        Args:
            image_id: 圖片 ID
            
        Returns:
            (圖片數據, 圖片元數據) 的元組
        """
        # 這是一個可選的方法，子類可以選擇實現它
        raise NotImplementedError("此存儲管理器不支持獲取圖片")
