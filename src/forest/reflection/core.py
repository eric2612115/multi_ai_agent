"""Core reflection system implementation.

This module provides the main ReflectionSystem class that coordinates the
OODA (Observe, Orient, Decide, Act) reflection cycle.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from src.forest.models import (
    ReflectionCycle, ReflectionStage, SystemStateSnapshot, 
    ReflectionTask, StrategyAdjustment, KnowledgeGap,
    StringId
)
from src.forest.reflection.observer import SystemObserver
from src.forest.reflection.analyzer import KnowledgeAnalyzer
from src.forest.reflection.planner import ReflectionPlanner
from src.forest.reflection.task_executor import TaskExecutor
from src.forest.reflection.gap_finder import KnowledgeGapFinder
from src.forest.energy.manager_combined import EnergyManager
from src.forest.lifecycle.manager_combined import LifecycleManager
from src.forest.abstraction.generator_combined import AbstractionGenerator
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import ReflectionError

settings = get_settings()
logger = logging.getLogger(__name__)

class ReflectionSystem:
    """Main reflection system that coordinates the OODA reflection cycle."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                energy_manager: Optional[EnergyManager] = None,
                lifecycle_manager: Optional[LifecycleManager] = None,
                abstraction_generator: Optional[AbstractionGenerator] = None):
        """Initialize the reflection system.
        
        Args:
            storage_provider: Optional storage provider
            energy_manager: Optional energy manager
            lifecycle_manager: Optional lifecycle manager
            abstraction_generator: Optional abstraction generator
        """
        self.storage = storage_provider
        self.energy_manager = energy_manager
        self.lifecycle_manager = lifecycle_manager
        self.abstraction_generator = abstraction_generator
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize energy manager if not provided
        if self.energy_manager is None:
            self.energy_manager = EnergyManager(storage_provider=self.storage)
            
        # Initialize sub-components
        self.observer = SystemObserver(storage_provider=self.storage)
        self.analyzer = KnowledgeAnalyzer(storage_provider=self.storage)
        self.gap_finder = KnowledgeGapFinder(storage_provider=self.storage)
        self.planner = ReflectionPlanner(storage_provider=self.storage)
        
        # Initialize executor with integrated components
        self.executor = TaskExecutor(
            storage_provider=self.storage,
            energy_manager=self.energy_manager,
            lifecycle_manager=self.lifecycle_manager,
            abstraction_generator=self.abstraction_generator
        )
        
        # Settings
        self.enable_autonomous = settings.reflection.enable_autonomous
        self.min_nodes_for_cycle = settings.reflection.min_nodes_for_cycle
        self.default_energy_budget = settings.reflection.energy_budget_default
    
    async def start_reflection_cycle(self, 
                                  user_id: str, 
                                  energy_budget: Optional[float] = None,
                                  trigger_source: str = "manual") -> str:
        """Start a reflection cycle for a user.
        
        Args:
            user_id: The user ID to run reflection for
            energy_budget: Optional energy budget for this cycle
            trigger_source: What triggered this reflection (manual, schedule, idle)
            
        Returns:
            The reflection cycle ID
            
        Raises:
            ReflectionError: If reflection fails
        """
        try:
            # Check if reflection is enabled
            if not self.enable_autonomous and trigger_source != "manual":
                logger.info(f"Autonomous reflection is disabled, skipping {trigger_source} trigger")
                return "disabled"
                
            # Check if there are enough nodes to warrant reflection
            node_count = await self._get_node_count(user_id)
            if node_count < self.min_nodes_for_cycle:
                logger.info(f"Not enough nodes ({node_count}) for reflection, minimum is {self.min_nodes_for_cycle}")
                return "insufficient_nodes"
                
            # Check if there's already an active reflection cycle
            active_cycle = await self._get_active_cycle(user_id)
            if active_cycle:
                logger.info(f"Active reflection cycle already exists: {active_cycle}")
                return active_cycle
                
            # Create a new reflection cycle
            cycle_id = await self._create_reflection_cycle(
                user_id=user_id,
                energy_budget=energy_budget or self.default_energy_budget,
                trigger_source=trigger_source
            )
            
            # Start the reflection cycle (without awaiting to avoid blocking)
            asyncio.create_task(self._run_reflection_cycle(cycle_id, user_id))
            
            return cycle_id
            
        except Exception as e:
            logger.error(f"Failed to start reflection cycle: {str(e)}")
            raise ReflectionError(f"Failed to start reflection cycle: {str(e)}")
    
    async def get_reflection_cycle(self, cycle_id: str) -> Dict[str, Any]:
        """Get the current status of a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            
        Returns:
            The reflection cycle data
            
        Raises:
            ReflectionError: If retrieval fails
        """
        try:
            cycle_data = await self.storage.get_document("reflection_cycles", cycle_id)
            if not cycle_data:
                raise ReflectionError(f"Reflection cycle not found: {cycle_id}")
                
            return cycle_data
            
        except Exception as e:
            logger.error(f"Failed to get reflection cycle: {str(e)}")
            raise ReflectionError(f"Failed to get reflection cycle: {str(e)}")
    
    async def get_user_reflection_cycles(self, 
                                      user_id: str, 
                                      limit: int = 10,
                                      status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get reflection cycles for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of cycles to return
            status: Optional filter by status
            
        Returns:
            List of reflection cycles
            
        Raises:
            ReflectionError: If retrieval fails
        """
        try:
            # Build query
            query = {"user_id": user_id}
            
            # Add status filter if provided
            if status:
                query["status"] = status
                
            # Get cycles
            cycles = await self.storage.find_documents(
                collection="reflection_cycles",
                query=query,
                sort=[("start_time", -1)],  # Newest first
                limit=limit
            )
            
            return cycles
            
        except Exception as e:
            logger.error(f"Failed to get user reflection cycles: {str(e)}")
            raise ReflectionError(f"Failed to get user reflection cycles: {str(e)}")
    
    async def cancel_reflection_cycle(self, cycle_id: str) -> bool:
        """Cancel an ongoing reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            
        Returns:
            True if successfully cancelled
            
        Raises:
            ReflectionError: If cancellation fails
        """
        try:
            # Get the cycle
            cycle = await self.storage.get_document("reflection_cycles", cycle_id)
            if not cycle:
                raise ReflectionError(f"Reflection cycle not found: {cycle_id}")
                
            # Check if it's already completed or cancelled
            if cycle.get("status") not in ["in_progress"]:
                logger.info(f"Reflection cycle is already {cycle.get('status')}, cannot cancel")
                return False
                
            # Update the cycle status
            await self.storage.update_document(
                collection="reflection_cycles",
                document_id=cycle_id,
                update_data={
                    "status": "cancelled",
                    "end_time": datetime.utcnow(),
                    "error_message": "Cancelled by user"
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel reflection cycle: {str(e)}")
            raise ReflectionError(f"Failed to cancel reflection cycle: {str(e)}")
    
    async def _run_reflection_cycle(self, cycle_id: str, user_id: str) -> None:
        """Run the reflection cycle (OODA loop).
        
        Args:
            cycle_id: The reflection cycle ID
            user_id: The user ID
        """
        try:
            # OBSERVE: Collect state metrics
            await self._update_cycle_stage(cycle_id, ReflectionStage.OBSERVE)
            system_state = await self.observer.collect_system_state(user_id)
            
            # Store the initial system state
            await self._update_cycle_system_state(cycle_id, system_state, "before")
            
            # Track energy consumption
            observe_energy_cost = self.observer.get_energy_cost()
            
            # Consume energy from energy system if available
            if self.energy_manager:
                await self.energy_manager.consume_energy(
                    user_id=user_id,
                    pool="reflection",
                    amount=observe_energy_cost,
                    component="reflection_observer",
                    task_id=cycle_id,
                    reason="Observation phase of reflection cycle"
                )
            
            # Update cycle energy consumption
            energy_consumed = observe_energy_cost
            await self._update_cycle_energy(cycle_id, energy_consumed)
            
            # Get the cycle to check energy budget
            cycle = await self.storage.get_document("reflection_cycles", cycle_id)
            if not cycle:
                logger.error(f"Reflection cycle not found: {cycle_id}")
                return
                
            energy_budget = cycle.get("energy_budget", self.default_energy_budget)
            remaining_energy = energy_budget - energy_consumed
            
            # Skip further stages if not enough energy
            if remaining_energy <= 0:
                logger.warning(f"Not enough energy to continue reflection cycle ({energy_consumed}/{energy_budget})")
                await self._complete_reflection_cycle(cycle_id, "completed_observe_only")
                return
                
            # ORIENT: Analyze and identify patterns/gaps
            await self._update_cycle_stage(cycle_id, ReflectionStage.ORIENT)
            
            # Analyze the knowledge graph
            analysis_results = await self.analyzer.analyze_knowledge_graph(user_id, system_state)
            
            # Identify knowledge gaps
            gaps = await self.gap_finder.identify_knowledge_gaps(user_id, analysis_results)
            
            # Store the identified gaps
            await self._update_cycle_gaps(cycle_id, gaps)
            
            # Calculate energy consumption for this phase
            analyzer_energy = self.analyzer.get_energy_cost()
            gap_finder_energy = self.gap_finder.get_energy_cost()
            orient_energy_cost = analyzer_energy + gap_finder_energy
            
            # Consume energy from energy system if available
            if self.energy_manager:
                await self.energy_manager.consume_energy(
                    user_id=user_id,
                    pool="reflection",
                    amount=orient_energy_cost,
                    component="reflection_analyzer",
                    task_id=cycle_id,
                    reason="Orientation phase of reflection cycle"
                )
            
            # Update energy consumption
            energy_consumed += orient_energy_cost
            await self._update_cycle_energy(cycle_id, energy_consumed)
            
            # Check remaining energy again
            remaining_energy = energy_budget - energy_consumed
            if remaining_energy <= 0:
                logger.warning(f"Not enough energy to continue after Orient stage ({energy_consumed}/{energy_budget})")
                await self._complete_reflection_cycle(cycle_id, "completed_orient_only")
                return
                
            # DECIDE: Plan actions
            await self._update_cycle_stage(cycle_id, ReflectionStage.DECIDE)
            
            # Create a plan
            tasks = await self.planner.plan_reflection_tasks(
                user_id=user_id, 
                analysis_results=analysis_results,
                identified_gaps=gaps,
                energy_budget=remaining_energy
            )
            
            # Calculate planning energy cost
            planning_energy_cost = self.planner.get_energy_cost()
            
            # Consume energy from energy system if available
            if self.energy_manager:
                await self.energy_manager.consume_energy(
                    user_id=user_id,
                    pool="reflection",
                    amount=planning_energy_cost,
                    component="reflection_planner",
                    task_id=cycle_id,
                    reason="Decision phase of reflection cycle"
                )
            
            # Update energy consumption
            energy_consumed += planning_energy_cost
            await self._update_cycle_energy(cycle_id, energy_consumed)
            
            # If no tasks, complete the cycle
            if not tasks:
                logger.info(f"No tasks planned for reflection cycle {cycle_id}")
                await self._complete_reflection_cycle(cycle_id, "completed_no_tasks")
                return
                
            # ACT: Execute the plan
            await self._update_cycle_stage(cycle_id, ReflectionStage.ACT)
            
            # Execute each task in order of priority
            executed_tasks = []
            for task in sorted(tasks, key=lambda t: t.priority, reverse=True):
                # Check if we would exceed the energy budget
                if energy_consumed + task.energy_cost > energy_budget:
                    logger.info(f"Skipping task {task.type} due to energy budget limit")
                    continue
                    
                # Execute the task
                result = await self.executor.execute_task(user_id, task)
                executed_tasks.append({**task.dict(), "result": result})
                
                # Update energy consumption
                energy_consumed += task.energy_cost
                await self._update_cycle_energy(cycle_id, energy_consumed)
                
                # Check if we've reached a stop condition
                if await self._check_stop_condition(cycle_id):
                    logger.info(f"Stop condition reached for cycle {cycle_id}")
                    break
            
            # Store the executed tasks
            await self._update_cycle_tasks(cycle_id, executed_tasks)
            
            # EVALUATE: Collect final state and complete
            await self._update_cycle_stage(cycle_id, ReflectionStage.EVALUATE)
            
            # Collect updated system state
            final_state = await self.observer.collect_system_state(user_id)
            
            # Store the final system state
            await self._update_cycle_system_state(cycle_id, final_state, "after")
            
            # Complete the reflection cycle
            await self._complete_reflection_cycle(cycle_id, "completed")
            
        except Exception as e:
            logger.error(f"Error during reflection cycle {cycle_id}: {str(e)}")
            
            # Update the cycle with error status
            try:
                await self.storage.update_document(
                    collection="reflection_cycles",
                    document_id=cycle_id,
                    update_data={
                        "status": "error",
                        "end_time": datetime.utcnow(),
                        "error_message": str(e)
                    }
                )
            except Exception as update_error:
                logger.error(f"Failed to update cycle with error status: {str(update_error)}")
    
    async def _create_reflection_cycle(self, 
                                    user_id: str, 
                                    energy_budget: float,
                                    trigger_source: str) -> str:
        """Create a new reflection cycle record.
        
        Args:
            user_id: The user ID
            energy_budget: Energy budget for this cycle
            trigger_source: What triggered this reflection
            
        Returns:
            The reflection cycle ID
        """
        # Create the cycle record
        cycle = ReflectionCycle(
            user_id=user_id,
            start_time=datetime.utcnow(),
            energy_budget=energy_budget,
            energy_consumed=0.0,
            current_stage=ReflectionStage.OBSERVE,
            status="in_progress",
            identified_gaps=[],
            executed_tasks=[],
        )
        
        # Save to database
        cycle_dict = cycle.dict(by_alias=True, exclude_none=True)
        cycle_id = await self.storage.save_document("reflection_cycles", cycle_dict)
        
        logger.info(f"Created reflection cycle {cycle_id} for user {user_id} (trigger: {trigger_source})")
        
        return cycle_id
    
    async def _update_cycle_stage(self, cycle_id: str, stage: ReflectionStage) -> None:
        """Update the current stage of a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            stage: The new stage
        """
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={"current_stage": stage}
        )
        
        logger.info(f"Reflection cycle {cycle_id} moved to stage: {stage}")
    
    async def _update_cycle_energy(self, cycle_id: str, energy_consumed: float) -> None:
        """Update the energy consumed in a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            energy_consumed: Total energy consumed so far
        """
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={"energy_consumed": energy_consumed}
        )
    
    async def _update_cycle_gaps(self, cycle_id: str, gaps: List[KnowledgeGap]) -> None:
        """Update the identified gaps in a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            gaps: The identified knowledge gaps
        """
        gaps_dicts = [gap.dict(by_alias=True, exclude_none=True) for gap in gaps]
        
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={"identified_gaps": gaps_dicts}
        )
        
        logger.info(f"Reflection cycle {cycle_id} identified {len(gaps)} knowledge gaps")
    
    async def _update_cycle_tasks(self, cycle_id: str, tasks: List[Dict[str, Any]]) -> None:
        """Update the executed tasks in a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            tasks: The executed tasks
        """
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={"executed_tasks": tasks}
        )
        
        logger.info(f"Reflection cycle {cycle_id} executed {len(tasks)} tasks")
    
    async def _update_cycle_system_state(self, 
                                      cycle_id: str, 
                                      state: SystemStateSnapshot,
                                      state_type: str) -> None:
        """Update a system state snapshot in a reflection cycle.
        
        Args:
            cycle_id: The reflection cycle ID
            state: The system state snapshot
            state_type: Either "before" or "after"
        """
        state_dict = state.dict(by_alias=True, exclude_none=True)
        
        field_name = f"system_state_{state_type}"
        
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={field_name: state_dict}
        )
    
    async def _complete_reflection_cycle(self, cycle_id: str, status: str) -> None:
        """Mark a reflection cycle as complete.
        
        Args:
            cycle_id: The reflection cycle ID
            status: The completion status
        """
        await self.storage.update_document(
            collection="reflection_cycles",
            document_id=cycle_id,
            update_data={
                "status": status,
                "end_time": datetime.utcnow()
            }
        )
        
        logger.info(f"Reflection cycle {cycle_id} completed with status: {status}")
    
    async def _check_stop_condition(self, cycle_id: str) -> bool:
        """Check if a reflection cycle should stop early.
        
        Args:
            cycle_id: The reflection cycle ID
            
        Returns:
            True if the cycle should stop
        """
        # Get the current cycle
        cycle = await self.storage.get_document("reflection_cycles", cycle_id)
        if not cycle:
            return True
            
        # Check if it's already marked as completed/errored/cancelled
        if cycle.get("status") not in ["in_progress"]:
            return True
            
        # Can add more stop conditions here
        
        return False
    
    async def _get_active_cycle(self, user_id: str) -> Optional[str]:
        """Check if there's an active reflection cycle for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            The active cycle ID or None
        """
        cycles = await self.storage.find_documents(
            collection="reflection_cycles",
            query={
                "user_id": user_id,
                "status": "in_progress"
            },
            limit=1
        )
        
        if cycles and len(cycles) > 0:
            return str(cycles[0]["_id"])
            
        return None
    
    async def _get_node_count(self, user_id: str) -> int:
        """Get the count of active nodes for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            The number of active nodes
        """
        count = await self.storage.count_documents(
            collection="nodes",
            query={
                "user_id": user_id,
                "status": "active"
            }
        )
        
        return count
    
    async def should_trigger_reflection(self, user_id: str) -> bool:
        """Check if reflection should be triggered based on system state.
        
        Args:
            user_id: The user ID
            
        Returns:
            True if reflection should be triggered
        """
        # Check if autonomous reflection is enabled
        if not self.enable_autonomous:
            return False
            
        # Check if there's already an active reflection cycle
        active_cycle = await self._get_active_cycle(user_id)
        if active_cycle:
            return False
            
        # Check if there are enough nodes
        node_count = await self._get_node_count(user_id)
        if node_count < self.min_nodes_for_cycle:
            return False
            
        # Check last reflection time
        last_cycle = await self._get_last_completed_cycle(user_id)
        if last_cycle:
            # Calculate time since last reflection
            last_time = last_cycle.get("end_time")
            if last_time:
                time_since = datetime.utcnow() - last_time
                min_interval = timedelta(hours=settings.reflection.cycle_interval_hours)
                
                if time_since < min_interval:
                    return False
                    
        # All checks passed, reflection should be triggered
        return True
    
    async def _get_last_completed_cycle(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recently completed reflection cycle for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            The most recent completed cycle or None
        """
        cycles = await self.storage.find_documents(
            collection="reflection_cycles",
            query={
                "user_id": user_id,
                "status": {"$in": ["completed", "completed_no_tasks", "completed_observe_only", "completed_orient_only"]}
            },
            sort=[("end_time", -1)],  # Latest first
            limit=1
        )
        
        if cycles and len(cycles) > 0:
            return cycles[0]
            
        return None
