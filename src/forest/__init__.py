"""Knowledge Forest module.

This module provides functionality for extracting, organizing, and
retrieving knowledge from conversations.
"""
# Re-export main models and interfaces
from forest.models import (
    Node,
    Edge,
    NodeVisualAttributes,
    Conversation,
    Message,
    KnowledgeExtractionResult,
    PlacementDecision,
    GraphUpdateResult,
    ProcessingResult
)


# Factory functions
def get_knowledge_extractor(**kwargs):
    """Get a knowledge extractor instance.
    
    Args:
        **kwargs: Additional constructor parameters.
        
    Returns:
        A knowledge extractor instance.
    """
    from forest.extraction import KnowledgeExtractor
    return KnowledgeExtractor(**kwargs)


def get_knowledge_placement(**kwargs):
    """Get a knowledge placement service instance.
    
    Args:
        **kwargs: Additional constructor parameters.
        
    Returns:
        A knowledge placement service instance.
    """
    from forest.placement import KnowledgePlacementService
    return KnowledgePlacementService(**kwargs)


def get_graph_manager(**kwargs):
    """Get a graph manager instance.
    
    Args:
        **kwargs: Additional constructor parameters.
        
    Returns:
        A graph manager instance.
    """
    from forest.graph import KnowledgeGraphManager
    return KnowledgeGraphManager(**kwargs)


# Processor and Search modules not implemented yet
# Uncomment these when implemented

def get_knowledge_processor(**kwargs):
    """Get a knowledge processor instance.
    
    Args:
        **kwargs: Additional constructor parameters.
        
    Returns:
        A knowledge processor instance.
    """
    # This is a placeholder implementation since the module isn't implemented yet
    from forest.tasks import KnowledgeForestTaskHandler
    return KnowledgeForestTaskHandler(**kwargs)
# 
# 
# def get_knowledge_search(**kwargs):
#     """Get a knowledge search instance.
#     
#     Args:
#         **kwargs: Additional constructor parameters.
#         
#     Returns:
#         A knowledge search instance.
#     """
#     from forest.search import KnowledgeSearch
#     return KnowledgeSearch(**kwargs)


def init_knowledge_forest(app=None):
    """Initialize the Knowledge Forest and integrate it with the app.
    
    Args:
        app: Optional FastAPI application instance.
    """
    # API module not implemented yet
    # Uncomment when implemented
    
    # from forest.api import init_forest_api
    # if app:
    #     init_forest_api(app)
    
    # For now, just log that initialization is skipped
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Knowledge Forest API initialization skipped - module not implemented yet.")


__all__ = [
    # Models
    "Node",
    "Edge",
    "NodeVisualAttributes",
    "Conversation",
    "Message",
    "KnowledgeExtractionResult",
    "PlacementDecision",
    "GraphUpdateResult",
    "ProcessingResult",

    # Factory functions
    "get_knowledge_extractor",
    "get_knowledge_placement",
    "get_graph_manager",
    "get_knowledge_processor",  # Now implemented
    # "get_knowledge_search",      # Still commented out until implemented

    # Initialization
    "init_knowledge_forest"
]
