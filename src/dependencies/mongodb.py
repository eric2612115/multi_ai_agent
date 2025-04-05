"""
MongoDB provider dependency for FastAPI routes
"""
from typing import Optional
from fastapi import Depends
from storage.mongodb import MongoDBProvider

# Global MongoDB provider instance
_mongodb_provider: Optional[MongoDBProvider] = None

def get_mongodb_provider() -> Optional[MongoDBProvider]:
    """Get the MongoDB provider instance.
    
    This dependency function is used by FastAPI routes to get access to the MongoDB provider.
    
    Returns:
        The MongoDB provider instance, or None if not initialized.
    """
    global _mongodb_provider
    return _mongodb_provider

def initialize_mongodb_provider(provider: MongoDBProvider) -> None:
    """Initialize the global MongoDB provider instance.
    
    Args:
        provider: The MongoDB provider instance to use.
    """
    global _mongodb_provider
    _mongodb_provider = provider
