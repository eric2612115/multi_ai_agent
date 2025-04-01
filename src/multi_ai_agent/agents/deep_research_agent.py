#!/usr/bin/env python
"""
深度搜尋代理 (DeepResearchAgent)

這個模組已經重構並移至 deep_research/ 目錄下。
此文件僅為向後兼容性保留，從 deep_research 包中重新導出 DeepResearchAgent 類。
"""
import warnings

# 警告用戶這是一個已棄用的導入路徑
warnings.warn(
    "從 'deep_research_agent' 模組直接導入已被棄用，請改用 'deep_research' 包", 
    DeprecationWarning, 
    stacklevel=2
)

# 從新的包導入
from .deep_research.agent import DeepResearchAgent

# 設置 __all__ 變數控制 from ... import * 行為
__all__ = ['DeepResearchAgent']
