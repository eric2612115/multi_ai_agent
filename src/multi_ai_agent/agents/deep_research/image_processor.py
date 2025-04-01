#!/usr/bin/env python
"""
圖片處理模塊 (Image Processor)

這個模組包含圖片評估、搜索和分析的相關功能。
"""
from typing import Dict, Any


def evaluate_need_for_images(gemini_model, topic: str) -> bool:
    """
    評估主題是否需要圖片輔助
    
    Args:
        gemini_model: Gemini 模型客戶端
        topic: 研究主題
        
    Returns:
        是否需要圖片
    """
    prompt = f"""
    請評估主題「{topic}」是否適合使用圖片輔助說明或解釋。
    
    考慮以下因素:
    1. 主題是否涉及視覺化內容（如藝術、設計、地理、建築等）
    2. 主題是否包含複雜概念，能通過圖表或示意圖更好理解
    3. 主題是否有標誌性的圖像或視覺表現
    4. 主題是否涉及實體物體或可視化的現象
    
    只回答 "是" 或 "否"，不要有其他文字。
    """
    
    try:
        response = gemini_model.generate_text(prompt).strip().lower()
        return "是" in response or "yes" in response or "true" in response
    except Exception:
        # 發生錯誤時，預設不使用圖片
        return False


def search_and_analyze_images(gemini_model, research_state: Dict[str, Any], topic: str, query_index: int):
    """
    搜索並分析與主題相關的圖片
    
    Args:
        gemini_model: Gemini 模型客戶端
        research_state: 研究狀態字典
        topic: 研究主題
        query_index: 查詢索引
    """
    # 這裡應實現圖片搜索和分析邏輯
    # 由於 API 限制或其他原因，這裡僅提供一個示例框架
    
    # 模擬圖片搜索結果
    image_entry = {
        "query": f"{topic} 圖片",
        "path": f"[圖片路徑將在實際實現中替換]",
        "analysis": f"[此處將包含圖片分析，由 Gemini 生成]"
    }
    
    # 添加圖片到研究狀態
    if "images" not in research_state:
        research_state["images"] = []
    
    research_state["images"].append(image_entry)
