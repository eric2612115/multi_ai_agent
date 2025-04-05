"""API layer for the innovation mechanism.

This module provides a high-level API for interacting with the innovation
mechanism of the knowledge forest.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from forest.models import StringId, SynthesisType, AbstractionLevel, ConceptSynthesisResult
from forest.innovation.models import SynthesisTask, SynthesisCandidate, InnovationEvaluation
from forest.innovation.synthesizer import ConceptSynthesizer
from forest.innovation.evaluator import InnovationEvaluator
from storage.mongodb import MongoDBProvider
from common.base_service import BaseService
from common.decorators import track_energy, handle_errors, log_operation
from common.exceptions import InnovationError

logger = logging.getLogger(__name__)


class InnovationAPI(BaseService):
    """High-level API for the innovation mechanism.
    
    This class provides a unified interface for interacting with all aspects
    of the innovation system, including concept synthesis, candidate discovery,
    and innovation evaluation.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                synthesizer: Optional[ConceptSynthesizer] = None,
                evaluator: Optional[InnovationEvaluator] = None):
        """Initialize the innovation API.
        
        Args:
            storage_provider: Optional storage provider
            synthesizer: Optional concept synthesizer
            evaluator: Optional innovation evaluator
        """
        super().__init__("innovation_api", storage_provider)
        self.synthesizer = synthesizer
        self.evaluator = evaluator
        
        # Lazy initialize components if not provided
        if self.synthesizer is None:
            self.synthesizer = ConceptSynthesizer(storage_provider=self.storage)
            
        if self.evaluator is None:
            self.evaluator = InnovationEvaluator(storage_provider=self.storage)
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing innovation API")
        
        # Start the components
        await self.synthesizer.start()
        await self.evaluator.start()
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup."""
        logger.info("Cleaning up innovation API")
        
        # Stop the components
        await self.synthesizer.stop()
        await self.evaluator.stop()
    
    @track_energy(5.0)
    @handle_errors(InnovationError)
    @log_operation("create_synthesis_task")
    async def create_synthesis_task(self,
                                user_id: str,
                                source_concept_ids: List[StringId],
                                synthesis_type: SynthesisType,
                                target_abstraction_level: AbstractionLevel,
                                priority: int = 1) -> SynthesisTask:
        """Create a new synthesis task.
        
        Args:
            user_id: The user ID
            source_concept_ids: List of source concept IDs
            synthesis_type: Type of synthesis to perform
            target_abstraction_level: Target abstraction level for the new concept
            priority: Task priority (1-5, higher numbers = higher priority)
            
        Returns:
            The created synthesis task
            
        Raises:
            InnovationError: If task creation fails
        """
        try:
            # Create the task
            task = SynthesisTask(
                user_id=user_id,
                source_concept_ids=source_concept_ids,
                synthesis_type=synthesis_type,
                target_abstraction_level=target_abstraction_level,
                priority=priority
            )
            
            # Save to database
            task_id = await self.storage.save_document("synthesis_tasks", task.model_dump(exclude={"id"}))
            task.id = StringId(task_id)
            
            return task
            
        except Exception as e:
            raise InnovationError(f"Failed to create synthesis task: {str(e)}")
    
    @track_energy(30.0)
    @handle_errors(InnovationError)
    @log_operation("execute_synthesis_task")
    async def execute_synthesis_task(self, task_id: StringId) -> ConceptSynthesisResult:
        """Execute a synthesis task.
        
        Args:
            task_id: ID of the synthesis task to execute
            
        Returns:
            Result of concept synthesis
            
        Raises:
            InnovationError: If synthesis fails
        """
        try:
            # Get the task
            task_doc = await self.storage.get_document("synthesis_tasks", task_id)
            if not task_doc:
                raise InnovationError(f"Synthesis task {task_id} not found")
                
            # Convert to task object
            task = SynthesisTask(
                id=task_id,
                user_id=task_doc["user_id"],
                source_concept_ids=task_doc["source_concept_ids"],
                synthesis_type=task_doc["synthesis_type"],
                target_abstraction_level=task_doc["target_abstraction_level"],
                creation_timestamp=task_doc["creation_timestamp"],
                status=task_doc["status"],
                priority=task_doc.get("priority", 1)
            )
            
            # Check if task is already completed or in progress
            if task.status == "completed":
                # Get the result concept
                result_concept_id = task_doc.get("result_concept_id")
                if result_concept_id:
                    # Try to retrieve the result
                    results = await self.storage.find_documents(
                        "synthesis_results",
                        {"concept_id": result_concept_id},
                        limit=1
                    )
                    
                    if results and len(results) > 0:
                        return ConceptSynthesisResult(**results[0])
                
                raise InnovationError(f"Task {task_id} is already completed but result not found")
                
            elif task.status == "in_progress":
                raise InnovationError(f"Task {task_id} is already in progress")
            
            # Execute the task
            result = await self.synthesizer.synthesize_concept(task)
            
            return result
            
        except Exception as e:
            if not isinstance(e, InnovationError):
                raise InnovationError(f"Failed to execute synthesis task: {str(e)}")
            raise
    
    @track_energy(15.0)
    @handle_errors(InnovationError)
    @log_operation("find_synthesis_candidates")
    async def find_synthesis_candidates(self,
                                    user_id: str,
                                    topic_id: Optional[str] = None,
                                    max_candidates: int = 10) -> List[SynthesisCandidate]:
        """Find potential candidates for concept synthesis.
        
        Args:
            user_id: The user ID
            topic_id: Optional topic ID to limit search
            max_candidates: Maximum number of candidates to return
            
        Returns:
            List of synthesis candidates
            
        Raises:
            InnovationError: If candidate search fails
        """
        try:
            return await self.synthesizer.find_synthesis_candidates(
                user_id=user_id,
                topic_id=topic_id,
                max_candidates=max_candidates
            )
            
        except Exception as e:
            raise InnovationError(f"Failed to find synthesis candidates: {str(e)}")
    
    @track_energy(15.0)
    @handle_errors(InnovationError)
    @log_operation("evaluate_concept")
    async def evaluate_concept(self,
                           user_id: str,
                           concept_id: StringId) -> InnovationEvaluation:
        """Evaluate a synthesized concept.
        
        Args:
            user_id: The user ID
            concept_id: The concept to evaluate
            
        Returns:
            Evaluation result
            
        Raises:
            InnovationError: If evaluation fails
        """
        try:
            return await self.evaluator.evaluate_concept(
                user_id=user_id,
                concept_id=concept_id
            )
            
        except Exception as e:
            raise InnovationError(f"Failed to evaluate concept: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(InnovationError)
    @log_operation("get_synthesis_tasks")
    async def get_synthesis_tasks(self,
                              user_id: str,
                              status: Optional[str] = None,
                              limit: int = 20) -> List[SynthesisTask]:
        """Get synthesis tasks for a user.
        
        Args:
            user_id: The user ID
            status: Optional status filter (pending, in_progress, completed, failed)
            limit: Maximum number of tasks to return
            
        Returns:
            List of synthesis tasks
            
        Raises:
            InnovationError: If task retrieval fails
        """
        try:
            # Build query
            query = {"user_id": user_id}
            if status:
                query["status"] = status
                
            # Get tasks
            task_docs = await self.storage.find_documents(
                "synthesis_tasks",
                query,
                sort=[("creation_timestamp", -1)],
                limit=limit
            )
            
            # Convert to task objects
            tasks = []
            for doc in task_docs:
                task = SynthesisTask(
                    id=doc["_id"],
                    user_id=doc["user_id"],
                    source_concept_ids=doc["source_concept_ids"],
                    synthesis_type=doc["synthesis_type"],
                    target_abstraction_level=doc["target_abstraction_level"],
                    creation_timestamp=doc["creation_timestamp"],
                    completion_timestamp=doc.get("completion_timestamp"),
                    status=doc["status"],
                    result_concept_id=doc.get("result_concept_id"),
                    priority=doc.get("priority", 1)
                )
                tasks.append(task)
                
            return tasks
            
        except Exception as e:
            raise InnovationError(f"Failed to get synthesis tasks: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(InnovationError)
    @log_operation("get_top_innovations")
    async def get_top_innovations(self,
                              user_id: str,
                              time_window_days: int = 30,
                              limit: int = 10) -> List[Dict[str, Any]]:
        """Get the top innovations based on evaluation scores.
        
        Args:
            user_id: The user ID
            time_window_days: Time window for innovations in days
            limit: Maximum number of innovations to return
            
        Returns:
            List of top innovations with scores
            
        Raises:
            InnovationError: If retrieval fails
        """
        try:
            return await self.evaluator.get_top_innovations(
                user_id=user_id,
                time_window_days=time_window_days,
                limit=limit
            )
            
        except Exception as e:
            raise InnovationError(f"Failed to get top innovations: {str(e)}")
    
    @track_energy(5.0)
    @handle_errors(InnovationError)
    @log_operation("get_innovation_history")
    async def get_innovation_history(self,
                                 user_id: str,
                                 activity_type: Optional[str] = None,
                                 limit: int = 20) -> List[Dict[str, Any]]:
        """Get innovation activity history for a user.
        
        Args:
            user_id: The user ID
            activity_type: Optional activity type filter
            limit: Maximum number of records to return
            
        Returns:
            List of innovation history records
            
        Raises:
            InnovationError: If retrieval fails
        """
        try:
            # Build query
            query = {"user_id": user_id}
            if activity_type:
                query["activity_type"] = activity_type
                
            # Get history records
            history = await self.storage.find_documents(
                "innovation_history",
                query,
                sort=[("timestamp", -1)],
                limit=limit
            )
            
            return history
            
        except Exception as e:
            raise InnovationError(f"Failed to get innovation history: {str(e)}")
    
    @track_energy(20.0)
    @handle_errors(InnovationError)
    @log_operation("synthesize_and_evaluate")
    async def synthesize_and_evaluate(self,
                                  user_id: str,
                                  source_concept_ids: List[StringId],
                                  synthesis_type: SynthesisType,
                                  target_abstraction_level: AbstractionLevel) -> Dict[str, Any]:
        """Create, execute, and evaluate a synthesis task in one operation.
        
        This is a convenience method that combines multiple steps into one.
        
        Args:
            user_id: The user ID
            source_concept_ids: List of source concept IDs
            synthesis_type: Type of synthesis to perform
            target_abstraction_level: Target abstraction level for the new concept
            
        Returns:
            Dictionary with task, result, and evaluation
            
        Raises:
            InnovationError: If any step fails
        """
        try:
            # Create the task
            task = await self.create_synthesis_task(
                user_id=user_id,
                source_concept_ids=source_concept_ids,
                synthesis_type=synthesis_type,
                target_abstraction_level=target_abstraction_level
            )
            
            # Execute the task
            result = await self.execute_synthesis_task(task.id)
            
            # Evaluate the result
            if result.id:
                evaluation = await self.evaluate_concept(user_id, result.id)
                
                return {
                    "task": task,
                    "result": result,
                    "evaluation": evaluation
                }
            else:
                return {
                    "task": task,
                    "result": result,
                    "evaluation": None
                }
            
        except Exception as e:
            if not isinstance(e, InnovationError):
                raise InnovationError(f"Failed to synthesize and evaluate: {str(e)}")
            raise