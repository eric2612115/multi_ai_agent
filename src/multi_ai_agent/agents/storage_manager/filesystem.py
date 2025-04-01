#!/usr/bin/env python
"""
文件系統存儲管理器 (FileSystemStorageManager)

使用本地文件系統存儲報告和圖片。
"""
import os
import uuid
import json
import glob
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import StorageManager


class FileSystemStorageManager(StorageManager):
    """文件系統存儲管理器"""
    
    def __init__(self, base_dir: str = "research_results", output_dir: Optional[str] = None):
        """
        初始化文件系統存儲管理器
        
        Args:
            base_dir: 基礎目錄
            output_dir: 輸出目錄（如果指定，則優先使用）
        """
        # 若指定了 output_dir，則使用它
        self.base_dir = Path(output_dir if output_dir else base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        self.reports_dir = self.base_dir / "reports"
        os.makedirs(self.reports_dir, exist_ok=True)
        self.images_dir = self.base_dir / "images"
        os.makedirs(self.images_dir, exist_ok=True)
        self.metadata_dir = self.base_dir / "metadata"
        os.makedirs(self.metadata_dir, exist_ok=True)
    
    def save_report(self, report_content: str, metadata: Dict[str, Any]) -> str:
        """
        保存報告到文件系統
        
        Args:
            report_content: 報告內容
            metadata: 報告元數據
            
        Returns:
            報告文件路徑
        """
        report_id = str(uuid.uuid4())
        topic = metadata.get("topic", "未知主題")
        safe_topic = "".join(c if c.isalnum() or c in "-_" else "_" for c in topic)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        format_ext = "md" if metadata.get("format", "html").lower() == "markdown" else "html"
        
        # 保存報告文件
        file_name = f"report_{safe_topic}_{timestamp}_{report_id[:8]}.{format_ext}"
        file_path = self.reports_dir / file_name
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        # 保存元數據
        metadata["report_id"] = report_id
        metadata["file_path"] = str(file_path)
        metadata["created_at"] = datetime.now().isoformat()
        
        metadata_path = self.metadata_dir / f"{report_id}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        return str(file_path)
    
    def save_image(self, image_path: str, metadata: Dict[str, Any]) -> str:
        """
        保存圖片到文件系統 (實際上只是返回原路徑，因為圖片已經在文件系統中)
        
        Args:
            image_path: 圖片路徑
            metadata: 圖片元數據
            
        Returns:
            圖片路徑
        """
        return image_path
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取報告
        
        Args:
            report_id: 報告ID或路徑
            
        Returns:
            報告數據
        """
        # 嘗試直接載入路徑
        if os.path.exists(report_id):
            file_path = report_id
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 嘗試找到對應的元數據
            metadata_path = self.metadata_dir / f"{os.path.basename(file_path).split('_')[-1].split('.')[0]}.json"
            
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                metadata = {
                    "topic": "未知主題",
                    "format": "html" if file_path.endswith(".html") else "markdown",
                    "created_at": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                }
                
            return {
                "content": content,
                "metadata": metadata
            }
        
        # 嘗試從元數據中找到文件
        metadata_path = self.metadata_dir / f"{report_id}.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            file_path = metadata.get("file_path")
            if file_path and os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                return {
                    "content": content,
                    "metadata": metadata
                }
                
        return None
    
    def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出報告
        
        Args:
            limit: 最大數量
            topic_filter: 主題過濾條件
            
        Returns:
            報告列表
        """
        result = []
        
        # 列出元數據目錄中的所有元數據文件
        if os.path.exists(self.metadata_dir):
            metadata_files = glob.glob(str(self.metadata_dir / "*.json"))
            metadata_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            for file_path in metadata_files[:limit]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    
                    # 過濾主題
                    if topic_filter and topic_filter.lower() not in metadata.get("topic", "").lower():
                        continue
                    
                    result.append(metadata)
                except Exception as e:
                    print(f"Error loading metadata file {file_path}: {e}")
                    
                if len(result) >= limit:
                    break
        
        return result
