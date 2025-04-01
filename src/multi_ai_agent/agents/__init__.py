"""
多 AI 代理模組

這個包提供多種 AI 代理實現，支持不同類型的任務和功能。
"""

from src.multi_ai_agent.agents.base_research_agent import BaseResearchAgent
from src.multi_ai_agent.agents.deep_research_agent import DeepResearchAgent
from src.multi_ai_agent.agents.storage_manager import (
    StorageManager, 
    FileSystemStorageManager, 
    get_storage_manager
)

# 有條件地從 storage_manager 導入 MongoDB 相關類
try:
    from src.multi_ai_agent.agents.storage_manager import MongoDBStorageManager
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    
try:
    from src.multi_ai_agent.agents.storage_manager import AsyncMongoDBStorageManager, AsyncToSyncAdapter
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

from src.multi_ai_agent.agents.report_generator import (
    BaseReportGenerator, 
    MarkdownReportGenerator, 
    HtmlReportGenerator, 
    get_report_generator
)

__all__ = [
    'BaseResearchAgent',
    'DeepResearchAgent',
    'StorageManager',
    'FileSystemStorageManager',
    'get_storage_manager',
    'BaseReportGenerator',
    'MarkdownReportGenerator',
    'HtmlReportGenerator',
    'get_report_generator'
]

# 根據可用性添加導出
if MONGODB_AVAILABLE:
    __all__.append('MongoDBStorageManager')
if MOTOR_AVAILABLE:
    __all__.extend(['AsyncMongoDBStorageManager', 'AsyncToSyncAdapter'])
