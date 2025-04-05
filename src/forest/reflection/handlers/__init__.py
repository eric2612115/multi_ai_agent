"""Reflection task handler package.

This package contains handlers for different types of reflection tasks.
"""
from forest.reflection.handlers.base import TaskHandler
from forest.reflection.handlers.topic_expansion import TopicExpansionHandler
from forest.reflection.handlers.abstraction_generation import AbstractionGenerationHandler
from forest.reflection.handlers.knowledge_pruning import KnowledgePruningHandler
from forest.reflection.handlers.relation_discovery import RelationDiscoveryHandler
from forest.reflection.handlers.content_verification import ContentVerificationHandler
from forest.reflection.handlers.importance_redistribution import ImportanceRedistributionHandler
from forest.reflection.handlers.lifecycle_management import LifecycleManagementHandler
from forest.reflection.handlers.strategy_adaptation import StrategyAdaptationHandler

# Registry of all handlers
TASK_HANDLERS = [
    TopicExpansionHandler,
    AbstractionGenerationHandler,
    KnowledgePruningHandler,
    RelationDiscoveryHandler,
    ContentVerificationHandler,
    ImportanceRedistributionHandler,
    LifecycleManagementHandler,
    StrategyAdaptationHandler
]

# Map of task types to handler classes
HANDLER_MAP = {handler.task_type: handler for handler in TASK_HANDLERS}

def get_handler_class(task_type: str) -> type:
    """Get the handler class for a task type.
    
    Args:
        task_type: Task type
        
    Returns:
        Handler class
    """
    return HANDLER_MAP.get(task_type)
