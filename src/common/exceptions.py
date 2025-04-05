"""自定义异常类。

这个模块定义了项目中使用的自定义异常，以便统一异常处理。
"""

class BaseError(Exception):
    """基础异常类，所有自定义异常的父类。"""
    pass


class ConfigError(BaseError):
    """配置错误。"""
    pass


class AIError(BaseError):
    """AI 相关错误的基类。"""
    pass


class AIServiceUnavailableError(AIError):
    """AI 服务不可用错误。"""
    pass


class AIRequestError(AIError):
    """AI 请求错误。"""
    pass


class AIRateLimitError(AIRequestError):
    """AI 请求速率限制错误。"""
    pass


class StorageError(BaseError):
    """存储相关错误的基类。"""
    pass


class StorageConnectionError(StorageError):
    """存储连接错误。"""
    pass


class StorageQueryError(StorageError):
    """存储查询错误。"""
    pass


class KnowledgeForestError(BaseError):
    """知识森林相关错误的基类。"""
    pass


class ExtractionError(KnowledgeForestError):
    """知识提取错误。"""
    pass


class PlacementError(KnowledgeForestError):
    """知识放置错误。"""
    pass


class GraphError(KnowledgeForestError):
    """图操作错误。"""
    pass


class TaskHandlerError(KnowledgeForestError):
    """任务处理器错误。"""
    pass


class APIError(BaseError):
    """API 相关错误的基类。"""
    pass


class AuthenticationError(APIError):
    """认证错误。"""
    pass


class AuthorizationError(APIError):
    """授权错误。"""
    pass


class RateLimitError(APIError):
    """API 速率限制错误。"""
    pass


class ValidationError(APIError):
    """输入验证错误。"""
    pass


class TaskError(BaseError):
    """任务相关错误的基类。"""
    pass


class TaskQueueError(TaskError):
    """任务队列错误。"""
    pass


class TaskExecutionError(TaskError):
    """任务执行错误。"""
    pass


# 反思系统相关错误
class ReflectionError(KnowledgeForestError):
    """反思系统错误。"""
    pass


class GapFinderError(ReflectionError):
    """知识缺口发现错误。"""
    pass


class AnalysisError(ReflectionError):
    """知识分析错误。"""
    pass


class ExecutionError(ReflectionError):
    """任务执行错误。"""
    pass


# 能量系统相关错误
class EnergyError(KnowledgeForestError):
    """能量管理错误。"""
    pass


# 生命周期管理相关错误
class LifecycleError(KnowledgeForestError):
    """生命周期管理错误。"""
    pass


# 抽象层级管理相关错误
class AbstractionError(KnowledgeForestError):
    """抽象层级管理错误。"""
    pass


# 创新机制相关错误
class InnovationError(KnowledgeForestError):
    """概念创新错误基类。"""
    pass


class SynthesisError(InnovationError):
    """概念合成错误。"""
    pass


class EvaluationError(InnovationError):
    """创新评估错误。"""
    pass


# 自我平衡相关错误
class BalanceError(KnowledgeForestError):
    """自我平衡错误。"""
    pass


# 系统评估与优化相关错误
class SystemEvaluationError(KnowledgeForestError):
    """系统评估错误。"""
    pass


class OptimizationError(KnowledgeForestError):
    """系统优化错误。"""
    pass


class ServiceError(BaseError):
    """服务层错误。"""
    pass


class FactoryError(BaseError):
    """工厂创建错误。"""
    pass


class StrategyError(BaseError):
    """策略执行错误。"""
    pass


class ObserverError(BaseError):
    """观察者通知错误。"""
    pass