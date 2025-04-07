"""Storage module for persistent and in-memory data storage.

This module provides interfaces and implementations for document storage,
vector storage, caching, and message queues.
"""
# Interfaces
from src.storage.base import (
    StorageProvider,
    DocumentStorage,
    VectorStorage,
    CacheStorage,
    MessageQueue
)

# Implementations
from src.storage.mongodb import MongoDBProvider
from src.storage.vector_search import MongoDBVectorProvider
from src.storage.redis import RedisProvider

# Convenience factory functions
def get_document_storage(**kwargs) -> DocumentStorage:
    """Get a document storage provider.
    
    Args:
        **kwargs: Parameters to pass to the storage provider constructor.
        
    Returns:
        A document storage provider.
    """
    from src.common.config import get_settings
    settings = get_settings()
    
    # Default to MongoDB
    provider = MongoDBProvider(**kwargs)
    
    return provider

def get_vector_storage(**kwargs) -> VectorStorage:
    """Get a vector storage provider.
    
    Args:
        **kwargs: Parameters to pass to the storage provider constructor.
        
    Returns:
        A vector storage provider.
    """
    from src.common.config import get_settings
    settings = get_settings()
    
    # Default to MongoDB Vector
    provider = MongoDBVectorProvider(**kwargs)
    
    return provider

def get_cache_storage(**kwargs) -> CacheStorage:
    """Get a cache storage provider.
    
    Args:
        **kwargs: Parameters to pass to the storage provider constructor.
        
    Returns:
        A cache storage provider.
    """
    from src.common.config import get_settings
    settings = get_settings()
    
    # Default to Redis
    provider = RedisProvider(**kwargs)
    
    return provider

def get_message_queue(**kwargs) -> MessageQueue:
    """Get a message queue provider.
    
    Args:
        **kwargs: Parameters to pass to the storage provider constructor.
        
    Returns:
        A message queue provider.
    """
    from src.common.config import get_settings
    settings = get_settings()
    
    # Default to Redis
    provider = RedisProvider(**kwargs)
    
    return provider

__all__ = [
    # Interfaces
    "StorageProvider",
    "DocumentStorage",
    "VectorStorage",
    "CacheStorage",
    "MessageQueue",
    
    # Implementations
    "MongoDBProvider",
    "MongoDBVectorProvider",
    "RedisProvider",
    
    # Factory functions
    "get_document_storage",
    "get_vector_storage",
    "get_cache_storage",
    "get_message_queue"
]
