"""Base class for reflection task handlers.

This module provides the abstract base class for all reflection task handlers.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type

from forest.models import ReflectionTask
from storage.mongodb import MongoDBProvider
from ai.base import TextGenerationModel
from forest.graph import KnowledgeGraphManager
from common.exceptions import ExecutionError
from common.decorators import handle_errors

logger = logging.getLogger(__name__)

class TaskHandler(ABC):
    """Base class for task handlers."""
    
    def __init__(self, executor: 'TaskExecutor'):
        """Initialize the task handler.
        
        Args:
            executor: The task executor that owns this handler
        """
        self.executor = executor
        self.storage = executor.storage
        self.text_model = executor.text_model
        self.graph_manager = executor.graph_manager
        self.energy_consumed = 0.0
    
    @property
    @abstractmethod
    def task_type(self) -> str:
        """Get the task type this handler supports.
        
        Returns:
            Task type string
        """
        pass
    
    @abstractmethod
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle a task.
        
        Args:
            user_id: The user ID
            task: The task to handle
            
        Returns:
            Result dictionary
        """
        pass
