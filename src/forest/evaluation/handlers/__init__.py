"""Optimization handlers package for AI Knowledge Forest evaluation system.

This package provides specific optimization handlers for different system components.
"""

from src.forest.evaluation.handlers.base import BaseOptimizationHandler
from src.forest.evaluation.handlers.energy_optimization import EnergyOptimizationHandler
from src.forest.evaluation.handlers.lifecycle_optimization import LifecycleOptimizationHandler
from src.forest.evaluation.handlers.reflection_optimization import ReflectionOptimizationHandler
from src.forest.evaluation.handlers.placement_optimization import PlacementOptimizationHandler

__all__ = [
    "BaseOptimizationHandler",
    "EnergyOptimizationHandler",
    "LifecycleOptimizationHandler",
    "ReflectionOptimizationHandler",
    "PlacementOptimizationHandler"
]