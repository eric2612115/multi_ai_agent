"""AI 模型工厂。

这个模块提供了创建和管理 AI 模型实例的工厂功能，支持模型的注册和实例化。
"""
from typing import Dict, Type, Any, Optional, List, Set
import importlib
import logging
from src.ai.base import AIModel, TextGenerationModel, EmbeddingModel, SearchModel, WebExtractionModel
from src.common.exceptions import ConfigError

# 模型类型注册表
_model_registry: Dict[str, Type[AIModel]] = {}

# 单例实例
_model_instances: Dict[str, AIModel] = {}

# 日志
logger = logging.getLogger(__name__)


def register_ai_model(model_type: str, model_class: Type[AIModel]) -> None:
    """注册 AI 模型实现。
    
    Args:
        model_type: 模型类型标识符。
        model_class: 要注册的模型类。
    """
    logger.debug(f"注册 AI 模型: {model_type}")
    _model_registry[model_type.lower()] = model_class


def create_ai_model(model_type: str, **kwargs) -> AIModel:
    """创建 AI 模型实例。
    
    Args:
        model_type: 要创建的模型类型。
        **kwargs: 传递给模型构造函数的参数。
        
    Returns:
        AI 模型实例。
        
    Raises:
        ValueError: 如果指定的模型类型不受支持。
    """
    model_type = model_type.lower()
    
    # 懒加载模型实现
    if model_type not in _model_registry:
        _load_model_implementation(model_type)
    
    # 从注册表获取模型类
    if model_type not in _model_registry:
        logger.error(f"尝试创建未注册的模型类型: {model_type}，已注册的模型: {list(_model_registry.keys())}")
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    model_class = _model_registry[model_type]
    logger.debug(f"创建 AI 模型实例: {model_type}")
    
    # 处理 API 密钥问题
    if model_type == "gemini" and "api_key" not in kwargs:
        # 检查环境变量
        import os
        gemini_key = os.environ.get("AI_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            kwargs["api_key"] = gemini_key
            logger.info("从环境变量加载 Gemini API 密钥")
    elif model_type == "claude" and "api_key" not in kwargs:
        import os
        claude_key = os.environ.get("AI_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if claude_key:
            kwargs["api_key"] = claude_key
            logger.info("从环境变量加载 Claude API 密钥")
    
    return model_class(**kwargs)


def get_ai_model(model_type: str = "default", **kwargs) -> AIModel:
    """获取或创建 AI 模型实例（单例模式）。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        AI 模型实例。
    """
    model_type = model_type.lower()
    
    # 使用默认模型
    if model_type == "default":
        from common.config import get_settings
        model_type = get_settings().ai.default_service
        
        # 确保默认服务被设置
        if not model_type or model_type == "default":
            # 加载所有可能的模型实现
            try:
                import ai.gemini
                model_type = "gemini"
            except ImportError:
                try:
                    import ai.claude
                    model_type = "claude"
                except ImportError:
                    raise ValueError("没有可用的默认AI模型服务. 请确保至少安装一个AI服务依赖 (gemini 或 claude)")
    
    # 如果实例不存在则创建
    if model_type not in _model_instances:
        _model_instances[model_type] = create_ai_model(model_type, **kwargs)
    
    return _model_instances[model_type]


def get_text_model(model_type: str = "default", **kwargs) -> TextGenerationModel:
    """获取文本生成模型实例（别名 get_text_generation_model）。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        TextGenerationModel 实例。
        
    Raises:
        TypeError: 如果模型不支持文本生成。
    """
    return get_text_generation_model(model_type, **kwargs)


def get_text_generation_model(model_type: str = "default", **kwargs) -> TextGenerationModel:
    """获取文本生成模型实例。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        TextGenerationModel 实例。
        
    Raises:
        TypeError: 如果模型不支持文本生成。
    """
    model = get_ai_model(model_type, **kwargs)
    if not isinstance(model, TextGenerationModel):
        raise TypeError(f"模型 {model_type} 不支持文本生成")
    return model


def get_embedding_model(model_type: str = "default", **kwargs) -> EmbeddingModel:
    """获取嵌入向量模型实例。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        EmbeddingModel 实例。
        
    Raises:
        TypeError: 如果模型不支持嵌入向量。
    """
    model = get_ai_model(model_type, **kwargs)
    if not isinstance(model, EmbeddingModel):
        raise TypeError(f"模型 {model_type} 不支持嵌入向量")
    return model


def get_search_model(model_type: str = "default", **kwargs) -> SearchModel:
    """获取搜索模型实例。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        SearchModel 实例。
        
    Raises:
        TypeError: 如果模型不支持搜索。
    """
    model = get_ai_model(model_type, **kwargs)
    if not isinstance(model, SearchModel):
        raise TypeError(f"模型 {model_type} 不支持搜索")
    return model


def get_web_extraction_model(model_type: str = "default", **kwargs) -> WebExtractionModel:
    """获取网页提取模型实例。
    
    Args:
        model_type: 要获取的模型类型。
        **kwargs: 如果需要创建，传递给模型构造函数的参数。
        
    Returns:
        WebExtractionModel 实例。
        
    Raises:
        TypeError: 如果模型不支持网页提取。
    """
    model = get_ai_model(model_type, **kwargs)
    if not isinstance(model, WebExtractionModel):
        raise TypeError(f"模型 {model_type} 不支持网页提取")
    return model


def get_available_models() -> Dict[str, Set[str]]:
    """获取可用的模型和它们支持的能力。
    
    Returns:
        字典，键是模型类型，值是支持的能力集合。
    """
    result = {}
    for model_type in _model_registry.keys():
        try:
            model = create_ai_model(model_type)
            capabilities = set()
            if isinstance(model, TextGenerationModel):
                capabilities.add("text_generation")
            if isinstance(model, EmbeddingModel):
                capabilities.add("embedding")
            if isinstance(model, SearchModel):
                capabilities.add("search")
            if isinstance(model, WebExtractionModel):
                capabilities.add("web_extraction")
            
            result[model_type] = capabilities
        except Exception as e:
            logger.warning(f"获取模型 {model_type} 能力时出错: {str(e)}")
    
    return result


def reset_model_instances() -> None:
    """重置所有模型实例（用于测试或重新加载配置）。"""
    global _model_instances
    _model_instances = {}


def _load_model_implementation(model_type: str) -> None:
    """动态加载模型实现。
    
    Args:
        model_type: 要加载的模型类型。
    """
    try:
        # 尝试基于模型类型导入模块
        module_name = f"ai.{model_type}"
        importlib.import_module(module_name)
        logger.debug(f"已加载模型实现: {module_name}")
    except ImportError as e:
        logger.warning(f"加载模型 {model_type} 实现失败: {str(e)}")
