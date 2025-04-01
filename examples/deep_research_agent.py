"""
深度搜尋代理 (DeepResearchAgent)

這個腳本實現了一個先進的搜尋代理，它結合了:
1. ReAct 模式 (Reasoning + Acting)
2. Chain of Thought (思考鏈)
3. 多種搜尋 API 整合
4. 多模態分析能力

用於執行深度研究任務，特別適合調查陌生領域、新名詞或複雜概念。
"""
import os
import sys
import json
import time
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient, ClaudeClient
from src.multi_ai_agent.services.image_search import ImageSearchService

# MongoDB 連接類
try:
    import pymongo
    from pymongo import MongoClient

    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False


class DeepResearchAgent:
    """深度搜尋代理實現"""

    def __init__(self, output_dir: str = "research_results", report_format: str = "html",
                 use_mongodb: bool = False, mongodb_uri: Optional[str] = None,
                 mongodb_db: str = "research_db", mongodb_collection: str = "research_reports"):
        """
        初始化深度搜尋代理
        
        Args:
            output_dir: 研究結果的輸出目錄
            report_format: 報告輸出格式，支援 'html' 或 'markdown'
            use_mongodb: 是否使用 MongoDB 儲存報告
            mongodb_uri: MongoDB 連接字串，預設從環境變數 MONGODB_URI 讀取
            mongodb_db: MongoDB 資料庫名稱
            mongodb_collection: MongoDB 集合名稱
        """
        # 確保輸出目錄存在
        self.output_dir = Path(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # 設置報告格式
        self.report_format = report_format.lower()
        if self.report_format not in ['html', 'markdown']:
            print(f"警告：不支援的報告格式 '{report_format}'，將使用預設的 HTML 格式")
            self.report_format = 'html'

        # MongoDB 設置
        self.use_mongodb = use_mongodb and MONGODB_AVAILABLE
        if self.use_mongodb:
            try:
                # 如果未指定，從環境變數取得 URI
                self.mongodb_uri = mongodb_uri or os.environ.get("MONGODB_URI")
                if not self.mongodb_uri:
                    print("警告：未指定 MongoDB URI，將使用本地儲存")
                    self.use_mongodb = False
                else:
                    # 連接 MongoDB
                    self.mongo_client = MongoClient(self.mongodb_uri)
                    self.mongo_db = self.mongo_client[mongodb_db]
                    self.mongo_collection = self.mongo_db[mongodb_collection]
                    print(f"已連接到 MongoDB，將使用 {mongodb_db}.{mongodb_collection} 儲存研究報告")
            except Exception as e:
                print(f"連接 MongoDB 失敗：{str(e)}，將使用本地儲存")
                self.use_mongodb = False
        elif use_mongodb and not MONGODB_AVAILABLE:
            print("警告：PyMongo 庫未安裝，將使用本地儲存。請安裝 pymongo： pip install pymongo")

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

        storage_type = "MongoDB" if self.use_mongodb else "本地檔案系統"
        print(f"深度搜尋代理初始化完成，將使用 {self.report_format.upper()} 格式產出報告，儲存至{storage_type}")

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
        執行深度研究
        
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
            # 執行簡化的 ReAct 循環研究
            self._perform_react_research(topic, depth, include_images, max_queries)

            # 整合發現
            integrated_findings = self._integrate_findings()
            self.research_state["integrated_findings"] = integrated_findings

            # 生成總結
            summary, follow_up_questions = self._generate_summary_and_questions()
            self.research_state["summary"] = summary
            self.research_state["follow_up_questions"] = follow_up_questions

            # 生成 HTML 報告
            report_path = self._generate_report()
            self.research_state["report_path"] = report_path

            # 紀錄研究完成
            self.research_state["end_time"] = datetime.now().isoformat()
            duration = datetime.fromisoformat(self.research_state["end_time"]) - datetime.fromisoformat(
                self.research_state["start_time"])
            self.research_state["duration"] = str(duration)

            self.log(f"研究完成！結果已儲存到: {report_path}")
            self.log(f"研究耗時: {duration}")

            return self.research_state

        except Exception as e:
            self.log(f"研究過程中發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()

            # 儲存部分結果
            self.research_state["error"] = str(e)
            self.research_state["end_time"] = datetime.now().isoformat()
            self._save_state_to_json()

            return self.research_state
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

    def _perform_react_research(self, topic: str, depth: int, include_images: bool, max_queries: int):
        """執行 ReAct 模式的深度研究循環"""
        self.log("開始使用 ReAct 模式進行研究")

        # 初始 query
        query_count = 0
        current_query = f"{topic} 介紹 定義 概述"
        search_history = []
        findings = []

        # 如果用戶選擇了包含圖片，先評估主題是否需要圖片
        needs_images = False
        if include_images:
            needs_images = self._evaluate_if_topic_needs_images(topic)
            if not needs_images:
                self.log("評估結果：此主題不需要圖片輔助，將跳過圖片搜索")
            else:
                self.log("評估結果：此主題適合使用圖片輔助說明")

        # ReAct 循環 (Reasoning + Acting)
        while query_count < max_queries:
            # 執行搜尋 (Acting)
            self.log(f"搜尋: {current_query}")
            search_result = self.gemini.search_web(current_query)
            query_count += 1

            # 記錄搜尋結果
            search_entry = {
                "query": current_query,
                "result_summary": search_result[:1000] + "..." if len(search_result) > 1000 else search_result,
                "timestamp": datetime.now().isoformat()
            }
            search_history.append(search_entry)
            self.research_state["query_log"].append(search_entry)

            # 處理搜尋結果 (Reasoning)
            reasoning_prompt = f"""
            請分析以下關於「{topic}」的最新搜尋結果:
            
            搜尋查詢: {current_query}
            搜尋結果:
            {search_result}
            
            請提供以下內容:
            1. 提取的重要資訊
            2. 搜尋結果是否充分回答了查詢
            3. 還需要搜尋哪些內容 (提供下一個具體搜尋查詢)
            4. 目前的知識或理解有哪些差距
            
            以JSON格式回應，包含 "findings", "query_satisfied", "next_query", "knowledge_gaps" 欄位。
            """

            # 使用 Claude 分析 (更適合結構化思考)
            reasoning_response = self.claude.generate_text(reasoning_prompt)

            # 解析 JSON 回應
            try:
                # 尋找 JSON 部分
                match = re.search(r'({[\s\S]*})', reasoning_response)
                if match:
                    json_str = match.group(1)
                    reasoning_result = json.loads(json_str)

                    # 添加到發現
                    findings.append({
                        "query": current_query,
                        "findings": reasoning_result.get("findings", "沒有發現重要資訊"),
                        "query_satisfied": reasoning_result.get("query_satisfied", False)
                    })

                    # 決定是否繼續搜尋
                    if reasoning_result.get("query_satisfied", False) and query_count >= depth * 2:
                        self.log("已獲得足夠資訊，停止搜尋")
                        break

                    # 獲取下一個搜尋查詢
                    current_query = reasoning_result.get("next_query", "")
                    if not current_query:
                        # 產生新的搜尋查詢
                        current_query = self._generate_new_query(topic, findings, depth)

                    self.log(f"下一個搜尋: {current_query}")
                else:
                    self.log("無法解析結構化回應，生成新的搜尋查詢")
                    current_query = self._generate_new_query(topic, findings, depth)
            except json.JSONDecodeError:
                self.log("解析 JSON 時出錯，生成新的搜尋查詢")
                current_query = self._generate_new_query(topic, findings, depth)

            # 處理圖片 (如果需要且用戶要求)
            if include_images and needs_images and query_count < max_queries // 2:
                self._search_and_analyze_images(topic, query_count)

        # 儲存研究發現
        self.research_state["findings"] = findings

    def _generate_new_query(self, topic: str, findings: List[Dict[str, Any]], depth: int) -> str:
        """根據已有發現生成新的搜尋查詢"""

        # 彙整目前的發現
        current_findings = "\n".join([f.get("findings", "") for f in findings[-3:]])

        query_prompt = f"""
        我正在研究「{topic}」，已收集到以下資訊：
        
        {current_findings}
        
        根據已有的資訊，請生成一個新的搜尋查詢，以填補知識空白或更深入探討。
        搜尋查詢應該 10 個字以上，但不超過 25 個字，格式為中文。
        
        直接返回搜尋查詢，不要有其他文字。
        """

        try:
            # 使用 Gemini 生成新查詢
            query = self.gemini.generate_text(query_prompt).strip()

            # 簡單驗證
            if len(query) > 100:  # 可能包含了多餘文字
                # 提取第一句話
                first_sentence = query.split('。')[0].strip()
                if 10 <= len(first_sentence) <= 50:
                    return first_sentence
                else:
                    return f"{topic} 進階 探討 分析 {len(findings) + 1}"

            return query
        except Exception:
            # 備用查詢
            return f"{topic} 進階 探討 分析 {len(findings) + 1}"

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

    def _integrate_findings(self) -> str:
        """整合所有研究發現"""
        self.log("整合研究發現...")

        # 彙總所有發現
        all_findings = "\n\n".join([
            f"查詢: {finding.get('query', '')}\n發現: {finding.get('findings', '')}"
            for finding in self.research_state["findings"]
        ])

        # 獲取圖片分析
        image_analyses = ""
        if self.research_state["images"]:
            image_analyses = "\n\n".join([
                f"圖片分析 {i + 1}:\n{img.get('analysis', '')}"
                for i, img in enumerate(self.research_state["images"])
            ])

        # 整合提示
        # 先定義要使用的字符串和變數
        topic = self.research_state["topic"]
        image_section = "圖片分析:\n" + image_analyses if image_analyses else ""

        # 在 f-string 中使用變數
        integration_prompt = f"""
        請整合以下關於「{topic}」的所有研究發現，提供一個全面、有條理的分析：

        研究發現:
        {all_findings}

        {image_section}

        請整合這些資訊，呈現一個連貫且全面的分析。包含以下部分:
        1. 主題概述
        2. 關鍵概念和定義
        3. 主要發現
        4. 重要關聯和洞見
        5. 可靠度評估

        務必去除重複資訊，並以清晰的結構組織內容。
        """

        # 讓 Claude 整合資訊
        integrated_analysis = self.claude.generate_text(integration_prompt)
        return integrated_analysis

    def _generate_summary_and_questions(self) -> Tuple[str, List[str]]:
        """生成研究總結和後續問題"""
        self.log("生成研究總結...")

        # 總結提示
        summary_prompt = f"""
        請根據以下整合分析，為「{self.research_state["topic"]}」研究提供一個簡潔的總結 (500 字以內)，
        以及 5 個有價值的後續研究問題。
        
        整合分析:
        {self.research_state.get("integrated_findings", "")}
        
        總結應該簡明扼要地捕捉研究的核心發現和意義。
        後續問題應該指向值得進一步探索的領域。
        
        以 JSON 格式回應，包含 "summary" 和 "follow_up_questions" (陣列) 欄位。
        """

        # 讓 Gemini 生成總結
        response = self.gemini.generate_text(summary_prompt)

        # 解析 JSON
        try:
            match = re.search(r'({[\s\S]*})', response)
            if match:
                json_str = match.group(1)
                result = json.loads(json_str)
                summary = result.get("summary", "無法生成總結")
                questions = result.get("follow_up_questions", [])
                return summary, questions
            else:
                # 提取總結部分
                summary_match = re.search(r'總結[:：]([\s\S]*?)(?:後續問題|$)', response)
                summary = summary_match.group(1).strip() if summary_match else "無法生成總結"

                # 提取問題
                questions_match = re.findall(r'\d+[\.。\s]+([^\d\n]+)', response)
                questions = questions_match if questions_match else ["無法生成後續問題"]

                return summary, questions
        except Exception:
            # 無法解析，返回原始回應
            return response, ["無法解析後續問題"]

    def _generate_report(self) -> str:
        """生成 HTML 研究報告"""
        self.log("生成 HTML 研究報告...")

        # 創建安全的檔名
        safe_topic = re.sub(r'[^\w\-_]', '_', self.research_state["topic"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"report_{safe_topic}_{timestamp}.html"

        # 圖片 HTML
        images_html = ""
        for i, img in enumerate(self.research_state.get("images", [])):
            img_path = img.get("path", "")
            if os.path.exists(img_path):
                rel_path = os.path.relpath(img_path, start=str(self.output_dir))
                analysis = img.get("analysis", "無分析")
                images_html += f"""
                <div class="image-container">
                    <img src="{rel_path}" alt="{self.research_state["topic"]} 圖片 {i + 1}">
                    <div class="image-analysis">
                        <h4>圖片 {i + 1} 分析</h4>
                        <p>{analysis}</p>
                    </div>
                </div>
                """

        # 生成報告 HTML
        html = f"""<!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>研究報告: {self.research_state["topic"]}</title>
            <style>
                body {{ font-family: 'Microsoft JhengHei', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .header {{ background-color: #f5f7fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .findings {{ margin-bottom: 30px; }}
                .image-container {{ display: flex; margin: 20px 0; border: 1px solid #eee; padding: 15px; border-radius: 5px; }}
                .image-container img {{ max-width: 300px; max-height: 300px; object-fit: contain; margin-right: 20px; }}
                .image-analysis {{ flex: 1; }}
                .follow-up {{ background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin-top: 30px; }}
                .footer {{ margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; color: #7f8c8d; font-size: 0.9em; }}
                pre {{ white-space: pre-wrap; background: #f8f8f8; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>研究報告: {self.research_state["topic"]}</h1>
                <p>研究深度: {self.research_state.get("depth", 3)}/5</p>
                <p>生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>研究耗時: {self.research_state.get("duration", "未知")}</p>
            </div>
            
            <div class="summary">
                <h2>研究總結</h2>
                <p>{self.research_state.get("summary", "無研究總結")}</p>
            </div>
            
            <div class="findings">
                <h2>詳細發現</h2>
                {self.research_state.get("integrated_findings", "無詳細發現")}
            </div>
            
            <div class="images">
                <h2>視覺資料分析</h2>
                {images_html if images_html else "<p>無圖片資料</p>"}
            </div>
            
            <div class="follow-up">
                <h2>後續研究問題</h2>
                <ol>
                    {"".join([f"<li>{q}</li>" for q in self.research_state.get("follow_up_questions", ["無後續研究問題"])])}
                </ol>
            </div>
            
            <div class="footer">
                <p>此報告由多 AI 代理深度搜尋系統自動生成</p>
                <p>免責聲明: 此報告基於網絡搜尋資訊，可能會有不完整或不準確的地方。請自行驗證重要資訊。</p>
            </div>
        </body>
        </html>
        """

        # 寫入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        # 儲存原始研究狀態
        self._save_state_to_json()

        return str(report_path)

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


# 當直接運行這個脚本時的演示程式
if __name__ == "__main__":
    # 載入環境變數
    load_dotenv()

    # 取得命令列參數
    import argparse

    parser = argparse.ArgumentParser(description="深度搜尋代理")
    parser.add_argument("--topic", type=str, required=True, help="研究主題")
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 6), help="研究深度 (1-5)")
    parser.add_argument("--no-images", action="store_true", help="不包含圖片")
    parser.add_argument("--advanced", action="store_true", help="使用進階模型")
    parser.add_argument("--max-queries", type=int, default=10, help="最大搜尋次數")
    parser.add_argument("--output-dir", type=str, default="research_results", help="輸出目錄")
    parser.add_argument("--format", type=str, choices=["html", "markdown"], default="html",
                        help="報告輸出格式 (html 或 markdown)")
    args = parser.parse_args()

    # 初始化代理
    agent = DeepResearchAgent(output_dir=args.output_dir, report_format=args.format)

    # 執行研究
    result = agent.research(
        topic=args.topic,
        depth=args.depth,
        include_images=not args.no_images,
        use_advanced_models=args.advanced,
        max_queries=args.max_queries
    )

    # 顯示結果摘要
    print("\n" + "=" * 60)
    print(f"研究報告已生成: {result.get('report_path', '未知')}")
    print(f"研究耗時: {result.get('duration', '未知')}")
    print("=" * 60)
