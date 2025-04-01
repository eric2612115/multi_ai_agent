#!/usr/bin/env python
"""
基礎研究代理 (BaseResearchAgent)

這個模組定義了研究代理的基礎類別，可被繼承以提供不同的實現。
"""
import os
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient, ClaudeClient
from src.multi_ai_agent.services.image_search import ImageSearchService

class BaseResearchAgent:
    """研究代理的基礎類別，提供共用功能"""
    
    def __init__(self, output_dir: str = "research_results"):
        """
        初始化基礎研究代理
        
        Args:
            output_dir: 研究結果的輸出目錄
        """
        # 確保輸出目錄存在
        self.output_dir = Path(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化服務客戶端
        print("正在初始化 AI 服務客戶端...")
        self.gemini = GeminiClient()
        self.claude = ClaudeClient()
        self.firecrawl = FirecrawlClient(logger=self.log)
        
        # 設置智能提取服務
        self.firecrawl.set_extraction_service(gemini_client=self.gemini)
        
        # 初始化圖片搜尋服務
        self.image_search = ImageSearchService(
            download_folder=str(self.output_dir / "images"),
            search_api_key=os.environ.get("SERP_API_KEY"),
            logger=self.log
        )
        
        # 研究狀態
        self.research_state = {
            "topic": "",
            "query_log": [],
            "sources": [],
            "findings": [],
            "images": [],
            "key_concepts": {},
            "chain_of_thought": []
        }
        
        print("研究代理初始化完成")
        
    def log(self, message: str):
        """記錄訊息到控制台和研究日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        if hasattr(self, 'research_state'):
            if 'log' not in self.research_state:
                self.research_state['log'] = []
            self.research_state['log'].append(f"[{timestamp}] {message}")
    
    def research(
        self, 
        topic: str, 
        depth: int = 3, 
        include_images: bool = True,
        use_advanced_models: bool = False,
        max_queries: int = 10
    ) -> Dict[str, Any]:
        """
        執行深度研究 (基礎方法，需要被子類覆寫)
        
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
            # 這個方法應該被子類覆寫
            self.log("警告：基礎研究方法被調用，但未實現。這個方法應該被子類覆寫。")
            
            return self.research_state
            
        except Exception as e:
            self.log(f"研究過程中發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 儲存部分結果
            self.research_state["error"] = str(e)
            self.research_state["end_time"] = datetime.now().isoformat()
            self._save_state_to_json()
            
            return {"error": str(e)}
        finally:
            # 恢復預設模型
            if use_advanced_models:
                self.gemini.set_model("gemini-2.0-flash")
                self.claude.set_model("claude-3-5-sonnet-20240620")
    
    def _evaluate_if_topic_needs_images(self, topic: str) -> bool:
        """評估研究主題是否適合使用圖片
        
        Args:
            topic: 研究主題
            
        Returns:
            表示主題是否適合使用圖片的布林值
        """
        # 使用 Gemini 評估主題是否需要視覺輔助
        prompt = f"""
        評估主題「{topic}」是否適合使用視覺輔助資料（圖片）。
        考慮此主題是否：
        1. 涉及實體物件、地點或外觀
        2. 包含視覺概念（設計、藝術等）
        3. 使用圖表或插圖能更容易理解
        4. 是否主要為抽象或理論性質
        
        只回答「是」或「否」。
        """
        
        try:
            response = self.gemini.generate_text(prompt).strip().lower()
            # 檢查回應是否包含「是」
            return '是' in response or 'yes' in response
        except Exception as e:
            self.log(f"評估主題是否需要圖片時出錯: {str(e)}")
            # 如果評估失敗，預設為使用圖片
            return True
    
    def _search_and_analyze_images(self, topic: str, query_index: int):
        """搜尋和分析與主題相關的圖片"""
        if query_index == 0:
            # 第一次搜尋
            image_query = f"{topic} 圖片 示意圖"
        else:
            # 後續搜尋
            image_query = f"{topic} {query_index + 1} 圖表 範例"
        
        self.log(f"搜尋相關圖片: {image_query}")
        
        try:
            # 搜尋並下載圖片
            image_paths = self.image_search.search_and_download_image(
                query=image_query,
                max_results=1,
                safe_search=True
            )
            
            if not image_paths:
                self.log("未找到相關圖片")
                return
            
            # 分析圖片
            image_path = image_paths[0]
            self.log(f"分析圖片: {image_path}")
            
            # 使用 Gemini 進行圖片分析
            try:
                # 暫時切換到支援圖片的模型
                original_model = self.gemini.model
                self.gemini.set_model("gemini-2.0-pro-vision")
                
                # 分析圖片
                analysis = self.gemini.client.models.generate_content(
                    model=self.gemini.model,
                    contents=[
                        f"分析這張關於「{topic}」的圖片，說明其中內容及與主題的關聯性",
                        self.gemini.genai.types.Part.from_uri(
                            file_uri=f"file://{image_path}", 
                            mime_type="image/jpeg"
                        )
                    ]
                ).text
                
                # 恢復原來的模型
                self.gemini.set_model(original_model)
                
                # 添加到研究結果
                self.research_state["images"].append({
                    "path": image_path,
                    "query": image_query,
                    "analysis": analysis
                })
                
                self.log("圖片分析完成")
            except Exception as e:
                self.log(f"圖片分析出錯: {str(e)}")
                # 恢復原來的模型
                self.gemini.set_model(original_model)
        except Exception as e:
            self.log(f"圖片搜尋出錯: {str(e)}")
            
    def _save_state_to_json(self) -> str:
        """儲存研究狀態到 JSON 檔案"""
        # 創建安全的檔名
        safe_topic = re.sub(r'[^\w\-_]', '_', self.research_state["topic"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.output_dir / f"research_data_{safe_topic}_{timestamp}.json"
        
        # 複製研究狀態 (不包括可能難以序列化的物件)
        state_copy = {k: v for k, v in self.research_state.items()}
        
        # 修正圖片路徑以使用相對路徑
        if "images" in state_copy:
            for img in state_copy["images"]:
                if "path" in img and os.path.exists(img["path"]):
                    img["path"] = os.path.relpath(img["path"], start=str(self.output_dir))
        
        # 儲存到 JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(state_copy, f, ensure_ascii=False, indent=2)
        
        return str(json_path)
