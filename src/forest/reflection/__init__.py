"""Autonomous reflection system for AI Knowledge Forest.

This package implements the self-awareness and self-evolution mechanisms
of the knowledge forest, allowing it to monitor, evaluate, and optimize
its own knowledge structures and learning strategies.
"""
from forest.reflection.core import ReflectionSystem
from forest.reflection.observer import SystemObserver
from forest.reflection.analyzer import KnowledgeAnalyzer
from forest.reflection.planner import ReflectionPlanner
from forest.reflection.executor import TaskExecutor
from forest.reflection.gap_finder import KnowledgeGapFinder

__all__ = [
    'ReflectionSystem',
    'SystemObserver',
    'KnowledgeAnalyzer',
    'ReflectionPlanner',
    'TaskExecutor',
    'KnowledgeGapFinder',
]
