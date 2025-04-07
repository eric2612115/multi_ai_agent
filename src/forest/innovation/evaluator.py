"""Innovation evaluator for the knowledge forest.

This module implements the evaluation framework for assessing the quality
and value of synthesized concepts in the innovation mechanism.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.forest.models import Node, StringId, ConceptSynthesisResult
from src.forest.innovation.models import InnovationEvaluation, InnovationCriterion
from src.storage.mongodb import MongoDBProvider
from src.ai.base import TextGenerationModel
from src.ai.factory import get_text_generation_model
from src.common.base_service import BaseService
from src.common.decorators import track_energy, handle_errors, log_operation
from src.common.exceptions import EvaluationError

logger = logging.getLogger(__name__)


class InnovationEvaluator(BaseService):
    """Evaluates synthesized concepts using multiple criteria.
    
    This service assesses the quality and value of innovations created
    through concept synthesis, helping to identify the most promising
    new concepts.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the innovation evaluator.
        
        Args:
            storage_provider: Optional storage provider
            text_model: Optional text generation model for evaluation
        """
        super().__init__("innovation_evaluator", storage_provider)
        self.text_model = text_model
        
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing innovation evaluator")
    
    @track_energy(15.0)
    @handle_errors(EvaluationError)
    @log_operation("evaluate_concept")
    async def evaluate_concept(self, 
                           user_id: str,
                           concept_id: StringId,
                           evaluator: str = "ai") -> InnovationEvaluation:
        """Evaluate a concept using multiple criteria.
        
        Args:
            user_id: The user ID
            concept_id: The concept to evaluate
            evaluator: Who/what is performing the evaluation
            
        Returns:
            Evaluation result
            
        Raises:
            EvaluationError: If evaluation fails
        """
        # Reset energy tracking for this operation
        self.reset_energy_tracking()
        
        try:
            # Get the concept node
            concept = await self.storage.get_document("nodes", concept_id)
            if not concept:
                raise EvaluationError(f"Concept node {concept_id} not found")
                
            # Get source concepts for context
            source_ids = concept.get("abstraction_source_ids", [])
            source_concepts = []
            
            for source_id in source_ids:
                source = await self.storage.get_document("nodes", source_id)
                if source:
                    source_concepts.append({
                        "id": source_id,
                        "label": source.get("label", "Unknown"),
                        "summary": source.get("summary", "")
                    })
            
            # Evaluate the concept
            criteria_scores = await self._generate_evaluation_scores(
                concept,
                source_concepts
            )
            
            # Create evaluation record
            evaluation = InnovationEvaluation(
                concept_id=concept_id,
                evaluator=evaluator,
                criteria_scores=criteria_scores,
                timestamp=datetime.utcnow()
            )
            
            # Save evaluation to database
            eval_id = await self.storage.save_document(
                "innovation_evaluations", 
                evaluation.model_dump(exclude={"id"})
            )
            evaluation.id = StringId(eval_id)
            
            # Record in innovation history
            history_entry = {
                "user_id": user_id,
                "activity_type": "evaluation",
                "result_concept_id": concept_id,
                "success": True,
                "details": {
                    "evaluation_id": str(eval_id),
                    "overall_score": evaluation.overall_score,
                    "top_criteria": max(criteria_scores.items(), key=lambda x: x[1])[0]
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            return evaluation
            
        except Exception as e:
            # Record failure in innovation history
            history_entry = {
                "user_id": user_id,
                "activity_type": "evaluation",
                "result_concept_id": concept_id,
                "success": False,
                "details": {
                    "error": str(e)
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            raise EvaluationError(f"Failed to evaluate concept: {str(e)}")
    
    @track_energy(25.0)
    @handle_errors(EvaluationError)
    @log_operation("evaluate_synthesis_result")
    async def evaluate_synthesis_result(self, 
                                    user_id: str,
                                    result: ConceptSynthesisResult,
                                    evaluator: str = "ai") -> Dict[str, float]:
        """Evaluate a synthesis result directly.
        
        This is used for evaluating concepts before they are added to the
        knowledge graph.
        
        Args:
            user_id: The user ID
            result: The synthesis result to evaluate
            evaluator: Who/what is performing the evaluation
            
        Returns:
            Dictionary of evaluation scores
            
        Raises:
            EvaluationError: If evaluation fails
        """
        # Reset energy tracking for this operation
        self.reset_energy_tracking()
        
        try:
            # Get source concepts for context
            source_concepts = []
            for source_id in result.source_concept_ids:
                source = await self.storage.get_document("nodes", source_id)
                if source:
                    source_concepts.append({
                        "id": source_id,
                        "label": source.get("label", "Unknown"),
                        "summary": source.get("summary", "")
                    })
            
            # Create a temporary concept structure for evaluation
            concept = {
                "label": result.new_concept_label,
                "summary": result.new_concept_summary,
                "abstraction_level": result.new_concept_abstraction_level
            }
            
            # Evaluate the concept
            criteria_scores = await self._generate_evaluation_scores(
                concept,
                source_concepts
            )
            
            # Calculate overall score
            overall_score = sum(criteria_scores.values()) / len(criteria_scores) if criteria_scores else 0.0
            
            # Record in innovation history
            history_entry = {
                "user_id": user_id,
                "activity_type": "evaluation",
                "synthesis_type": result.synthesis_type,
                "source_concept_ids": result.source_concept_ids,
                "success": True,
                "details": {
                    "concept_label": result.new_concept_label,
                    "overall_score": overall_score,
                    "top_criteria": max(criteria_scores.items(), key=lambda x: x[1])[0] if criteria_scores else None
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            return criteria_scores
            
        except Exception as e:
            # Record failure in innovation history
            history_entry = {
                "user_id": user_id,
                "activity_type": "evaluation",
                "synthesis_type": result.synthesis_type,
                "source_concept_ids": result.source_concept_ids,
                "success": False,
                "details": {
                    "error": str(e),
                    "concept_label": result.new_concept_label
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            raise EvaluationError(f"Failed to evaluate synthesis result: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(EvaluationError)
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
            EvaluationError: If retrieval fails
        """
        # Reset energy tracking for this operation
        self.reset_energy_tracking()
        
        try:
            # Calculate the cutoff date
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=time_window_days)
            
            # Get evaluations for this user in the time window
            pipeline = [
                # Join evaluations with nodes
                {
                    "$lookup": {
                        "from": "nodes",
                        "localField": "concept_id",
                        "foreignField": "_id",
                        "as": "concept"
                    }
                },
                # Filter by user and time
                {
                    "$match": {
                        "concept.user_id": user_id,
                        "timestamp": {"$gte": cutoff_date}
                    }
                },
                # Project relevant fields
                {
                    "$project": {
                        "concept_id": 1,
                        "concept_label": {"$arrayElemAt": ["$concept.label", 0]},
                        "overall_score": 1,
                        "criteria_scores": 1,
                        "timestamp": 1
                    }
                },
                # Sort by overall score (descending)
                {
                    "$sort": {"overall_score": -1}
                },
                # Limit results
                {
                    "$limit": limit
                }
            ]
            
            results = await self.storage.aggregate("innovation_evaluations", pipeline)
            
            return list(results)
            
        except Exception as e:
            raise EvaluationError(f"Failed to get top innovations: {str(e)}")
    
    async def _generate_evaluation_scores(self, 
                                      concept: Dict[str, Any],
                                      source_concepts: List[Dict[str, Any]]) -> Dict[InnovationCriterion, float]:
        """Generate evaluation scores for a concept.
        
        Args:
            concept: The concept to evaluate
            source_concepts: List of source concepts for context
            
        Returns:
            Dictionary of evaluation criteria and scores
        """
        # Prepare the input for evaluation
        concept_label = concept.get("label", "Unknown")
        concept_summary = concept.get("summary", "")
        abstraction_level = concept.get("abstraction_level", 2)
        
        # Create context from source concepts
        source_context = "\n\n".join([
            f"Source Concept: {src['label']}\n{src['summary']}"
            for src in source_concepts[:3]  # Limit to 3 source concepts for brevity
        ])
        
        # Prepare the prompt
        prompt = f"""Evaluate this synthesized concept according to multiple innovation criteria:

Concept: {concept_label}
Summary: {concept_summary}
Abstraction Level: {abstraction_level}

Source Concepts:
{source_context}

Please evaluate this synthesized concept on the following criteria (scale 0.0-1.0):

1. Novelty: How new and original is the concept?
2. Coherence: How internally consistent and well-structured is the concept?
3. Utility: How useful and valuable is the concept?
4. Compatibility: How well does it fit with existing knowledge?
5. Flexibility: How adaptable and extendable is the concept?
6. Simplicity: How elegantly simple is the concept?
7. Explanatory Power: How well does it explain phenomena?
8. Generative Potential: How many new ideas could this concept spawn?

Format your response as follows (include only the JSON, no other text):
```json
{
  "novelty": 0.8,
  "coherence": 0.7,
  "utility": 0.9,
  "compatibility": 0.6,
  "flexibility": 0.7,
  "simplicity": 0.5,
  "explanatory_power": 0.8,
  "generative_potential": 0.9
}
```
"""
        
        # Get the evaluation from the AI model
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Parse the JSON response
        import json
        import re
        
        try:
            # Look for JSON between triple backticks
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find any JSON-like content
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                    
            raw_scores = json.loads(json_str)
            
            # Convert to proper enum keys
            scores = {}
            for key, value in raw_scores.items():
                try:
                    criterion = InnovationCriterion(key.lower())
                    scores[criterion] = min(1.0, max(0.0, float(value)))  # Ensure in 0.0-1.0 range
                except (ValueError, TypeError):
                    # Skip invalid criteria
                    continue
                    
            # Ensure all criteria are present with reasonable defaults
            for criterion in InnovationCriterion:
                if criterion not in scores:
                    scores[criterion] = 0.7  # Default score for missing criteria
                    
            return scores
            
        except Exception as e:
            logger.error(f"Failed to parse evaluation scores: {str(e)}")
            
            # Return default scores
            return {
                InnovationCriterion.NOVELTY: 0.7,
                InnovationCriterion.COHERENCE: 0.7,
                InnovationCriterion.UTILITY: 0.7,
                InnovationCriterion.COMPATIBILITY: 0.7,
                InnovationCriterion.FLEXIBILITY: 0.7,
                InnovationCriterion.SIMPLICITY: 0.7,
                InnovationCriterion.EXPLANATORY_POWER: 0.7,
                InnovationCriterion.GENERATIVE_POTENTIAL: 0.7
            }