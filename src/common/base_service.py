"""Base service class for all services in the AI Knowledge Forest.

This module provides a base class that implements common functionality needed
across different services, including:
- Common initialization patterns
- Energy consumption tracking
- Dependency injection
- Async lifecycle management
"""
import logging
from typing import Optional, Dict, Any, List, Callable, Type, TypeVar, Generic
import asyncio
from datetime import datetime

from storage.mongodb import MongoDBProvider
from common.exceptions import ServiceError

# Generic type for service configuration
T = TypeVar('T')

class BaseService(Generic[T]):
    """Base class for services in the AI Knowledge Forest.
    
    Provides common functionality for services:
    - Storage provider management
    - Energy consumption tracking
    - Dependency injection
    - Async lifecycle management
    """
    
    def __init__(self, 
                 service_name: str,
                 storage_provider: Optional[MongoDBProvider] = None,
                 config: Optional[T] = None,
                 dependencies: Optional[Dict[str, Any]] = None):
        """Initialize the base service.
        
        Args:
            service_name: Name of the service (used for logging)
            storage_provider: Optional MongoDB storage provider
            config: Optional service configuration
            dependencies: Optional dictionary of service dependencies
        """
        self.service_name = service_name
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.storage = storage_provider
        self.config = config
        self.dependencies = dependencies or {}
        self.energy_consumed = 0.0
        self.started = False
        self.tasks = []
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
    
    async def start(self) -> bool:
        """Start the service and its background tasks.
        
        Returns:
            True if service started successfully
        """
        if self.started:
            self.logger.warning(f"{self.service_name} already started")
            return True
            
        try:
            # Ensure storage connection
            if not await self.storage.is_connected():
                await self.storage.connect()
                
            # Call service-specific initialization
            await self._initialize()
            
            self.started = True
            self.logger.info(f"{self.service_name} started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start {self.service_name}: {str(e)}")
            return False
    
    async def stop(self) -> bool:
        """Stop the service and clean up resources.
        
        Returns:
            True if service stopped successfully
        """
        if not self.started:
            self.logger.warning(f"{self.service_name} is not running")
            return True
            
        try:
            # Cancel any background tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    
            # Wait for all tasks to complete
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
                
            # Call service-specific cleanup
            await self._cleanup()
            
            self.started = False
            self.logger.info(f"{self.service_name} stopped successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping {self.service_name}: {str(e)}")
            return False
    
    async def _initialize(self) -> None:
        """Service-specific initialization.
        
        Override this method in derived classes to implement service-specific
        initialization logic.
        """
        pass
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup.
        
        Override this method in derived classes to implement service-specific
        cleanup logic.
        """
        pass
    
    def add_background_task(self, coro) -> asyncio.Task:
        """Add a background task to the service.
        
        Args:
            coro: Coroutine to run as a background task
            
        Returns:
            The created task
        """
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        # Add done callback to remove task from list when complete
        task.add_done_callback(lambda t: self.tasks.remove(t) if t in self.tasks else None)
        return task
    
    def track_energy(self, amount: float) -> None:
        """Track energy consumption.
        
        Args:
            amount: Amount of energy consumed
        """
        self.energy_consumed += amount
    
    def get_energy_cost(self) -> float:
        """Get the current energy consumption.
        
        Returns:
            Total energy consumed
        """
        return self.energy_consumed
    
    def reset_energy_tracking(self) -> None:
        """Reset energy consumption tracking."""
        self.energy_consumed = 0.0
    
    def get_dependency(self, name: str, required: bool = False) -> Any:
        """Get a dependency by name.
        
        Args:
            name: Name of the dependency
            required: Whether the dependency is required
            
        Returns:
            The dependency or None if not found
            
        Raises:
            ServiceError: If dependency is required but not found
        """
        dependency = self.dependencies.get(name)
        if required and dependency is None:
            raise ServiceError(f"Required dependency '{name}' not found")
        return dependency
    
    async def log_operation(self, 
                          operation: str, 
                          user_id: Optional[str] = None,
                          details: Optional[Dict[str, Any]] = None,
                          success: bool = True) -> None:
        """Log an operation to the database.
        
        Args:
            operation: Name of the operation
            user_id: Optional user ID
            details: Optional operation details
            success: Whether the operation was successful
        """
        if not self.storage:
            return
            
        log_entry = {
            "service": self.service_name,
            "operation": operation,
            "timestamp": datetime.utcnow(),
            "success": success,
        }
        
        if user_id:
            log_entry["user_id"] = user_id
            
        if details:
            log_entry["details"] = details
            
        try:
            await self.storage.save_document("service_logs", log_entry)
        except Exception as e:
            self.logger.error(f"Failed to log operation: {str(e)}")
