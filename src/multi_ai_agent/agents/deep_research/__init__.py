#!/usr/bin/env python
"""
深度搜尋代理模組 (Deep Research Agent Module)

這個模組實現了一個先進的搜尋代理，它結合了:
1. ReAct 模式 (Reasoning + Acting)
2. Chain of Thought (思考鏈)
3. 多種搜尋 API 整合
4. 多模態分析能力
5. 多種格式的報告生成
6. 多種後端的儲存支持

用於執行深度研究任務，特別適合調查陌生領域、新名詞或複雜概念。
"""

from .agent import DeepResearchAgent

__all__ = ['DeepResearchAgent']
