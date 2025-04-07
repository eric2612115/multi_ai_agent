"""Concept synthesizer for the innovation mechanism.

This module implements different strategies for creating new concepts by
combining existing knowledge nodes in various ways, supporting different
types of concept synthesis: analogical, integrative, transformational,
and dialectical.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.forest.models import (
    Node, StringId, SynthesisType, AbstractionLevel, 
    NodeStatus, RelationshipType, ConceptSynthesisResult
)
from src.forest.innovation.models import SynthesisTask, SynthesisCandidate
from src.storage.mongodb import MongoDBProvider
from src.ai.base import TextGenerationModel
from src.ai.factory import get_text_generation_model
from src.common.base_service import BaseService
from src.common.strategy import Strategy, StrategyManager
from src.common.decorators import track_energy, handle_errors, log_operation
from src.common.exceptions import SynthesisError

logger = logging.getLogger(__name__)


class ConceptSynthesizer(BaseService):
    """Synthesizes new concepts from existing knowledge nodes.
    
    This service implements various strategies for concept synthesis,
    allowing for the creation of innovative concepts through different
    combination methods.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the concept synthesizer.
        
        Args:
            storage_provider: Optional storage provider
            text_model: Optional text generation model for concept synthesis
        """
        super().__init__("concept_synthesizer", storage_provider)
        self.text_model = text_model
        
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
            
        # Create strategy manager for different synthesis types
        self.strategy_manager = StrategyManager[SynthesisType, SynthesisTask, ConceptSynthesisResult]()
        
        # Register strategies
        self.strategy_manager.register(SynthesisType.ANALOGICAL, AnalogicalSynthesizer(self.storage, self.text_model))
        self.strategy_manager.register(SynthesisType.INTEGRATIVE, IntegrativeSynthesizer(self.storage, self.text_model))
        self.strategy_manager.register(SynthesisType.TRANSFORMATIONAL, TransformationalSynthesizer(self.storage, self.text_model))
        self.strategy_manager.register(SynthesisType.DIALECTICAL, DialecticalSynthesizer(self.storage, self.text_model))
        self.strategy_manager.register(SynthesisType.CONCEPTUAL_BLENDING, ConceptualBlendingSynthesizer(self.storage, self.text_model))
        
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing concept synthesizer")
    
    @track_energy(25.0)
    @handle_errors(SynthesisError)
    @log_operation("synthesize_concept")
    async def synthesize_concept(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Synthesize a new concept based on the task specification.
        
        Args:
            task: The synthesis task specification
            
        Returns:
            Result of concept synthesis
            
        Raises:
            SynthesisError: If synthesis fails
        """
        # Reset energy tracking for this operation
        self.reset_energy_tracking()
        
        # Update task status
        task.status = "in_progress"
        await self.storage.update_document("synthesis_tasks", task.id, {"status": "in_progress"})
        
        # Get the appropriate strategy for this synthesis type
        try:
            # Execute the strategy
            result = self.strategy_manager.execute(task.synthesis_type, task)
            
            # Create the node in the knowledge graph
            node_id = await self._create_concept_node(task.user_id, result)
            
            # Create edges connecting source nodes to the new concept
            for source_id in task.source_concept_ids:
                await self._create_concept_relationship(task.user_id, source_id, node_id, task.synthesis_type)
                
            # Update the result with the node ID
            result.id = node_id
            
            # Save the synthesis result
            await self.storage.save_document("synthesis_results", result.model_dump(exclude={"id"}))
            
            # Update task status
            task.status = "completed"
            task.result_concept_id = node_id
            task.completion_timestamp = datetime.utcnow()
            await self.storage.update_document(
                "synthesis_tasks", 
                task.id, 
                {
                    "status": "completed", 
                    "result_concept_id": node_id,
                    "completion_timestamp": datetime.utcnow()
                }
            )
            
            # Record in innovation history
            history_entry = {
                "user_id": task.user_id,
                "activity_type": "synthesis",
                "synthesis_type": task.synthesis_type,
                "source_concept_ids": task.source_concept_ids,
                "result_concept_id": node_id,
                "success": True,
                "details": {
                    "task_id": str(task.id),
                    "target_abstraction_level": task.target_abstraction_level,
                    "evaluation_scores": result.evaluation_scores
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            return result
            
        except Exception as e:
            # Update task status
            task.status = "failed"
            await self.storage.update_document("synthesis_tasks", task.id, {"status": "failed"})
            
            # Record failure in innovation history
            history_entry = {
                "user_id": task.user_id,
                "activity_type": "synthesis",
                "synthesis_type": task.synthesis_type,
                "source_concept_ids": task.source_concept_ids,
                "result_concept_id": None,
                "success": False,
                "details": {
                    "task_id": str(task.id),
                    "error": str(e)
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            # Re-raise as SynthesisError
            raise SynthesisError(f"Failed to synthesize concept: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(SynthesisError)
    @log_operation("find_synthesis_candidates")
    async def find_synthesis_candidates(self, 
                                    user_id: str, 
                                    topic_id: Optional[str] = None,
                                    max_candidates: int = 10,
                                    min_synthesis_potential: float = 0.6) -> List[SynthesisCandidate]:
        """Find potential candidates for concept synthesis.
        
        Args:
            user_id: The user ID
            topic_id: Optional topic ID to limit search
            max_candidates: Maximum number of candidates to return
            min_synthesis_potential: Minimum synthesis potential score (0.0-1.0)
            
        Returns:
            List of synthesis candidates
            
        Raises:
            SynthesisError: If candidate search fails
        """
        # Reset energy tracking for this operation
        self.reset_energy_tracking()
        
        try:
            # Get nodes for analysis
            node_query = {
                "user_id": user_id,
                "status": "active",
                "type": {"$in": ["concept", "abstraction", "topic"]}  # Focus on conceptual nodes
            }
            
            if topic_id:
                node_query["topic_cluster_id"] = topic_id
                
            nodes = await self.storage.find_documents(
                "nodes",
                node_query,
                projection={
                    "_id": 1,
                    "label": 1,
                    "summary": 1,
                    "abstraction_level": 1,
                    "embedding": 1
                },
                limit=100  # Reasonable limit for analysis
            )
            
            if len(nodes) < 2:
                return []
                
            # Find node pairs with potential for synthesis
            candidates = []
            node_ids = [node["_id"] for node in nodes]
            node_map = {str(node["_id"]): node for node in nodes}
            
            # Use embeddings to find similar pairs if available
            if nodes[0].get("embedding") is not None:
                pairs = await self._find_pairs_by_embedding(nodes, max_candidates)
            else:
                # Fallback to random pairs if embeddings not available
                pairs = await self._find_random_pairs(node_ids, max_candidates)
            
            # Analyze each pair
            for node_id1, node_id2 in pairs:
                node1 = node_map.get(str(node_id1))
                node2 = node_map.get(str(node_id2))
                
                if not node1 or not node2:
                    continue
                    
                # Calculate synthesis potential
                potential = await self._analyze_synthesis_potential(
                    user_id,
                    node1,
                    node2
                )
                
                if potential["synthesis_potential"] >= min_synthesis_potential:
                    candidates.append(SynthesisCandidate(
                        source_concept_ids=[node_id1, node_id2],
                        source_concept_labels=[node1.get("label", "Unknown"), node2.get("label", "Unknown")],
                        similarity_score=potential["similarity_score"],
                        difference_score=potential["difference_score"],
                        complementarity_score=potential["complementarity_score"],
                        synthesis_potential=potential["synthesis_potential"],
                        suggested_synthesis_types=potential["suggested_synthesis_types"]
                    ))
            
            # Sort by synthesis potential (descending)
            candidates.sort(key=lambda x: x.synthesis_potential, reverse=True)
            
            # Record in innovation history
            history_entry = {
                "user_id": user_id,
                "activity_type": "candidate_identification",
                "success": True,
                "details": {
                    "candidates_found": len(candidates),
                    "topic_id": topic_id
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            return candidates[:max_candidates]
            
        except Exception as e:
            # Record failure
            history_entry = {
                "user_id": user_id,
                "activity_type": "candidate_identification",
                "success": False,
                "details": {
                    "error": str(e),
                    "topic_id": topic_id
                },
                "energy_consumed": self.get_energy_cost()
            }
            await self.storage.save_document("innovation_history", history_entry)
            
            raise SynthesisError(f"Failed to find synthesis candidates: {str(e)}")
    
    async def _find_pairs_by_embedding(self, 
                                   nodes: List[Dict[str, Any]], 
                                   max_pairs: int) -> List[Tuple[StringId, StringId]]:
        """Find pairs of nodes based on embedding similarity.
        
        Args:
            nodes: List of nodes with embeddings
            max_pairs: Maximum number of pairs to return
            
        Returns:
            List of node ID pairs
        """
        # Implementation would use vector similarity to find promising pairs
        # For now, return random pairs as placeholder
        import random
        node_ids = [node["_id"] for node in nodes]
        
        pairs = []
        for _ in range(min(max_pairs, len(nodes) * (len(nodes) - 1) // 2)):
            id1, id2 = random.sample(node_ids, 2)
            pairs.append((id1, id2))
            
        return pairs
    
    async def _find_random_pairs(self, 
                             node_ids: List[StringId], 
                             max_pairs: int) -> List[Tuple[StringId, StringId]]:
        """Find random pairs of nodes.
        
        Args:
            node_ids: List of node IDs
            max_pairs: Maximum number of pairs to return
            
        Returns:
            List of node ID pairs
        """
        import random
        
        pairs = []
        for _ in range(min(max_pairs, len(node_ids) * (len(node_ids) - 1) // 2)):
            id1, id2 = random.sample(node_ids, 2)
            pairs.append((id1, id2))
            
        return pairs
    
    async def _analyze_synthesis_potential(self, 
                                       user_id: str,
                                       node1: Dict[str, Any], 
                                       node2: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the potential for synthesizing two concepts.
        
        Args:
            user_id: The user ID
            node1: First node
            node2: Second node
            
        Returns:
            Dictionary with synthesis potential metrics
        """
        # Get node information
        node1_label = node1.get("label", "Unknown")
        node1_summary = node1.get("summary", "")
        
        node2_label = node2.get("label", "Unknown")
        node2_summary = node2.get("summary", "")
        
        # Prepare the prompt
        prompt = f"""Analyze the potential for synthesizing these two concepts into a new innovative concept:

Concept 1: {node1_label}
{node1_summary}

Concept 2: {node2_label}
{node2_summary}

Please evaluate:
1. Similarity (0.0-1.0): How similar are these concepts?
2. Difference (0.0-1.0): How different or contrasting are these concepts?
3. Complementarity (0.0-1.0): How well do these concepts complement each other?
4. Overall synthesis potential (0.0-1.0): How promising would a synthesis be?

Also suggest which synthesis methods would be most appropriate from this list:
- ANALOGICAL: Uses analogy between domains
- INTEGRATIVE: Combines compatible concepts
- TRANSFORMATIONAL: Transforms concept to new domain
- DIALECTICAL: Synthesizes opposing/contrasting concepts
- CONCEPTUAL_BLENDING: Blends multiple concepts into new whole

Format your response as follows (include only the JSON, no other text):
```json
{
  "similarity_score": 0.7,
  "difference_score": 0.5,
  "complementarity_score": 0.8,
  "synthesis_potential": 0.75,
  "suggested_synthesis_types": ["INTEGRATIVE", "CONCEPTUAL_BLENDING"]
}
```
"""
        
        # Get response and parse
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Extract JSON part
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
                    
            result = json.loads(json_str)
            
            # Convert synthesis types to enum
            if "suggested_synthesis_types" in result:
                synthesis_types = []
                for type_str in result["suggested_synthesis_types"]:
                    try:
                        synthesis_types.append(SynthesisType(type_str.lower()))
                    except ValueError:
                        # Skip invalid types
                        pass
                        
                if not synthesis_types:
                    # Fallback to default if no valid types
                    synthesis_types = [SynthesisType.INTEGRATIVE]
                    
                result["suggested_synthesis_types"] = synthesis_types
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse synthesis potential JSON: {str(e)}")
            
            # Return fallback values
            return {
                "similarity_score": 0.5,
                "difference_score": 0.5,
                "complementarity_score": 0.5,
                "synthesis_potential": 0.5,
                "suggested_synthesis_types": [SynthesisType.INTEGRATIVE]
            }
    
    async def _create_concept_node(self, 
                              user_id: str, 
                              synthesis_result: ConceptSynthesisResult) -> StringId:
        """Create a knowledge node from the synthesis result.
        
        Args:
            user_id: The user ID
            synthesis_result: The synthesis result
            
        Returns:
            ID of the created node
        """
        # Get a random topic ID from source concepts (could be more sophisticated)
        topic_id = await self._get_topic_for_synthesis(user_id, synthesis_result.source_concept_ids)
        
        # Create the node
        node = {
            "user_id": user_id,
            "label": synthesis_result.new_concept_label,
            "type": "concept",
            "summary": synthesis_result.new_concept_summary,
            "content": synthesis_result.new_concept_summary,  # Use summary as content for now
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": NodeStatus.ACTIVE,
            "abstraction_level": synthesis_result.new_concept_abstraction_level,
            "abstraction_source_ids": synthesis_result.source_concept_ids,
            "abstraction_method": f"synthesis_{synthesis_result.synthesis_type.value}",
            "topic_cluster_id": topic_id,
            "importance_score": 0.7,  # Start with moderately high importance
            "certainty_score": 0.6,  # Moderate certainty for synthesized concepts
            "metadata": {
                "source": "innovation",
                "tags": ["synthesized", synthesis_result.synthesis_type.value],
                "config": {
                    "auto_prune": False,  # Don't auto-prune innovations initially
                    "importance_decay_rate": 0.005  # Slower decay for innovations
                }
            }
        }
        
        # Save the node
        node_id = await self.storage.save_document("nodes", node)
        
        return node_id
    
    async def _create_concept_relationship(self,
                                      user_id: str,
                                      source_id: StringId,
                                      target_id: StringId,
                                      synthesis_type: SynthesisType) -> StringId:
        """Create a relationship between source and synthesized concepts.
        
        Args:
            user_id: The user ID
            source_id: Source concept ID
            target_id: Target concept ID
            synthesis_type: Type of synthesis used
            
        Returns:
            ID of the created edge
        """
        # Map synthesis type to relationship type
        relationship_map = {
            SynthesisType.ANALOGICAL: RelationshipType.RELATES_TO,
            SynthesisType.INTEGRATIVE: RelationshipType.EXTENDS,
            SynthesisType.TRANSFORMATIONAL: RelationshipType.BRANCHES_FROM,
            SynthesisType.DIALECTICAL: RelationshipType.EXTENDS,
            SynthesisType.CONCEPTUAL_BLENDING: RelationshipType.PART_OF
        }
        
        relationship_type = relationship_map.get(synthesis_type, RelationshipType.RELATES_TO)
        
        # Create the edge
        edge = {
            "user_id": user_id,
            "source_node_id": source_id,
            "target_node_id": target_id,
            "relationship_type": relationship_type,
            "strength": 0.8,  # Strong connection for synthesized concepts
            "context_summary": f"Part of {synthesis_type.value} synthesis",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "source": "innovation",
            "certainty_score": 0.7
        }
        
        # Save the edge
        edge_id = await self.storage.save_document("edges", edge)
        
        return edge_id
    
    async def _get_topic_for_synthesis(self, 
                                  user_id: str, 
                                  source_concept_ids: List[StringId]) -> Optional[StringId]:
        """Get an appropriate topic ID for a synthesized concept.
        
        Args:
            user_id: The user ID
            source_concept_ids: Source concept IDs
            
        Returns:
            Topic ID or None
        """
        # Simple strategy: use the topic of the first source concept
        if not source_concept_ids:
            return None
            
        source_id = source_concept_ids[0]
        source_node = await self.storage.get_document("nodes", source_id)
        
        if not source_node:
            return None
            
        return source_node.get("topic_cluster_id")


class BaseSynthesisStrategy:
    """Base class for synthesis strategies.
    
    Provides common functionality for all synthesis strategies.
    """
    
    def __init__(self, 
                storage_provider: MongoDBProvider,
                text_model: TextGenerationModel):
        """Initialize the synthesis strategy.
        
        Args:
            storage_provider: Storage provider for database access
            text_model: Text generation model for synthesis
        """
        self.storage = storage_provider
        self.text_model = text_model
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    async def get_node_details(self, node_id: StringId) -> Dict[str, Any]:
        """Get details about a node for synthesis.
        
        Args:
            node_id: The node ID
            
        Returns:
            Node details dictionary
        """
        node = await self.storage.get_document("nodes", node_id)
        
        if not node:
            return {
                "label": "Unknown",
                "summary": "",
                "content": "",
                "abstraction_level": 2
            }
            
        return {
            "label": node.get("label", "Unknown"),
            "summary": node.get("summary", ""),
            "content": node.get("content", ""),
            "abstraction_level": node.get("abstraction_level", 2)
        }
    
    async def generate_evaluation_scores(self, 
                                    synthesis_type: SynthesisType,
                                    source_concepts: List[Dict[str, Any]],
                                    new_concept_label: str,
                                    new_concept_summary: str) -> Dict[str, float]:
        """Generate evaluation scores for a synthesized concept.
        
        Args:
            synthesis_type: Type of synthesis used
            source_concepts: List of source concept details
            new_concept_label: Label of the new concept
            new_concept_summary: Summary of the new concept
            
        Returns:
            Dictionary of evaluation scores
        """
        # Default scores
        default_scores = {
            "novelty": 0.7,
            "coherence": 0.8,
            "utility": 0.6,
            "compatibility": 0.7
        }
        
        return default_scores


class AnalogicalSynthesizer(BaseSynthesisStrategy, Strategy[SynthesisTask, ConceptSynthesisResult]):
    """Strategy for analogical synthesis.
    
    Creates new concepts by mapping relationships from one domain to another.
    """
    
    async def execute(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Execute analogical synthesis.
        
        Args:
            task: The synthesis task
            
        Returns:
            Synthesis result
        """
        # Get source concept details
        source_concepts = []
        for node_id in task.source_concept_ids:
            source_concepts.append(await self.get_node_details(node_id))
            
        if len(source_concepts) < 2:
            raise SynthesisError("Analogical synthesis requires at least two concepts")
            
        # Create prompt for analogical synthesis
        source_concept_text = "\n\n".join([
            f"Concept {i+1}: {concept['label']}\n{concept['summary']}"
            for i, concept in enumerate(source_concepts)
        ])
        
        prompt = f"""Create a new concept using analogical synthesis.

Source concepts:
{source_concept_text}

Analogical synthesis maps structures or relationships from one domain to another.
Find the underlying patterns, principles, or relationships in these concepts
and create a new concept that applies these patterns in a different context.

Target abstraction level: {task.target_abstraction_level.name} (Level {task.target_abstraction_level.value})

Please provide:
1. A concise label for the new concept (3-7 words)
2. A detailed summary of the new concept (2-3 paragraphs)

Format your response as:
Label: [new concept label]
Summary: [new concept summary]
"""
        
        # Generate the new concept
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse the response
        new_concept_label = "Analogical Concept"
        new_concept_summary = "Synthesized concept based on analogy."
        
        try:
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Label:"):
                    new_concept_label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    # Get the rest of the text as summary
                    new_concept_summary = '\n'.join(lines[i:]).replace("Summary:", "").strip()
                    break
        except Exception as e:
            self.logger.error(f"Failed to parse analogical synthesis response: {str(e)}")
            
        # Generate evaluation scores
        evaluation_scores = await self.generate_evaluation_scores(
            SynthesisType.ANALOGICAL,
            source_concepts,
            new_concept_label,
            new_concept_summary
        )
        
        # Create the result
        result = ConceptSynthesisResult(
            synthesis_type=SynthesisType.ANALOGICAL,
            source_concept_ids=task.source_concept_ids,
            new_concept_label=new_concept_label,
            new_concept_summary=new_concept_summary,
            new_concept_abstraction_level=task.target_abstraction_level,
            evaluation_scores=evaluation_scores,
            creation_timestamp=datetime.utcnow()
        )
        
        return result


class IntegrativeSynthesizer(BaseSynthesisStrategy, Strategy[SynthesisTask, ConceptSynthesisResult]):
    """Strategy for integrative synthesis.
    
    Creates new concepts by combining compatible elements from multiple concepts.
    """
    
    async def execute(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Execute integrative synthesis.
        
        Args:
            task: The synthesis task
            
        Returns:
            Synthesis result
        """
        # Get source concept details
        source_concepts = []
        for node_id in task.source_concept_ids:
            source_concepts.append(await self.get_node_details(node_id))
            
        if not source_concepts:
            raise SynthesisError("Integrative synthesis requires at least one concept")
            
        # Create prompt for integrative synthesis
        source_concept_text = "\n\n".join([
            f"Concept {i+1}: {concept['label']}\n{concept['summary']}"
            for i, concept in enumerate(source_concepts)
        ])
        
        prompt = f"""Create a new concept using integrative synthesis.

Source concepts:
{source_concept_text}

Integrative synthesis combines compatible elements from multiple concepts into a cohesive whole.
Identify the complementary aspects of these concepts and integrate them into a new concept
that preserves and enhances their compatible features.

Target abstraction level: {task.target_abstraction_level.name} (Level {task.target_abstraction_level.value})

Please provide:
1. A concise label for the new concept (3-7 words)
2. A detailed summary of the new concept (2-3 paragraphs)

Format your response as:
Label: [new concept label]
Summary: [new concept summary]
"""
        
        # Generate the new concept
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse the response
        new_concept_label = "Integrated Concept"
        new_concept_summary = "Synthesized concept based on integration."
        
        try:
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Label:"):
                    new_concept_label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    # Get the rest of the text as summary
                    new_concept_summary = '\n'.join(lines[i:]).replace("Summary:", "").strip()
                    break
        except Exception as e:
            self.logger.error(f"Failed to parse integrative synthesis response: {str(e)}")
            
        # Generate evaluation scores
        evaluation_scores = await self.generate_evaluation_scores(
            SynthesisType.INTEGRATIVE,
            source_concepts,
            new_concept_label,
            new_concept_summary
        )
        
        # Create the result
        result = ConceptSynthesisResult(
            synthesis_type=SynthesisType.INTEGRATIVE,
            source_concept_ids=task.source_concept_ids,
            new_concept_label=new_concept_label,
            new_concept_summary=new_concept_summary,
            new_concept_abstraction_level=task.target_abstraction_level,
            evaluation_scores=evaluation_scores,
            creation_timestamp=datetime.utcnow()
        )
        
        return result


class TransformationalSynthesizer(BaseSynthesisStrategy, Strategy[SynthesisTask, ConceptSynthesisResult]):
    """Strategy for transformational synthesis.
    
    Creates new concepts by transforming core aspects of existing concepts.
    """
    
    async def execute(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Execute transformational synthesis.
        
        Args:
            task: The synthesis task
            
        Returns:
            Synthesis result
        """
        # Get source concept details
        source_concepts = []
        for node_id in task.source_concept_ids:
            source_concepts.append(await self.get_node_details(node_id))
            
        if not source_concepts:
            raise SynthesisError("Transformational synthesis requires at least one concept")
            
        # Create prompt for transformational synthesis
        source_concept_text = "\n\n".join([
            f"Concept {i+1}: {concept['label']}\n{concept['summary']}"
            for i, concept in enumerate(source_concepts)
        ])
        
        prompt = f"""Create a new concept using transformational synthesis.

Source concepts:
{source_concept_text}

Transformational synthesis radically redefines or transforms core aspects of existing concepts.
Take the fundamental principles or structures of these concepts and transform them
by challenging assumptions, shifting contexts, or changing perspective.

Target abstraction level: {task.target_abstraction_level.name} (Level {task.target_abstraction_level.value})

Please provide:
1. A concise label for the new concept (3-7 words)
2. A detailed summary of the new concept (2-3 paragraphs)

Format your response as:
Label: [new concept label]
Summary: [new concept summary]
"""
        
        # Generate the new concept
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse the response
        new_concept_label = "Transformed Concept"
        new_concept_summary = "Synthesized concept based on transformation."
        
        try:
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Label:"):
                    new_concept_label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    # Get the rest of the text as summary
                    new_concept_summary = '\n'.join(lines[i:]).replace("Summary:", "").strip()
                    break
        except Exception as e:
            self.logger.error(f"Failed to parse transformational synthesis response: {str(e)}")
            
        # Generate evaluation scores
        evaluation_scores = await self.generate_evaluation_scores(
            SynthesisType.TRANSFORMATIONAL,
            source_concepts,
            new_concept_label,
            new_concept_summary
        )
        
        # Create the result
        result = ConceptSynthesisResult(
            synthesis_type=SynthesisType.TRANSFORMATIONAL,
            source_concept_ids=task.source_concept_ids,
            new_concept_label=new_concept_label,
            new_concept_summary=new_concept_summary,
            new_concept_abstraction_level=task.target_abstraction_level,
            evaluation_scores=evaluation_scores,
            creation_timestamp=datetime.utcnow()
        )
        
        return result


class DialecticalSynthesizer(BaseSynthesisStrategy, Strategy[SynthesisTask, ConceptSynthesisResult]):
    """Strategy for dialectical synthesis.
    
    Creates new concepts by resolving tensions between opposing concepts.
    """
    
    async def execute(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Execute dialectical synthesis.
        
        Args:
            task: The synthesis task
            
        Returns:
            Synthesis result
        """
        # Get source concept details
        source_concepts = []
        for node_id in task.source_concept_ids:
            source_concepts.append(await self.get_node_details(node_id))
            
        if len(source_concepts) < 2:
            raise SynthesisError("Dialectical synthesis requires at least two concepts")
            
        # Create prompt for dialectical synthesis
        source_concept_text = "\n\n".join([
            f"Concept {i+1}: {concept['label']}\n{concept['summary']}"
            for i, concept in enumerate(source_concepts)
        ])
        
        prompt = f"""Create a new concept using dialectical synthesis.

Source concepts:
{source_concept_text}

Dialectical synthesis resolves tensions between opposing or contradictory concepts.
Identify the thesis and antithesis in these concepts and create a synthesis that
transcends their opposition while preserving valuable aspects of both.

Target abstraction level: {task.target_abstraction_level.name} (Level {task.target_abstraction_level.value})

Please provide:
1. A concise label for the new concept (3-7 words)
2. A detailed summary of the new concept (2-3 paragraphs)

Format your response as:
Label: [new concept label]
Summary: [new concept summary]
"""
        
        # Generate the new concept
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse the response
        new_concept_label = "Dialectical Concept"
        new_concept_summary = "Synthesized concept based on dialectical integration."
        
        try:
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Label:"):
                    new_concept_label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    # Get the rest of the text as summary
                    new_concept_summary = '\n'.join(lines[i:]).replace("Summary:", "").strip()
                    break
        except Exception as e:
            self.logger.error(f"Failed to parse dialectical synthesis response: {str(e)}")
            
        # Generate evaluation scores
        evaluation_scores = await self.generate_evaluation_scores(
            SynthesisType.DIALECTICAL,
            source_concepts,
            new_concept_label,
            new_concept_summary
        )
        
        # Create the result
        result = ConceptSynthesisResult(
            synthesis_type=SynthesisType.DIALECTICAL,
            source_concept_ids=task.source_concept_ids,
            new_concept_label=new_concept_label,
            new_concept_summary=new_concept_summary,
            new_concept_abstraction_level=task.target_abstraction_level,
            evaluation_scores=evaluation_scores,
            creation_timestamp=datetime.utcnow()
        )
        
        return result


class ConceptualBlendingSynthesizer(BaseSynthesisStrategy, Strategy[SynthesisTask, ConceptSynthesisResult]):
    """Strategy for conceptual blending synthesis.
    
    Creates new concepts by blending multiple input spaces.
    """
    
    async def execute(self, task: SynthesisTask) -> ConceptSynthesisResult:
        """Execute conceptual blending synthesis.
        
        Args:
            task: The synthesis task
            
        Returns:
            Synthesis result
        """
        # Get source concept details
        source_concepts = []
        for node_id in task.source_concept_ids:
            source_concepts.append(await self.get_node_details(node_id))
            
        if len(source_concepts) < 2:
            raise SynthesisError("Conceptual blending requires at least two concepts")
            
        # Create prompt for conceptual blending
        source_concept_text = "\n\n".join([
            f"Concept {i+1}: {concept['label']}\n{concept['summary']}"
            for i, concept in enumerate(source_concepts)
        ])
        
        prompt = f"""Create a new concept using conceptual blending.

Source concepts:
{source_concept_text}

Conceptual blending creates a new mental space by selectively projecting elements from 
multiple input spaces, developing emergent structure, and creating a blended concept.
Identify the most relevant elements from each concept and blend them into a novel 
conceptual space that has emergent properties beyond the original inputs.

Target abstraction level: {task.target_abstraction_level.name} (Level {task.target_abstraction_level.value})

Please provide:
1. A concise label for the new concept (3-7 words)
2. A detailed summary of the new concept (2-3 paragraphs)

Format your response as:
Label: [new concept label]
Summary: [new concept summary]
"""
        
        # Generate the new concept
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse the response
        new_concept_label = "Blended Concept"
        new_concept_summary = "Synthesized concept based on conceptual blending."
        
        try:
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Label:"):
                    new_concept_label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    # Get the rest of the text as summary
                    new_concept_summary = '\n'.join(lines[i:]).replace("Summary:", "").strip()
                    break
        except Exception as e:
            self.logger.error(f"Failed to parse conceptual blending response: {str(e)}")
            
        # Generate evaluation scores
        evaluation_scores = await self.generate_evaluation_scores(
            SynthesisType.CONCEPTUAL_BLENDING,
            source_concepts,
            new_concept_label,
            new_concept_summary
        )
        
        # Create the result
        result = ConceptSynthesisResult(
            synthesis_type=SynthesisType.CONCEPTUAL_BLENDING,
            source_concept_ids=task.source_concept_ids,
            new_concept_label=new_concept_label,
            new_concept_summary=new_concept_summary,
            new_concept_abstraction_level=task.target_abstraction_level,
            evaluation_scores=evaluation_scores,
            creation_timestamp=datetime.utcnow()
        )
        
        return result