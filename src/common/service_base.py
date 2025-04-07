"""Base classes for services.

This module provides base classes for services with common functionality,
such as storage provider initialization and dependency injection.
"""
import logging
from typing import Optional, Dict, Any, Type

from src.storage.mongodb import MongoDBProvider

logger = logging.getLogger(__name__)


class ServiceBase:
    """Base class for services with common initialization logic."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the service.
        
        Args:
            storage_provider: Optional storage provider
        """
        self.storage = storage_provider
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()


class ForestService(ServiceBase):
    """Base class for forest services with dependency injection."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None, 
                dependencies: Optional[Dict[str, Any]] = None):
        """Initialize the forest service.
        
        Args:
            storage_provider: Optional storage provider
            dependencies: Optional dictionary of service dependencies
        """
        super().__init__(storage_provider)
        
        # Store dependencies
        self.dependencies = dependencies or {}
    
    def get_dependency(self, name: str, default: Any = None) -> Any:
        """Get a dependency by name.
        
        Args:
            name: Dependency name
            default: Default value if dependency not found
            
        Returns:
            The dependency or default value
        """
        return self.dependencies.get(name, default)
    
    def register_dependency(self, name: str, dependency: Any) -> None:
        """Register a dependency.
        
        Args:
            name: Dependency name
            dependency: The dependency object
        """
        self.dependencies[name] = dependency


class AsyncServiceBase(ServiceBase):
    """Base class for async services with lifecycle management."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the async service.
        
        Args:
            storage_provider: Optional storage provider
        """
        super().__init__(storage_provider)
        self._is_running = False
    
    async def start(self) -> None:
        """Start the service."""
        if self._is_running:
            logger.debug(f"{self.__class__.__name__} already running")
            return
            
        logger.info(f"Starting {self.__class__.__name__}")
        self._is_running = True
        await self._on_start()
        
    async def stop(self) -> None:
        """Stop the service."""
        if not self._is_running:
            logger.debug(f"{self.__class__.__name__} already stopped")
            return
            
        logger.info(f"Stopping {self.__class__.__name__}")
        await self._on_stop()
        self._is_running = False
        
    async def _on_start(self) -> None:
        """Hook called when service starts.
        
        Override this in subclasses to implement startup logic.
        """
        pass
        
    async def _on_stop(self) -> None:
        """Hook called when service stops.
        
        Override this in subclasses to implement shutdown logic.
        """
        pass
