"""Base optimization strategy for AI Knowledge Forest evaluation system.

This module provides the base class for all optimization strategies used by the 
evaluation system to improve system performance and knowledge quality.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from src.storage.mongodb import MongoDBProvider
from src.common.decorators import track_energy, handle_errors

logger = logging.getLogger(__name__)


class BaseOptimizationStrategy(ABC):
    """Base class for optimization strategies.
    
    All optimization strategies should inherit from this base class
    and implement the required methods.
    """
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the optimization strategy.
        
        Args:
            storage_provider: Optional storage provider for persistence
        """
        self.storage = storage_provider
        self.name = self.__class__.__name__
    
    @abstractmethod
    @track_energy(10.0)
    async def evaluate(self, user_id: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate current system state for optimization opportunities.
        
        Args:
            user_id: User ID
            current_metrics: Current system metrics
            
        Returns:
            Evaluation results with optimization recommendations
        """
        pass
    
    @abstractmethod
    @track_energy(15.0)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply optimization strategy.
        
        Args:
            user_id: User ID
            parameters: Optimization parameters
            
        Returns:
            Optimization results
        """
        pass
    
    @abstractmethod
    async def revert(self, user_id: str, optimization_id: str) -> bool:
        """Revert an optimization if it caused degradation.
        
        Args:
            user_id: User ID
            optimization_id: ID of the optimization to revert
            
        Returns:
            True if successfully reverted
        """
        pass
    
    async def record_optimization(self, user_id: str, 
                                 strategy_name: str,
                                 parameters: Dict[str, Any],
                                 metrics_before: Dict[str, Any],
                                 result: Dict[str, Any]) -> str:
        """Record optimization for tracking and potential reversion.
        
        Args:
            user_id: User ID
            strategy_name: Name of the optimization strategy
            parameters: Optimization parameters used
            metrics_before: System metrics before optimization
            result: Optimization result
            
        Returns:
            ID of the recorded optimization
        """
        if not self.storage:
            logger.warning("No storage provider available to record optimization")
            return "no_storage"
            
        record = {
            "user_id": user_id,
            "strategy_name": strategy_name,
            "parameters": parameters,
            "metrics_before": metrics_before,
            "result": result,
            "timestamp": {"$currentDate": {"$type": "date"}},
            "status": "applied"
        }
        
        record_id = await self.storage.save_document("optimizations", record)
        return str(record_id)