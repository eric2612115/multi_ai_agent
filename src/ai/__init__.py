"""AI 模型模块。

这个模块提供了 AI 模型的接口和实现，支持不同类型的 AI 服务。
"""
# 重新导出基类和工厂函数，以便于使用
from ai.base import (
    AIModel, 
    TextGenerationModel,
    EmbeddingModel,
    SearchModel,
    WebExtractionModel,
    MultiModalModel
)

from ai.factory import (
    register_ai_model,
    create_ai_model,
    get_ai_model,
    get_text_generation_model,
    get_embedding_model,
    get_search_model,
    get_web_extraction_model,
    get_available_models,
    reset_model_instances
)

# 版本信息
__version__ = "1.0.0"

# 公开的符号
__all__ = [
    # 基类
    "AIModel",
    "TextGenerationModel",
    "EmbeddingModel",
    "SearchModel",
    "WebExtractionModel",
    "MultiModalModel",
    
    # 工厂函数
    "register_ai_model",
    "create_ai_model",
    "get_ai_model",
    "get_text_generation_model",
    "get_embedding_model",
    "get_search_model",
    "get_web_extraction_model",
    "get_available_models",
    "reset_model_instances",
]

# 初始化日志
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# 导入默认模型实现，触发自注册
# 注意：这些导入会通过调用 register_ai_model 在工厂里注册模型
try:
    import ai.gemini
    import ai.gemini_function_calling  # 导入 Gemini 的 function calling 扩展
    import ai.claude
    import ai.firecrawl
    
    # 导入思考过程监控相关模块
    import ai.thinking_monitor
    import ai.thinking_context
    import ai.chat_agent_thinking  # 这会扩展 ChatAgent 类
except ImportError as e:
    logger.debug(f"导入 AI 模型时出错 (这可能是正常的，如果你不需要某些模型): {str(e)}")
