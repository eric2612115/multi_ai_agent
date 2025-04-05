"""Reflection task planner for reflection cycle.

This module provides functionality for planning reflection tasks,
which forms the Decide phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from forest.models import (
    ReflectionTask, KnowledgeGap, SynthesisType, AbstractionLevel,
    StringId
)
from storage.mongodb import MongoDBProvider
from common.config import get_settings
from common.exceptions import PlannerError

settings = get_settings()
logger = logging.getLogger(__name__)

class ReflectionPlanner:
    """Planner for reflection tasks based on analysis and gaps."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the reflection planner.
        
        Args:
            storage_provider: Optional storage provider
        """
        self.storage = storage_provider
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Energy cost for planning
        self._energy_cost = 5.0  # Base cost
    
    async def plan_reflection_tasks(self,
                                 user_id: str,
                                 analysis_results: Dict[str, Any],
                                 identified_gaps: List[KnowledgeGap],
                                 energy_budget: float) -> List[ReflectionTask]:
        """Plan reflection tasks based on analysis and gaps.
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            identified_gaps: Identified knowledge gaps
            energy_budget: Energy budget for tasks
            
        Returns:
            List of planned tasks
            
        Raises:
            PlannerError: If planning fails
        """
        try:
            start_time = datetime.utcnow()
            
            # Initialize task list
            tasks = []
            
            # Skip if no gaps
            if not identified_gaps:
                logger.info("No gaps identified, no tasks to plan")
                return tasks
                
            # Create tasks from gaps
            for gap in identified_gaps:
                task = self._create_task_from_gap(gap)
                if task:
                    tasks.append(task)
            
            # Add system health tasks if needed
            system_health_tasks = self._create_system_health_tasks(analysis_results)
            tasks.extend(system_health_tasks)
            
            # Filter tasks based on energy budget
            tasks = self._filter_tasks_by_energy(tasks, energy_budget)
            
            # Adjust energy cost based on task count
            self._energy_cost = 5.0 + (len(tasks) * 0.5)
            
            # Log the duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Planned {len(tasks)} reflection tasks for user {user_id} in {duration:.2f}s")
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to plan reflection tasks: {str(e)}")
            raise PlannerError(f"Failed to plan reflection tasks: {str(e)}")
    
    def get_energy_cost(self) -> float:
        """Get the energy cost of the last planning operation.
        
        Returns:
            Energy cost
        """
        return self._energy_cost
    
    def _create_task_from_gap(self, gap: KnowledgeGap) -> Optional[ReflectionTask]:
        """Create a reflection task from a knowledge gap.
        
        Args:
            gap: The knowledge gap
            
        Returns:
            Reflection task or None
        """
        # Map gap types to task types
        task_mapping = {
            "coverage": "topic_expansion",
            "depth": "abstraction_generation",
            "connectivity": "relation_discovery",
            "timeliness": "knowledge_pruning",
            "consistency": "content_verification"
        }
        
        # Get task type
        task_type = task_mapping.get(gap.type)
        if not task_type:
            return None
            
        # Check for potential innovation opportunities in depth gaps
        if gap.type == "depth" and self._is_synthesis_candidate(gap):
            task_type = "concept_synthesis"
            
        # Map severity to priority and energy cost
        if gap.severity >= 0.8:
            priority = 10  # High
            energy_cost = 30.0
        elif gap.severity >= 0.5:
            priority = 5   # Medium
            energy_cost = 20.0
        else:
            priority = 1   # Low
            energy_cost = 10.0
            
        # Prepare parameters
        parameters = {
            "gap_id": gap.id,
            "description": gap.description,
            "severity": gap.severity
        }
        
        # Add topic_id if present
        if gap.topic_id:
            parameters["topic_id"] = gap.topic_id
            
        # Add related_node_ids if present
        if gap.related_node_ids:
            parameters["node_ids"] = gap.related_node_ids
            
        # Add synthesis type if applicable
        if task_type == "concept_synthesis":
            parameters["synthesis_type"] = self._determine_synthesis_type(gap)
            parameters["target_level"] = self._determine_target_abstraction_level(gap)
            
        # Create target node IDs list
        target_node_ids = gap.related_node_ids.copy() if gap.related_node_ids else []
        
        # Create the task
        task = ReflectionTask(
            type=task_type,
            priority=priority,
            energy_cost=energy_cost,
            parameters=parameters,
            target_node_ids=target_node_ids
        )
        
        return task
        
    def _is_synthesis_candidate(self, gap: KnowledgeGap) -> bool:
        """Determine if a gap is a good candidate for concept synthesis.
        
        Args:
            gap: The knowledge gap
            
        Returns:
            True if the gap is a good candidate for synthesis
        """
        # Keywords that suggest synthesis opportunity
        synthesis_keywords = [
            "synthesis", "combine", "integration", "relationship", "connection",
            "synergy", "analogy", "transform", "associate", "link", "blend",
            "innovation", "novel", "cross-domain"
        ]
        
        # Check description for keywords
        if gap.description:
            description_lower = gap.description.lower()
            if any(keyword in description_lower for keyword in synthesis_keywords):
                return True
                
        # Check if there are enough related nodes (need at least 2 for synthesis)
        if gap.related_node_ids and len(gap.related_node_ids) >= 2:
            return True
            
        # Default to false - use abstraction generation instead
        return False
        
    def _determine_synthesis_type(self, gap: KnowledgeGap) -> SynthesisType:
        """Determine the appropriate synthesis type for a gap.
        
        Args:
            gap: The knowledge gap
            
        Returns:
            The synthesis type
        """
        from forest.models import SynthesisType
        
        # Default synthesis type
        default_type = SynthesisType.INTEGRATIVE
        
        # If no description, return default
        if not gap.description:
            return default_type
            
        # Check for keywords that suggest specific synthesis types
        description_lower = gap.description.lower()
        
        if any(term in description_lower for term in ["analo", "similar", "metaphor", "like"]):
            return SynthesisType.ANALOGICAL
            
        if any(term in description_lower for term in ["integrat", "combin", "merge", "join"]):
            return SynthesisType.INTEGRATIVE
            
        if any(term in description_lower for term in ["transform", "evolve", "adapt", "change"]):
            return SynthesisType.TRANSFORMATIONAL
            
        if any(term in description_lower for term in ["dialect", "thesis", "antithesis", "conflict", "opposing", "contrary"]):
            return SynthesisType.DIALECTICAL
            
        if any(term in description_lower for term in ["blend", "mix", "hybrid"]):
            return SynthesisType.CONCEPTUAL_BLENDING
            
        # Default to integrative if no specific type detected
        return default_type
        
    def _determine_target_abstraction_level(self, gap: KnowledgeGap) -> int:
        """Determine the target abstraction level for synthesis.
        
        Args:
            gap: The knowledge gap
            
        Returns:
            The target abstraction level (3-5)
        """
        from forest.models import AbstractionLevel
        
        # Default to Rule level
        default_level = AbstractionLevel.RULE
        
        # If no description, return default
        if not gap.description:
            return default_level
            
        # Check for keywords that suggest higher abstraction levels
        description_lower = gap.description.lower()
        
        if any(term in description_lower for term in ["paradigm", "framework", "worldview", "philosophy"]):
            return AbstractionLevel.PARADIGM
            
        if any(term in description_lower for term in ["principle", "theory", "model", "law"]):
            return AbstractionLevel.PRINCIPLE
            
        # Default to rule level
        return default_level
    
    def _create_system_health_tasks(self, analysis_results: Dict[str, Any]) -> List[ReflectionTask]:
        """Create tasks for maintaining system health.
        
        Args:
            analysis_results: Analysis results
            
        Returns:
            List of system health tasks
        """
        tasks = []
        
        # Check if node pruning is needed
        structure = analysis_results.get("structure", {})
        node_count = structure.get("node_count", 0)
        
        # If we have many nodes, consider pruning
        if node_count > 50:
            tasks.append(
                ReflectionTask(
                    type="knowledge_lifecycle_management",
                    priority=3,  # Medium-low priority
                    energy_cost=15.0,
                    parameters={
                        "operation": "prune_low_importance",
                        "threshold": settings.knowledge_lifecycle.node_dormancy_threshold,
                        "description": "Prune low-importance nodes to maintain knowledge quality"
                    }
                )
            )
            
        # Check if importance redistribution is needed
        if node_count > 20:
            tasks.append(
                ReflectionTask(
                    type="importance_redistribution",
                    priority=2,  # Low priority
                    energy_cost=10.0,
                    parameters={
                        "description": "Redistribute importance scores across knowledge graph"
                    }
                )
            )
            
        # Check if learning strategy adaptation is needed
        if len(analysis_results.get("recommendations", [])) > 0:
            tasks.append(
                ReflectionTask(
                    type="learning_strategy_adaptation",
                    priority=4,  # Medium priority
                    energy_cost=8.0,
                    parameters={
                        "description": "Adapt learning strategies based on analysis",
                        "recommendations": analysis_results.get("recommendations", [])
                    }
                )
            )
            
        return tasks
    
    def _filter_tasks_by_energy(self, 
                             tasks: List[ReflectionTask], 
                             energy_budget: float) -> List[ReflectionTask]:
        """Filter tasks based on available energy budget.
        
        Args:
            tasks: List of tasks
            energy_budget: Available energy
            
        Returns:
            Filtered list of tasks
        """
        # Sort tasks by priority (high to low)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        # Keep adding tasks until we exceed the budget
        filtered_tasks = []
        remaining_energy = energy_budget
        
        for task in sorted_tasks:
            if task.energy_cost <= remaining_energy:
                filtered_tasks.append(task)
                remaining_energy -= task.energy_cost
            else:
                # Stop adding tasks if we don't have enough energy
                break
                
        logger.info(f"Filtered tasks from {len(tasks)} to {len(filtered_tasks)} based on energy budget {energy_budget}")
        
        return filtered_tasks
