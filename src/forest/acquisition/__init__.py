"""Active knowledge acquisition package for AI Knowledge Forest.

This package provides mechanisms for the system to autonomously identify knowledge
gaps and proactively acquire new knowledge from external sources.
"""

from src.forest.acquisition.manager import AcquisitionManager
from src.forest.acquisition.perception import PerceptionSystem

__all__ = ["AcquisitionManager", "PerceptionSystem"]