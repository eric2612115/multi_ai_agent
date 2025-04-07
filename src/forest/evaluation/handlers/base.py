"""Base optimization handler for AI Knowledge Forest evaluation system.

This module provides the base class for all component-specific optimization handlers
used by the evaluation system.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from src.storage.mongodb import MongoDBProvider
from src.common.decorators import track_energy, handle_errors

logger = logging.getLogger(__name__)


class BaseOptimizationHandler(ABC):
    """Base class for component-specific optimization handlers.
    
    All component optimization handlers should inherit from this base class
    and implement the required methods.
    """
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the optimization handler.
        
        Args:
            storage_provider: Optional storage provider for persistence
        """
        self.storage = storage_provider
        self.name = self.__class__.__name__
    
    @abstractmethod
    @track_energy(5.0)
    async def collect_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect component-specific metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Component metrics
        """
        pass
    
    @abstractmethod
    @track_energy(8.0)
    async def analyze_metrics(self, user_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze component metrics and identify issues.
        
        Args:
            user_id: User ID
            metrics: Component metrics
            
        Returns:
            Analysis results with identified issues
        """
        pass
    
    @abstractmethod
    @track_energy(10.0)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply component-specific optimizations.
        
        Args:
            user_id: User ID
            parameters: Optimization parameters
            
        Returns:
            Optimization results
        """
        pass
    
    async def calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate component health score from metrics.
        
        Args:
            metrics: Component metrics
            
        Returns:
            Health score (0.0 to 1.0)
        """
        # Default implementation - can be overridden by subclasses
        # to provide component-specific health scoring
        if not metrics:
            return 0.5
            
        # Simple average of relevant metrics
        relevant_metrics = []
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and key != "timestamp":
                if key.endswith("_score") or key.endswith("_ratio"):
                    relevant_metrics.append(value)
                    
        if not relevant_metrics:
            return 0.5
            
        return sum(relevant_metrics) / len(relevant_metrics)