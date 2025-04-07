"""Reflection task planner for reflection cycle.

This module provides functionality for planning reflection tasks,
which forms the Decide phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.forest.models import (
    ReflectionTask, KnowledgeGap, SynthesisType, AbstractionLevel,
    StringId
)
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import PlannerError

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
            
            # First, retrieve relevant context for better planning
            await self._enhance_planning_with_context(user_id, analysis_results, identified_gaps)
            
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
            
            # Add quality monitoring tasks if needed
            quality_tasks = await self._create_quality_monitoring_tasks(user_id, analysis_results)
            tasks.extend(quality_tasks)
            
            # Filter tasks based on energy budget and optimize task set
            tasks = await self._optimize_and_filter_tasks(tasks, energy_budget, user_id)
            
            # Adjust energy cost based on task count
            self._energy_cost = 5.0 + (len(tasks) * 0.5)
            
            # Log the duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Planned {len(tasks)} reflection tasks for user {user_id} in {duration:.2f}s")
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to plan reflection tasks: {str(e)}")
            raise PlannerError(f"Failed to plan reflection tasks: {str(e)}")
            
    async def _enhance_planning_with_context(self, 
                                        user_id: str, 
                                        analysis_results: Dict[str, Any],
                                        gaps: List[KnowledgeGap]) -> None:
        """Enhance planning with relevant context from the knowledge forest.
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            gaps: Identified knowledge gaps
        """
        try:
            # Import here to avoid circular imports
            from src.services.retrieval_service import RetrievalService
            
            # Create retrieval service
            retrieval_service = RetrievalService(storage_provider=self.storage)
            
            # For each gap, try to enhance with context
            for gap in gaps:
                # Skip if no description
                if not gap.description:
                    continue
                    
                # Retrieve relevant context for this gap
                context_items = await retrieval_service.retrieve_relevant_context(
                    user_id=user_id, 
                    query_text=gap.description,
                    k=5,  # Limit to 5 most relevant items
                    min_similarity=0.65
                )
                
                # Enhance gap with context
                if context_items:
                    # Store node IDs if not already present
                    if not gap.related_node_ids:
                        gap.related_node_ids = []
                        
                    # Add relevant node IDs from context
                    for item in context_items:
                        node_id = item.get("node_id")
                        if node_id and node_id not in gap.related_node_ids:
                            gap.related_node_ids.append(node_id)
                            
                    # Set the gap's topic if not already set
                    if not gap.topic_id and context_items[0].get("topic_id") != "unknown":
                        gap.topic_id = context_items[0].get("topic_id")
                        
                    logger.debug(f"Enhanced gap {gap.id} with {len(context_items)} context items")
                    
        except Exception as e:
            # Don't fail the whole planning process if context enhancement fails
            logger.warning(f"Failed to enhance planning with context: {str(e)}")
            
    async def _create_quality_monitoring_tasks(self, 
                                          user_id: str, 
                                          analysis_results: Dict[str, Any]) -> List[ReflectionTask]:
        """Create tasks for quality monitoring based on analysis results.
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            
        Returns:
            List of quality monitoring tasks
        """
        tasks = []
        
        # Check content quality issues
        content_quality = analysis_results.get("content_quality", {})
        avg_certainty = content_quality.get("avg_certainty", 1.0)
        verified_ratio = content_quality.get("verified_ratio", 1.0)
        
        # Create content verification task if needed
        if avg_certainty < 0.6 or verified_ratio < 0.3:
            tasks.append(
                ReflectionTask(
                    type="content_verification",
                    priority=6,  # Medium-high priority
                    energy_cost=15.0,
                    parameters={
                        "min_certainty": avg_certainty,
                        "verified_ratio": verified_ratio,
                        "description": "Verify content with low certainty scores"
                    }
                )
            )
        
        # Check for structural issues
        structure = analysis_results.get("structure", {})
        isolated_component_count = structure.get("isolated_component_count", 0)
        
        # Create task to fix isolated components
        if isolated_component_count > 2:
            tasks.append(
                ReflectionTask(
                    type="relation_discovery",
                    priority=5,  # Medium priority
                    energy_cost=20.0,
                    parameters={
                        "focus": "isolated_components",
                        "count": isolated_component_count,
                        "description": f"Connect {isolated_component_count} isolated nodes to the main graph"
                    }
                )
            )
                
        # Check for abstraction balance issues
        abstraction_balance = structure.get("abstraction_balance", 1.0)
        abstraction_distribution = structure.get("abstraction_distribution", {})
        
        # Convert string keys to integers if needed
        if abstraction_distribution and all(isinstance(k, str) for k in abstraction_distribution.keys()):
            abstraction_distribution = {int(k): v for k, v in abstraction_distribution.items()}
        
        # Check if we're missing higher-level abstractions
        has_principles = abstraction_distribution.get(4, 0) > 0
        has_paradigms = abstraction_distribution.get(5, 0) > 0
        
        if abstraction_balance < 0.4 and not has_principles and not has_paradigms:
            tasks.append(
                ReflectionTask(
                    type="abstraction_generation",
                    priority=4,  # Medium priority
                    energy_cost=25.0,
                    parameters={
                        "target_level": 4,  # Principle level
                        "description": "Generate higher-level abstractions across the knowledge graph"
                    }
                )
            )
        
        return tasks
    
    async def _optimize_and_filter_tasks(self,
                                    tasks: List[ReflectionTask],
                                    energy_budget: float,
                                    user_id: str) -> List[ReflectionTask]:
        """Optimize and filter tasks for maximum impact within energy constraints.
        
        Args:
            tasks: List of tasks
            energy_budget: Available energy budget
            user_id: The user ID
            
        Returns:
            Optimized and filtered list of tasks
        """
        # If budget is sufficient for all tasks, return all tasks
        total_energy = sum(task.energy_cost for task in tasks)
        if total_energy <= energy_budget:
            return tasks
        
        # Otherwise, we need to optimize
        # First, group tasks by type
        task_groups = {}
        for task in tasks:
            if task.type not in task_groups:
                task_groups[task.type] = []
            task_groups[task.type].append(task)
        
        # For types with multiple tasks, merge or select the highest priority ones
        optimized_tasks = []
        for task_type, group_tasks in task_groups.items():
            if len(group_tasks) <= 1:
                # If only one task of this type, keep it
                optimized_tasks.extend(group_tasks)
            else:
                # If multiple tasks of the same type, try to merge or select best
                if task_type == "topic_expansion":
                    # Merge topic expansion tasks
                    merged_task = self._merge_topic_expansion_tasks(group_tasks)
                    optimized_tasks.append(merged_task)
                elif task_type == "relation_discovery":
                    # Merge relation discovery tasks
                    merged_task = self._merge_relation_tasks(group_tasks)
                    optimized_tasks.append(merged_task)
                elif task_type == "content_verification":
                    # Take the highest priority content verification task
                    best_task = max(group_tasks, key=lambda t: t.priority)
                    optimized_tasks.append(best_task)
                else:
                    # For other types, take the highest priority task
                    best_task = max(group_tasks, key=lambda t: t.priority)
                    optimized_tasks.append(best_task)
        
        # Now filter the optimized tasks by priority and energy budget
        # Sort by priority (high to low)
        sorted_tasks = sorted(optimized_tasks, key=lambda t: t.priority, reverse=True)
        
        # Keep adding tasks until we exceed the budget
        filtered_tasks = []
        remaining_energy = energy_budget
        
        for task in sorted_tasks:
            if task.energy_cost <= remaining_energy:
                filtered_tasks.append(task)
                remaining_energy -= task.energy_cost
            elif remaining_energy > 0 and task.priority >= 8:
                # For very high priority tasks, try to scale down energy cost
                scaled_task = self._scale_down_task(task, remaining_energy)
                if scaled_task:
                    filtered_tasks.append(scaled_task)
                    remaining_energy = 0
        
        logger.info(f"Optimized and filtered tasks from {len(tasks)} to {len(filtered_tasks)} based on energy budget {energy_budget}")
        return filtered_tasks
        
    def _merge_topic_expansion_tasks(self, tasks: List[ReflectionTask]) -> ReflectionTask:
        """Merge multiple topic expansion tasks into one.
        
        Args:
            tasks: List of topic expansion tasks
            
        Returns:
            Merged task
        """
        # Sort by priority
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        # Use the highest priority task as the base
        base_task = sorted_tasks[0]
        
        # Collect all topic IDs and descriptions
        topic_ids = set()
        descriptions = []
        
        for task in tasks:
            if task.parameters.get("topic_id"):
                topic_ids.add(task.parameters["topic_id"])
            if task.parameters.get("description"):
                descriptions.append(task.parameters["description"])
        
        # Prepare merged parameters
        merged_params = base_task.parameters.copy()
        if topic_ids:
            merged_params["topic_ids"] = list(topic_ids)
        if descriptions:
            merged_params["descriptions"] = descriptions
            
        # Create merged task with increased energy cost
        energy_cost = min(base_task.energy_cost * 1.5, sum(t.energy_cost for t in tasks) * 0.8)
        
        return ReflectionTask(
            type="topic_expansion",
            priority=base_task.priority,
            energy_cost=energy_cost,
            parameters=merged_params,
            target_node_ids=[]
        )
        
    def _merge_relation_tasks(self, tasks: List[ReflectionTask]) -> ReflectionTask:
        """Merge multiple relation discovery tasks into one.
        
        Args:
            tasks: List of relation discovery tasks
            
        Returns:
            Merged task
        """
        # Sort by priority
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        # Use the highest priority task as the base
        base_task = sorted_tasks[0]
        
        # Collect all node IDs
        node_ids = set()
        for task in tasks:
            if task.target_node_ids:
                node_ids.update(task.target_node_ids)
        
        # Create merged task with increased energy cost
        energy_cost = min(base_task.energy_cost * 1.5, sum(t.energy_cost for t in tasks) * 0.8)
        
        return ReflectionTask(
            type="relation_discovery",
            priority=base_task.priority,
            energy_cost=energy_cost,
            parameters=base_task.parameters,
            target_node_ids=list(node_ids)
        )
        
    def _scale_down_task(self, task: ReflectionTask, available_energy: float) -> Optional[ReflectionTask]:
        """Scale down a task to fit within available energy.
        
        Args:
            task: The task to scale down
            available_energy: Available energy
            
        Returns:
            Scaled down task or None if not possible
        """
        # Minimum energy needed for any task
        min_energy = 5.0
        
        # If available energy is too low, we can't scale
        if available_energy < min_energy:
            return None
            
        # Create a copy of the task with scaled down energy
        scaled_task = ReflectionTask(
            type=task.type,
            priority=task.priority,
            energy_cost=available_energy,
            parameters=task.parameters.copy(),
            target_node_ids=task.target_node_ids.copy() if task.target_node_ids else []
        )
        
        # Modify parameters based on task type to reflect reduced scope
        if task.type == "topic_expansion":
            scaled_task.parameters["scope"] = "limited"
            scaled_task.parameters["max_nodes"] = 3
        elif task.type == "abstraction_generation":
            scaled_task.parameters["scope"] = "focused"
            scaled_task.parameters["max_abstractions"] = 1
        elif task.type == "relation_discovery":
            scaled_task.parameters["scope"] = "limited"
            scaled_task.parameters["max_relations"] = 5
        
        return scaled_task
    
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
        from src.forest.models import SynthesisType
        
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
        from src.forest.models import AbstractionLevel
        
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
