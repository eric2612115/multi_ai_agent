"""Task executor for reflection cycle.

This module provides a factory-based task executor for reflection tasks,
which forms the Act phase of the OODA reflection cycle.
"""
import logging
from typing import Dict, List, Optional, Any, Type, Mapping

from src.forest.models import ReflectionTask, StringId
from src.forest.reflection.handlers import get_handler_class, TaskHandler
from src.forest.reflection.handlers.base import TaskHandler
from src.storage.mongodb import MongoDBProvider
from src.forest.graph import KnowledgeGraphManager
from src.forest.energy.manager_combined import EnergyManager
from src.forest.lifecycle.manager_combined import LifecycleManager
from src.forest.abstraction.generator_combined import AbstractionGenerator
from src.ai.base import TextGenerationModel
from src.ai.factory import get_text_generation_model
from src.common.config import get_settings
from src.common.exceptions import ExecutionError
from src.common.service_base import ForestService

settings = get_settings()
logger = logging.getLogger(__name__)

class TaskExecutor(ForestService):
    """Executor for reflection tasks."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None,
                energy_manager: Optional[EnergyManager] = None,
                lifecycle_manager: Optional[LifecycleManager] = None,
                abstraction_generator: Optional[AbstractionGenerator] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the task executor.
        
        Args:
            storage_provider: Optional storage provider
            graph_manager: Optional knowledge graph manager
            energy_manager: Optional energy manager
            lifecycle_manager: Optional lifecycle manager
            abstraction_generator: Optional abstraction generator
            text_model: Optional text generation model
        """
        super().__init__(storage_provider)
        
        # Initialize dependencies
        self.graph_manager = graph_manager
        self.energy_manager = energy_manager
        self.lifecycle_manager = lifecycle_manager
        self.abstraction_generator = abstraction_generator
        self.text_model = text_model
        
        # Lazy initialize graph manager if not provided
        if self.graph_manager is None:
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
            
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
            
        # Handler cache
        self._handlers: Dict[str, TaskHandler] = {}
        
        # Pool mapping for tasks
        self.energy_pool_mapping = {
            # Gap-related tasks
            "topic_expansion": "exploration",
            "abstraction_generation": "abstraction",
            "relation_discovery": "reflection",
            "knowledge_pruning": "reflection",
            "content_verification": "reflection",
            
            # System tasks
            "importance_redistribution": "system",
            "knowledge_lifecycle_management": "system",
            "learning_strategy_adaptation": "system"
        }
    
    async def execute_task(self, 
                        user_id: str, 
                        task: ReflectionTask) -> Dict[str, Any]:
        """Execute a reflection task.
        
        Args:
            user_id: The user ID
            task: The task to execute
            
        Returns:
            Task execution result
            
        Raises:
            ExecutionError: If task execution fails
        """
        try:
            # Get handler for this task
            handler = self._get_handler(task.type)
            
            if not handler:
                raise ExecutionError(f"No handler for task type: {task.type}")
                
            # Check if we have enough energy
            energy_cost = task.energy_cost
            pool_type = self._get_task_energy_pool(task.type)
            
            # Try to consume energy
            if self.energy_manager:
                success, remaining = await self.energy_manager.consume_energy(
                    user_id=user_id,
                    pool=pool_type,
                    amount=energy_cost,
                    component="reflection_executor",
                    task_id=str(task.id),
                    reason=f"Executing {task.type} task"
                )
                
                if not success:
                    logger.warning(f"Not enough energy in {pool_type.value} pool for task {task.type}")
                    return {
                        "success": False,
                        "error": f"Not enough energy for task. Required: {energy_cost}, Available: {remaining}.",
                        "energy_consumed": 0.0
                    }
            
            # Execute the task
            result = await handler.handle(user_id, task)
            
            # Use handler's energy consumption tracking
            energy_consumed = getattr(handler, 'energy_consumed', task.energy_cost)
            result["energy_consumed"] = energy_consumed
            
            # Log execution
            logger.info(f"Executed task {task.type} (energy: {energy_consumed})")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute task {task.type}: {str(e)}")
            raise ExecutionError(f"Failed to execute task {task.type}: {str(e)}")
    
    def _get_handler(self, task_type: str) -> Optional[TaskHandler]:
        """Get the handler for a task type.
        
        Creates and caches handlers on demand.
        
        Args:
            task_type: Task type
            
        Returns:
            Handler or None if no handler available
        """
        # Return cached handler if available
        if task_type in self._handlers:
            return self._handlers[task_type]
            
        # Get handler class
        handler_class = get_handler_class(task_type)
        
        if not handler_class:
            logger.error(f"No handler class found for task type: {task_type}")
            return None
            
        # Create handler
        handler = handler_class(self)
        
        # Cache for future use
        self._handlers[task_type] = handler
        
        return handler
    
    def _get_task_energy_pool(self, task_type: str) -> 'EnergyPoolType':
        """Get the energy pool type for a task type.
        
        Args:
            task_type: The task type
            
        Returns:
            Energy pool type
        """
        from src.forest.energy.models import EnergyPoolType
        
        # Get the pool name from mapping
        pool_name = self.energy_pool_mapping.get(task_type, "reflection")  # Default to reflection
        
        # Map to EnergyPoolType
        try:
            return getattr(EnergyPoolType, pool_name.upper())
        except AttributeError:
            logger.warning(f"Unknown energy pool: {pool_name}, using REFLECTION")
            return EnergyPoolType.REFLECTION
