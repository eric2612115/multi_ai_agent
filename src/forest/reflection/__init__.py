"""Autonomous reflection system for AI Knowledge Forest.

This package implements the self-awareness and self-evolution mechanisms
of the knowledge forest, allowing it to monitor, evaluate, and optimize
its own knowledge structures and learning strategies.
"""
from src.forest.reflection.core import ReflectionSystem
from src.forest.reflection.observer import SystemObserver
from src.forest.reflection.analyzer import KnowledgeAnalyzer
from src.forest.reflection.planner import ReflectionPlanner
from src.forest.reflection.executor import TaskExecutor
from src.forest.reflection.gap_finder import KnowledgeGapFinder

__all__ = [
    'ReflectionSystem',
    'SystemObserver',
    'KnowledgeAnalyzer',
    'ReflectionPlanner',
    'TaskExecutor',
    'KnowledgeGapFinder',
]
