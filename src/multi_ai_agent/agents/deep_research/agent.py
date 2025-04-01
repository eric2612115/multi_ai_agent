#!/usr/bin/env python
"""
深度搜尋代理 (DeepResearchAgent)

這個模組包含深度搜尋代理的主要實現。
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from src.multi_ai_agent.agents.base_research_agent import BaseResearchAgent
from src.multi_ai_agent.agents.report_generator import get_report_generator
from src.multi_ai_agent.agents.storage_manager import get_storage_manager, StorageManager

from .research_processor import ResearchProcessor
from .report_generator import ReportGenerator


class DeepResearchAgent(BaseResearchAgent):
    """深度搜尋代理實現"""
    
    def __init__(self, 
                 output_dir: str = "research_results", 
                 report_format: str = "html",
                 storage_type: str = "filesystem",
                 mongodb_uri: Optional[str] = None,
                 mongodb_db: str = "research_db", 
                 mongodb_collection: str = "research_reports",
                 async_mode: bool = False):
        """
        初始化深度搜尋代理
        
        Args:
            output_dir: 研究結果的輸出目錄
            report_format: 報告輸出格式，支援 'html' 或 'markdown'
            storage_type: 存儲類型，支援 'filesystem' 或 'mongodb'
            mongodb_uri: MongoDB 連接字串，預設從環境變數 MONGODB_URI 讀取
            mongodb_db: MongoDB 資料庫名稱
            mongodb_collection: MongoDB 集合名稱
            async_mode: 是否使用異步模式（僅對 MongoDB 有效）
        """
        # 調用父類初始化
        super().__init__(output_dir)
        
        # 報告格式
        self.report_format = report_format.lower()
        if self.report_format not in ['html', 'markdown']:
            print(f"警告：不支援的報告格式 '{report_format}'，將使用預設的 HTML 格式")
            self.report_format = 'html'
        
        # 初始化報告生成器
        self.report_generator = get_report_generator(self.report_format, self.output_dir)
        
        # 異步模式設置
        self.async_mode = async_mode
        
        # 初始化存儲管理器
        self.storage_type = storage_type.lower()
        self.storage_manager = get_storage_manager(
            storage_type=storage_type,
            async_mode=async_mode,
            output_dir=str(self.output_dir),  # 傳遞輸出目錄
            mongodb_uri=mongodb_uri,         # 用於 MongoDB 存儲
            mongodb_db=mongodb_db,
            mongodb_collection=mongodb_collection
        )
        
        # 初始化研究處理器和報告生成器
        self.research_processor = ResearchProcessor(self.gemini, self.claude)
        self.report_gen = ReportGenerator(self.report_generator, self.storage_manager, self.async_mode)
        
        # 存儲描述
        storage_desc = "MongoDB" if self.storage_type == "mongodb" else "本地檔案系統"
        async_desc = "（非阻塞模式）" if async_mode else ""
        print(f"深度搜尋代理初始化完成，將使用 {self.report_format.upper()} 格式產出報告，儲存至{storage_desc}{async_desc}")
    
    def research(
        self, 
        topic: str, 
        depth: int = 3, 
        include_images: bool = True,
        use_advanced_models: bool = False,
        max_queries: int = 10
    ) -> Dict[str, Any]:
        """
        執行深度研究 (同步版本)
        
        Args:
            topic: 研究主題
            depth: 研究深度 (1-5)，越高越深入
            include_images: 是否包含圖片資料
            use_advanced_models: 是否使用更先進的 AI 模型
            max_queries: 最大搜尋查詢次數
            
        Returns:
            研究結果字典
        """
        # 如果是異步模式，使用同步包裝執行
        if self.async_mode:
            return asyncio.run(self.research_async(
                topic, depth, include_images, use_advanced_models, max_queries
            ))
        
        # 否則正常執行同步研究
        return self._research_impl(topic, depth, include_images, use_advanced_models, max_queries)
    
    async def research_async(
        self, 
        topic: str, 
        depth: int = 3, 
        include_images: bool = True,
        use_advanced_models: bool = False,
        max_queries: int = 10
    ) -> Dict[str, Any]:
        """
        執行深度研究 (異步版本)
        
        Args:
            topic: 研究主題
            depth: 研究深度 (1-5)，越高越深入
            include_images: 是否包含圖片資料
            use_advanced_models: 是否使用更先進的 AI 模型
            max_queries: 最大搜尋查詢次數
            
        Returns:
            研究結果字典
        """
        # 檢查是否為異步模式
        if not self.async_mode:
            raise RuntimeError("研究代理非異步模式，請使用 research() 方法或創建帶有 async_mode=True 的實例")
        
        # 執行與同步版本相同的研究過程，但可能使用異步存儲管理器
        return self._research_impl(topic, depth, include_images, use_advanced_models, max_queries)
    
    def _research_impl(
        self, 
        topic: str, 
        depth: int = 3, 
        include_images: bool = True,
        use_advanced_models: bool = False,
        max_queries: int = 10
    ) -> Dict[str, Any]:
        """
        研究實現 (既可同步也可異步調用)
        
        Args:
            topic: 研究主題
            depth: 研究深度 (1-5)，越高越深入
            include_images: 是否包含圖片資料
            use_advanced_models: 是否使用更先進的 AI 模型
            max_queries: 最大搜尋查詢次數
            
        Returns:
            研究結果字典
        """
        # 初始化新的研究
        self.research_state = {
            "topic": topic,
            "start_time": datetime.now().isoformat(),
            "depth": depth,
            "query_log": [],
            "sources": [],
            "findings": [],
            "images": [],
            "key_concepts": {},
            "chain_of_thought": [],
            "log": []
        }
        
        # 紀錄研究起始
        self.log(f"開始研究主題: {topic}")
        self.log(f"研究深度: {depth}")
        self.log(f"包含圖片: {'是' if include_images else '否'}")
        self.log(f"使用進階模型: {'是' if use_advanced_models else '否'}")
        
        # 設置進階模型 (如果需要)
        if use_advanced_models:
            self.gemini.set_model("gemini-2.5-pro-exp-03-25")
            self.claude.set_model("claude-3-opus-20240229")
            self.log("已啟用進階 AI 模型")
        
        try:
            # 執行研究過程
            self.research_processor.perform_research(
                self.research_state, topic, depth, include_images, max_queries, self.log
            )
            
            # 紀錄研究完成
            self.research_state["end_time"] = datetime.now().isoformat()
            duration = datetime.fromisoformat(self.research_state["end_time"]) - datetime.fromisoformat(self.research_state["start_time"])
            self.research_state["duration"] = str(duration)
            
            # 生成報告
            result = self.report_gen.generate_and_save_report(self.research_state)
            result["duration"] = str(duration)
            
            self.log(f"研究完成！結果已儲存")
            self.log(f"研究耗時: {duration}")
            
            return result
            
        except Exception as e:
            self.log(f"研究過程中發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 儲存部分結果
            self.research_state["error"] = str(e)
            self.research_state["end_time"] = datetime.now().isoformat()
            duration = datetime.fromisoformat(self.research_state["end_time"]) - datetime.fromisoformat(self.research_state["start_time"])
            self.research_state["duration"] = str(duration)
            self._save_state_to_json()
            
            # 嘗試保存部分結果到MongoDB
            try:
                if len(self.research_state.get("findings", [])) > 0:
                    # 產生一些簡單的總結
                    if "summary" not in self.research_state:
                        findings_text = "\n".join([f.get("findings", "") for f in self.research_state["findings"]])
                        self.research_state["summary"] = f"部分研究結果 (因錯誤中斷): {findings_text[:200]}..."
                    
                    # 使用報告生成器存儲部分結果
                    self.log("嘗試保存部分研究結果到存儲系統")
                    partial_result = self.report_gen.generate_and_save_report(self.research_state)
                    
                    # 合併錯誤信息和存儲結果
                    return {"error": str(e), "partial_result": partial_result}
            except Exception as save_error:
                self.log(f"保存部分結果時出錯: {str(save_error)}")
            
            return {"error": str(e)}
        finally:
            # 恢復預設模型
            if use_advanced_models:
                self.gemini.set_model("gemini-2.0-flash")
                self.claude.set_model("claude-3-5-sonnet-20240620")

    def list_reports(self, limit: int = 10, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出存儲的報告
        
        Args:
            limit: 最大回傳數量
            topic_filter: 主題過濾條件
            
        Returns:
            報告列表
        """
        if hasattr(self, 'storage_manager'):
            try:
                if self.async_mode and asyncio.iscoroutinefunction(self.storage_manager.list_reports):
                    return asyncio.run(self.storage_manager.list_reports(limit, topic_filter))
                else:
                    return self.storage_manager.list_reports(limit, topic_filter)
            except Exception as e:
                self.log(f"列出報告時出錯: {str(e)}")
                return []
        return []
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取報告
        
        Args:
            report_id: 報告 ID
            
        Returns:
            報告數據
        """
        if hasattr(self, 'storage_manager'):
            try:
                if self.async_mode and asyncio.iscoroutinefunction(self.storage_manager.get_report):
                    return asyncio.run(self.storage_manager.get_report(report_id))
                else:
                    return self.storage_manager.get_report(report_id)
            except Exception as e:
                self.log(f"獲取報告時出錯: {str(e)}")
                return None
        return None
