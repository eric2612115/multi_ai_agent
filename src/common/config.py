"""全局配置管理模块。

这个模块提供了一个中心配置管理系统，统一所有服务和组件的配置。
配置可以从环境变量、配置文件或默认值加载。
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Union, List, Set
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from common.exceptions import ConfigError

# 设置日志
logger = logging.getLogger(__name__)

# 尝试加载 .env 文件
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    logger.debug(f"Loaded environment from {dotenv_path}")
else:
    load_dotenv()  # Fall back to default behavior
    logger.debug("Attempted to load environment from default location")

# 映射 API 密钥到期望的格式
if os.environ.get('GEMINI_API_KEY') and not os.environ.get('AI_GEMINI_API_KEY'):
    os.environ['AI_GEMINI_API_KEY'] = os.environ.get('GEMINI_API_KEY')
    logger.debug("Mapped GEMINI_API_KEY to AI_GEMINI_API_KEY")

if os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('AI_CLAUDE_API_KEY'):
    os.environ['AI_CLAUDE_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY')
    logger.debug("Mapped ANTHROPIC_API_KEY to AI_CLAUDE_API_KEY")

if os.environ.get('FIRECRAWL_API_KEY') and not os.environ.get('AI_FIRECRAWL_API_KEY'):
    os.environ['AI_FIRECRAWL_API_KEY'] = os.environ.get('FIRECRAWL_API_KEY')
    logger.debug("Mapped FIRECRAWL_API_KEY to AI_FIRECRAWL_API_KEY")


class AISettings(BaseSettings):
    """AI 模型相关配置。"""
    
    default_service: str = Field(
        default="gemini", 
        env="DEFAULT_AI_SERVICE", 
        description="默认使用的 AI 服务"
    )
    max_tokens: int = Field(
        default=1024, 
        env="MAX_TOKENS", 
        description="默认的最大 token 生成数量"
    )
    enable_advanced_models: bool = Field(
        default=False, 
        env="ENABLE_ADVANCED_MODELS", 
        description="是否启用高级模型"
    )
    embedding_dimensions: int = Field(
        default=768,
        env="EMBEDDING_DIMENSIONS",
        description="嵌入向量的维度"
    )
    
    # Gemini 配置
    gemini_api_key: str = Field(
        default="", 
        env="GEMINI_API_KEY", 
        description="Google Gemini API 密钥"
    )
    gemini_model_name: str = Field(
        default="gemini-pro", 
        env="GEMINI_MODEL_NAME", 
        description="Gemini 模型名称"
    )
    gemini_embedding_model: str = Field(
        default="embedding-001", 
        env="GEMINI_EMBEDDING_MODEL", 
        description="Gemini 嵌入模型名称"
    )
    
    # Claude 配置
    claude_api_key: str = Field(
        default="", 
        env="CLAUDE_API_KEY", 
        description="Anthropic Claude API 密钥"
    )
    claude_model_name: str = Field(
        default="claude-3-opus-20240229", 
        env="CLAUDE_MODEL_NAME", 
        description="Claude 模型名称"
    )
    claude_api_version: str = Field(
        default="2023-06-01", 
        env="CLAUDE_API_VERSION", 
        description="Claude API 版本"
    )
    
    # Firecrawl 配置
    firecrawl_api_key: str = Field(
        default="", 
        env="FIRECRAWL_API_KEY", 
        description="Firecrawl API 密钥"
    )
    firecrawl_api_url: str = Field(
        default="https://api.firecrawl.dev", 
        env="FIRECRAWL_API_URL", 
        description="Firecrawl API URL"
    )

    class Config:
        env_prefix = "AI_"
        env_file = ".env"


class DatabaseSettings(BaseSettings):
    """数据库相关配置。"""
    
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017", 
        env="MONGODB_URL", 
        description="MongoDB 连接 URI"
    )
    mongodb_db: str = Field(
        default="multi_ai_agent", 
        env="MONGODB_DB", 
        description="MongoDB 数据库名称"
    )
    redis_uri: str = Field(
        default="redis://localhost:6379/0", 
        env="REDIS_URI", 
        description="Redis 连接 URI"
    )
    enable_vector_search: bool = Field(
        default=False, 
        env="ENABLE_VECTOR_SEARCH", 
        description="是否启用向量搜索（需要 MongoDB Atlas）"
    )
    vector_search_index: str = Field(
        default="nodes_vector_index", 
        env="VECTOR_SEARCH_INDEX", 
        description="MongoDB Atlas 向量搜索索引名称"
    )
    node_similarity_threshold: float = Field(
        default=0.7, 
        env="NODE_SIMILARITY_THRESHOLD", 
        description="节点相似性阈值（0-1）"
    )

    class Config:
        env_prefix = "DB_"
        env_file = ".env"


class SecuritySettings(BaseSettings):
    """安全相关配置。"""
    
    jwt_secret_key: str = Field(
        default="your_default_secret_key_for_development", 
        env="JWT_SECRET_KEY", 
        description="JWT 密钥（重要：生产中必须设置）"
    )
    jwt_algorithm: str = Field(
        default="HS256", 
        env="JWT_ALGORITHM", 
        description="JWT 算法"
    )
    access_token_expire_minutes: int = Field(
        default=1440, 
        env="ACCESS_TOKEN_EXPIRE_MINUTES", 
        description="访问令牌过期时间（分钟）"
    )

    class Config:
        env_prefix = "SECURITY_"
        env_file = ".env"


class KnowledgeForestSettings(BaseSettings):
    """知识森林特定配置。"""
    
    threshold_extend: float = Field(
        default=0.85, 
        env="THRESHOLD_EXTEND", 
        description="扩展现有节点的相似度阈值（0-1）"
    )
    threshold_branch: float = Field(
        default=0.70, 
        env="THRESHOLD_BRANCH", 
        description="创建分支节点的相似度阈值（0-1）"
    )
    threshold_crosslink: float = Field(
        default=0.80, 
        env="THRESHOLD_CROSSLINK", 
        description="创建跨主题链接的相似度阈值（0-1）"
    )
    max_crosslink_distance: int = Field(
        default=3, 
        env="MAX_CROSSLINK_DISTANCE", 
        description="最大跨主题链接距离"
    )
    enable_auto_classification: bool = Field(
        default=True, 
        env="ENABLE_AUTO_CLASSIFICATION", 
        description="启用自动知识分类"
    )

    class Config:
        env_prefix = "FOREST_"
        env_file = ".env"


class ReflectionSettings(BaseSettings):
    """反思系统配置。"""
    
    enable_autonomous: bool = Field(
        default=True, 
        env="ENABLE_AUTONOMOUS", 
        description="启用自主反思"
    )
    cycle_interval_hours: int = Field(
        default=6, 
        env="CYCLE_INTERVAL_HOURS", 
        description="反思循环间隔（小时）"
    )
    idle_trigger_minutes: int = Field(
        default=30, 
        env="IDLE_TRIGGER_MINUTES", 
        description="空闲触发反思的时间（分钟）"
    )
    energy_budget_default: float = Field(
        default=100.0, 
        env="ENERGY_BUDGET_DEFAULT", 
        description="默认能量预算"
    )
    min_nodes_for_cycle: int = Field(
        default=10,
        env="MIN_NODES_FOR_CYCLE",
        description="启动反思循环所需的最小节点数"
    )

    class Config:
        env_prefix = "REFLECTION_"
        env_file = ".env"


class LifecycleSettings(BaseSettings):
    """生命周期管理配置。"""
    
    node_dormancy_threshold: float = Field(
        default=0.2, 
        env="NODE_DORMANCY_THRESHOLD", 
        description="节点休眠阈值（低于该重要性分数进入休眠）"
    )
    node_min_age_days: int = Field(
        default=7, 
        env="NODE_MIN_AGE_DAYS", 
        description="节点被考虑休眠的最小年龄（天）"
    )
    enable_auto_pruning: bool = Field(
        default=True, 
        env="ENABLE_AUTO_PRUNING", 
        description="启用自动知识淘汰"
    )
    pruning_interval_hours: int = Field(
        default=24, 
        env="PRUNING_INTERVAL_HOURS", 
        description="知识淘汰执行间隔（小时）"
    )
    revival_threshold: float = Field(
        default=0.5, 
        env="REVIVAL_THRESHOLD", 
        description="节点复活阈值（高于该重要性分数时可能复活）"
    )

    class Config:
        env_prefix = "LIFECYCLE_"
        env_file = ".env"


class AbstractionSettings(BaseSettings):
    """抽象层级管理配置。"""
    
    min_cluster_size: int = Field(
        default=3, 
        env="MIN_CLUSTER_SIZE", 
        description="生成抽象所需的最小集群大小"
    )
    similarity_threshold: float = Field(
        default=0.7, 
        env="SIMILARITY_THRESHOLD", 
        description="抽象生成的相似度阈值"
    )
    max_level: int = Field(
        default=5, 
        env="MAX_LEVEL", 
        description="最高抽象层级（1-5）"
    )
    enable_auto_generation: bool = Field(
        default=True, 
        env="ENABLE_AUTO_GENERATION", 
        description="启用自动抽象生成"
    )

    class Config:
        env_prefix = "ABSTRACTION_"
        env_file = ".env"


class EnergySettings(BaseSettings):
    """能量系统配置。"""
    
    initial_energy: float = Field(
        default=100.0, 
        env="INITIAL_ENERGY", 
        description="初始能量值"
    )
    replenish_rate: float = Field(
        default=10.0, 
        env="REPLENISH_RATE", 
        description="每小时能量恢复率"
    )
    max_energy: float = Field(
        default=150.0, 
        env="MAX_ENERGY", 
        description="最大能量上限"
    )
    decay_rate: float = Field(
        default=0.01, 
        env="DECAY_RATE", 
        description="自然能量衰减率"
    )

    class Config:
        env_prefix = "ENERGY_"
        env_file = ".env"


class BalanceSettings(BaseSettings):
    """平衡系统配置。"""
    
    enable_auto_balance: bool = Field(
        default=True, 
        env="ENABLE_AUTO_BALANCE", 
        description="启用自动平衡"
    )
    balance_interval_hours: int = Field(
        default=12, 
        env="BALANCE_INTERVAL_HOURS", 
        description="平衡循环间隔（小时）"
    )
    target_growth_rate: float = Field(
        default=0.05, 
        env="TARGET_GROWTH_RATE", 
        description="目标每日增长率"
    )
    target_connection_density: float = Field(
        default=0.1, 
        env="TARGET_CONNECTION_DENSITY", 
        description="目标连接密度"
    )
    max_topic_distribution_adjustment: float = Field(
        default=0.2, 
        env="MAX_TOPIC_DISTRIBUTION_ADJUSTMENT", 
        description="主题分布调整最大幅度"
    )

    class Config:
        env_prefix = "BALANCE_"
        env_file = ".env"


class EvaluationSettings(BaseSettings):
    """评估和优化系统配置。"""
    
    enable_auto_optimization: bool = Field(
        default=True, 
        env="ENABLE_AUTO_OPTIMIZATION", 
        description="启用自动系统优化"
    )
    evaluation_interval_hours: int = Field(
        default=24, 
        env="EVALUATION_INTERVAL_HOURS", 
        description="系统评估间隔（小时）"
    )
    optimization_trigger_threshold: float = Field(
        default=0.15, 
        env="OPTIMIZATION_TRIGGER_THRESHOLD", 
        description="触发优化的最小性能下降阈值"
    )
    metrics_retention_days: int = Field(
        default=30, 
        env="METRICS_RETENTION_DAYS", 
        description="保留历史指标的天数"
    )
    experiment_timeout_hours: int = Field(
        default=48, 
        env="EXPERIMENT_TIMEOUT_HOURS", 
        description="优化实验最长持续时间（小时）"
    )
    max_concurrent_experiments: int = Field(
        default=1, 
        env="MAX_CONCURRENT_EXPERIMENTS", 
        description="最大并发优化实验数量"
    )
    
    class Config:
        env_prefix = "EVALUATION_"
        env_file = ".env"


class ApiSettings(BaseSettings):
    """API 相关配置。"""
    
    frontend_url: str = Field(
        default="http://localhost:3000", 
        env="FRONTEND_URL", 
        description="前端 URL"
    )
    debug_mode: bool = Field(
        default=False, 
        env="DEBUG_MODE", 
        description="调试模式"
    )
    enable_mcp: bool = Field(
        default=True, 
        env="ENABLE_MCP", 
        description="启用 Model Context Protocol"
    )

    class Config:
        env_prefix = "API_"
        env_file = ".env"


class Settings(BaseSettings):
    """全局设置类，整合所有配置模块。"""
    
    app_name: str = Field(
        default="知识森林 AI 代理系统", 
        env="APP_NAME", 
        description="应用程序名称"
    )
    version: str = Field(
        default="1.0.0", 
        env="APP_VERSION", 
        description="应用程序版本"
    )
    environment: str = Field(
        default="development", 
        env="ENVIRONMENT", 
        description="运行环境 (development/production)"
    )
    
    ai: AISettings = AISettings()
    db: DatabaseSettings = DatabaseSettings()
    security: SecuritySettings = SecuritySettings()
    knowledge_forest: KnowledgeForestSettings = KnowledgeForestSettings()
    api: ApiSettings = ApiSettings()
    
    # 自我进化系统组件
    reflection: ReflectionSettings = ReflectionSettings()
    lifecycle: LifecycleSettings = LifecycleSettings()
    abstraction: AbstractionSettings = AbstractionSettings()
    energy: EnergySettings = EnergySettings()
    balance: BalanceSettings = BalanceSettings()
    evaluation: EvaluationSettings = EvaluationSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典（移除敏感信息）。"""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "ai": {k: v for k, v in self.ai.dict().items() 
                  if not k.endswith('_api_key')},  # 不包含敏感信息
            "db": {k: v for k, v in self.db.dict().items() 
                  if not k.endswith('_uri')},  # 不包含敏感信息
            "security": {k: v for k, v in self.security.dict().items() 
                        if k != 'jwt_secret_key'},  # 不包含敏感信息
            "knowledge_forest": self.knowledge_forest.dict(),
            "api": self.api.dict(),
            # 自我进化系统组件
            "reflection": self.reflection.dict(),
            "lifecycle": self.lifecycle.dict(),
            "abstraction": self.abstraction.dict(),
            "energy": self.energy.dict(),
            "balance": self.balance.dict(),
            "evaluation": self.evaluation.dict()
        }


# 创建全局配置实例
_settings = None


def get_settings() -> Settings:
    """获取全局配置实例。
    
    Returns:
        全局配置实例。
    """
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
            logger.debug("已加载配置")
        except Exception as e:
            logger.error(f"加载配置时出错: {str(e)}")
            raise ConfigError(f"无法加载配置: {str(e)}") from e
    return _settings


def reload_settings() -> Settings:
    """重新加载配置。
    
    Returns:
        重新加载的全局配置实例。
    """
    global _settings
    _settings = None
    return get_settings()