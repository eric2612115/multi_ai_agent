#!/usr/bin/env python
"""
研究處理器 (ResearchProcessor)

這個模組包含深度研究的核心處理邏輯，包括 ReAct 循環、知識整合等功能。
"""
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable

from .image_processor import evaluate_need_for_images, search_and_analyze_images


class ResearchProcessor:
    """研究處理器，實現研究的核心邏輯"""
    
    def __init__(self, gemini_model, claude_model):
        """
        初始化研究處理器
        
        Args:
            gemini_model: Gemini 模型客戶端
            claude_model: Claude 模型客戶端
        """
        self.gemini = gemini_model
        self.claude = claude_model
    
    def perform_research(
        self, 
        research_state: Dict[str, Any], 
        topic: str, 
        depth: int, 
        include_images: bool, 
        max_queries: int,
        log_func: Callable[[str], None]
    ):
        """
        執行 ReAct 模式的深度研究
        
        Args:
            research_state: 研究狀態字典
            topic: 研究主題
            depth: 研究深度 (1-5)
            include_images: 是否包含圖片
            max_queries: 最大查詢次數
            log_func: 日誌記錄函數
        """
        log_func("開始使用 ReAct 模式進行研究")
        
        # 初始 query
        query_count = 0
        current_query = f"{topic} 介紹 定義 概述"
        search_history = []
        findings = []
        
        # 如果用戶選擇了包含圖片，先評估主題是否需要圖片
        needs_images = False
        if include_images:
            needs_images = evaluate_need_for_images(self.gemini, topic)
            if not needs_images:
                log_func("評估結果：此主題不需要圖片輔助，將跳過圖片搜索")
            else:
                log_func("評估結果：此主題適合使用圖片輔助說明")
        
        # ReAct 循環 (Reasoning + Acting)
        while query_count < max_queries:
            # 執行搜尋 (Acting)
            log_func(f"搜尋: {current_query}")
            search_result = self.gemini.search_web(current_query)
            query_count += 1
            
            # 記錄搜尋結果
            search_entry = {
                "query": current_query,
                "result_summary": search_result[:1000] + "..." if len(search_result) > 1000 else search_result,
                "timestamp": datetime.now().isoformat()
            }
            search_history.append(search_entry)
            research_state["query_log"].append(search_entry)
            
            # 處理搜尋結果 (Reasoning)
            reasoning_response = self._analyze_search_result(topic, current_query, search_result)
            
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
                        log_func("已獲得足夠資訊，停止搜尋")
                        break
                    
                    # 獲取下一個搜尋查詢
                    current_query = reasoning_result.get("next_query", "")
                    if not current_query:
                        # 產生新的搜尋查詢
                        current_query = self._generate_new_query(topic, findings, depth)
                    
                    log_func(f"下一個搜尋: {current_query}")
                else:
                    log_func("無法解析結構化回應，生成新的搜尋查詢")
                    current_query = self._generate_new_query(topic, findings, depth)
            except json.JSONDecodeError:
                log_func("解析 JSON 時出錯，生成新的搜尋查詢")
                current_query = self._generate_new_query(topic, findings, depth)
            
            # 處理圖片 (如果需要且用戶要求)
            if include_images and needs_images and query_count < max_queries // 2:
                search_and_analyze_images(self.gemini, research_state, topic, query_count)
        
        # 儲存研究發現
        research_state["findings"] = findings
        
        # 整合發現和生成總結
        integrated_findings = self._integrate_findings(research_state, topic)
        research_state["integrated_findings"] = integrated_findings
        
        summary, follow_up_questions = self._generate_summary_and_questions(research_state)
        research_state["summary"] = summary
        research_state["follow_up_questions"] = follow_up_questions

    def _analyze_search_result(self, topic: str, query: str, search_result: str) -> str:
        """
        分析搜索結果
        
        Args:
            topic: 研究主題
            query: 搜索查詢
            search_result: 搜索結果
            
        Returns:
            分析結果
        """
        reasoning_prompt = f"""
        請分析以下關於「{topic}」的最新搜尋結果:
        
        搜尋查詢: {query}
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
        return self.claude.generate_text(reasoning_prompt)
    
    def _generate_new_query(self, topic: str, findings: List[Dict[str, Any]], depth: int) -> str:
        """
        生成新的搜尋查詢
        
        Args:
            topic: 研究主題
            findings: 目前的發現列表
            depth: 研究深度
            
        Returns:
            下一個搜尋查詢
        """
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
    
    def _integrate_findings(self, research_state: Dict[str, Any], topic: str) -> str:
        """
        整合所有研究發現
        
        Args:
            research_state: 研究狀態字典
            topic: 研究主題
            
        Returns:
            整合後的分析結果
        """
        # 彙總所有發現
        all_findings = "\n\n".join([
            f"查詢: {finding.get('query', '')}\n發現: {finding.get('findings', '')}"
            for finding in research_state["findings"]
        ])
        
        # 獲取圖片分析
        image_analyses = ""
        if research_state["images"]:
            image_analyses = "\n\n".join([
                f"圖片分析 {i+1}:\n{img.get('analysis', '')}"
                for i, img in enumerate(research_state["images"])
            ])
        
        # 整合提示
        image_section = "圖片分析:\n" + image_analyses if image_analyses else ""

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
        return self.claude.generate_text(integration_prompt)
    
    def _generate_summary_and_questions(self, research_state: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        生成研究總結和後續問題
        
        Args:
            research_state: 研究狀態字典
            
        Returns:
            (總結, 後續問題清單)
        """
        # 總結提示
        topic = research_state["topic"]
        summary_prompt = f"""
        請根據以下整合分析，為「{topic}」研究提供一個簡潔的總結 (500 字以內)，
        以及 5 個有價值的後續研究問題。
        
        整合分析:
        {research_state.get("integrated_findings", "")}
        
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
