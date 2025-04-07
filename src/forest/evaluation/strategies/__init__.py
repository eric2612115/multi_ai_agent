"""Optimization strategies package for AI Knowledge Forest evaluation system.

This package provides various optimization strategies that can be applied
to improve system performance and knowledge quality.
"""

from src.forest.evaluation.strategies.base import BaseOptimizationStrategy
from src.forest.evaluation.strategies.parameter_tuning import ParameterTuningStrategy
from src.forest.evaluation.strategies.resource_allocation import ResourceAllocationStrategy
from src.forest.evaluation.strategies.structure_optimization import StructureOptimizationStrategy

__all__ = [
    "BaseOptimizationStrategy",
    "ParameterTuningStrategy",
    "ResourceAllocationStrategy",
    "StructureOptimizationStrategy"
]