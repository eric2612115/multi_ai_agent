#!/usr/bin/env python
"""
報告生成器 (Report Generator)

這個模組負責生成並保存研究報告，支持同步和異步存儲。
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any


class ReportGenerator:
    """報告生成與存儲管理類"""
    
    def __init__(self, report_generator, storage_manager, async_mode=False):
        """
        初始化報告生成器
        
        Args:
            report_generator: 報告模板生成器
            storage_manager: 存儲管理器
            async_mode: 是否使用異步模式
        """
        self.report_generator = report_generator
        self.storage_manager = storage_manager
        self.async_mode = async_mode
    
    def generate_and_save_report(self, research_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成報告並存儲
        
        Args:
            research_state: 研究狀態字典
            
        Returns:
            含有報告路徑及存儲ID的結果字典
        """
        # 生成報告
        report_path = self.report_generator.generate_report(research_state)
        result = {"report_path": report_path}
        
        # 如果啟用了存儲管理器，也保存到該存儲系統
        if self.storage_manager:
            try:
                # 讀取報告內容
                with open(report_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                
                # 準備元數據
                metadata = self._prepare_metadata(research_state)
                
                # 當存到MongoDB時顯示詳細信息
                print(f"正在將報告存入存儲系統... (主題: {metadata['topic']}, 格式: {metadata['format']})")
                
                # 根據存儲管理器類型選擇同步或異步保存
                if self.async_mode and asyncio.iscoroutinefunction(self.storage_manager.save_report):
                    # 異步保存
                    report_id = asyncio.run(self.storage_manager.save_report(report_content, metadata))
                else:
                    # 同步保存
                    report_id = self.storage_manager.save_report(report_content, metadata)
                
                if report_id:
                    result["storage_id"] = report_id
                    
                    # 保存關聯的圖片
                    image_ids = self._save_associated_images(research_state, report_id)
                    if image_ids:
                        result["image_ids"] = image_ids
                
                print(f"報告已儲存到存儲系統，ID: {report_id}")
            except Exception as e:
                print(f"儲存報告到存儲系統時出錯: {e}")
                import traceback
                traceback.print_exc()
        
        return result
    
    def _prepare_metadata(self, research_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        準備報告元數據
        
        Args:
            research_state: 研究狀態字典
            
        Returns:
            元數據字典
        """
        return {
            "topic": research_state["topic"],
            "format": research_state.get("format", "html"),
            "summary": research_state.get("summary", ""),
            "depth": research_state.get("depth", 3),
            "duration": research_state.get("duration", ""),
            "has_images": len(research_state.get("images", [])) > 0,
            "follow_up_questions": research_state.get("follow_up_questions", []),
            "created_at": datetime.now().isoformat()
        }
    
    def _save_associated_images(self, research_state: Dict[str, Any], report_id: str) -> list:
        """
        保存關聯的圖片
        
        Args:
            research_state: 研究狀態字典
            report_id: 報告ID
            
        Returns:
            圖片ID列表
        """
        image_ids = []
        
        # 如果有圖片，保存圖片
        for img in research_state.get("images", []):
            img_path = img.get("path", "")
            if os.path.exists(img_path):
                try:
                    img_metadata = {
                        "topic": research_state["topic"],
                        "analysis": img.get("analysis", ""),
                        "query": img.get("query", ""),
                        "report_id": report_id
                    }
                    
                    # 根據存儲管理器類型選擇同步或異步保存
                    if self.async_mode and asyncio.iscoroutinefunction(self.storage_manager.save_image):
                        # 異步保存
                        img_id = asyncio.run(self.storage_manager.save_image(img_path, img_metadata))
                    else:
                        # 同步保存
                        img_id = self.storage_manager.save_image(img_path, img_metadata)
                    
                    if img_id:
                        image_ids.append(img_id)
                except Exception as e:
                    print(f"保存圖片時出錯: {str(e)}")
        
        return image_ids
