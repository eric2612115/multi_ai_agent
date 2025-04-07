"""Reflection task executor for reflection cycle.

This module provides functionality for executing reflection tasks,
which forms the Act phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from src.forest.models import (
    Node, Edge, NodeStatus, AbstractionLevel,
    RelationshipType, AbstractionCluster, StrategyAdjustment, StringId,
    SynthesisType, ReflectionTask
)
from src.storage.mongodb import MongoDBProvider
from src.forest.graph import KnowledgeGraphManager
from src.forest.energy.manager_combined import EnergyManager
from src.forest.lifecycle.manager_combined import LifecycleManager
from src.forest.abstraction.generator_combined import AbstractionGenerator
from src.forest.innovation.api import InnovationAPI
from src.ai.base import TextGenerationModel
from src.ai.factory import get_text_generation_model
from src.common.config import get_settings
from src.common.exceptions import ExecutionError

settings = get_settings()
logger = logging.getLogger(__name__)

class TaskExecutor:
    """Executor for reflection tasks."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None,
                energy_manager: Optional[EnergyManager] = None,
                lifecycle_manager: Optional[LifecycleManager] = None,
                abstraction_generator: Optional[AbstractionGenerator] = None,
                innovation_api: Optional[InnovationAPI] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the task executor.
        
        Args:
            storage_provider: Optional storage provider
            graph_manager: Optional knowledge graph manager
            energy_manager: Optional energy manager
            lifecycle_manager: Optional lifecycle manager
            abstraction_generator: Optional abstraction generator
            innovation_api: Optional innovation API
            text_model: Optional text generation model
        """
        self.storage = storage_provider
        self.graph_manager = graph_manager
        self.energy_manager = energy_manager
        self.lifecycle_manager = lifecycle_manager
        self.abstraction_generator = abstraction_generator
        self.innovation_api = innovation_api
        self.text_model = text_model
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize graph manager if not provided
        if self.graph_manager is None:
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
            
        # Lazy initialize energy manager if not provided
        if self.energy_manager is None:
            self.energy_manager = EnergyManager(storage_provider=self.storage)
            
        # Lazy initialize lifecycle manager if not provided
        if self.lifecycle_manager is None:
            self.lifecycle_manager = LifecycleManager(
                storage_provider=self.storage,
                graph_manager=self.graph_manager
            )
            
        # Lazy initialize abstraction generator if not provided
        if self.abstraction_generator is None:
            self.abstraction_generator = AbstractionGenerator(
                storage_provider=self.storage,
                graph_manager=self.graph_manager
            )
            
        # Lazy initialize innovation API if not provided
        if self.innovation_api is None:
            self.innovation_api = InnovationAPI(storage_provider=self.storage)
            
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
            
        # Track energy consumption
        self.energy_consumed = 0.0
        
        # Pool mapping for tasks
        self.energy_pool_mapping = {
            # Gap-related tasks
            "topic_expansion": "exploration",
            "abstraction_generation": "abstraction",
            "relation_discovery": "reflection",
            "knowledge_pruning": "reflection",
            "content_verification": "reflection",
            "concept_synthesis": "exploration",
            
            # System tasks
            "importance_redistribution": "system",
            "knowledge_lifecycle_management": "system",
            "learning_strategy_adaptation": "system"
        }
        
        # Register task handlers
        self.task_handlers = {
            # Gap-related tasks
            "topic_expansion": self._handle_topic_expansion,
            "abstraction_generation": self._handle_abstraction_generation,
            "relation_discovery": self._handle_relation_discovery,
            "knowledge_pruning": self._handle_knowledge_pruning,
            "content_verification": self._handle_content_verification,
            "concept_synthesis": self._handle_concept_synthesis,
            
            # System tasks
            "importance_redistribution": self._handle_importance_redistribution,
            "knowledge_lifecycle_management": self._handle_lifecycle_management,
            "learning_strategy_adaptation": self._handle_strategy_adaptation
        }
    
    async def execute_task(self, 
                        user_id: str, 
                        task: ReflectionTask) -> Dict[str, Any]:
        """Execute a reflection task.
        
        Args:
            user_id: The user ID
            task: The task to execute
            
        Returns:
            Task execution result
            
        Raises:
            ExecutionError: If task execution fails
        """
        try:
            start_time = datetime.utcnow()
            self.energy_consumed = 0.0  # Reset for this task
            
            # Get the appropriate handler for this task type
            handler = self.task_handlers.get(task.type)
            
            if not handler:
                raise ExecutionError(f"No handler for task type: {task.type}")
                
            # Check if we have enough energy
            energy_cost = task.energy_cost
            pool_type = self._get_task_energy_pool(task.type)
            
            # Try to consume energy
            if self.energy_manager:
                success, remaining = await self.energy_manager.consume_energy(
                    user_id=user_id,
                    pool=pool_type,
                    amount=energy_cost,
                    component="reflection_executor",
                    task_id=str(task.id),
                    reason=f"Executing {task.type} task"
                )
                
                if not success:
                    logger.warning(f"Not enough energy in {pool_type.value} pool for task {task.type}")
                    return {
                        "success": False,
                        "error": f"Not enough energy for task. Required: {energy_cost}, Available: {remaining}.",
                        "energy_consumed": 0.0
                    }
            
            # Execute the task
            result = await handler(user_id, task)
            
            # Add timing information to result
            duration = (datetime.utcnow() - start_time).total_seconds()
            result["execution_time"] = duration
            result["energy_consumed"] = self.energy_consumed or task.energy_cost
            
            # Log execution
            logger.info(f"Executed task {task.type} in {duration:.2f}s (energy: {self.energy_consumed})")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute task {task.type}: {str(e)}")
            raise ExecutionError(f"Failed to execute task {task.type}: {str(e)}")
            
    def _get_task_energy_pool(self, task_type: str) -> 'EnergyPoolType':
        """Get the energy pool type for a task type.
        
        Args:
            task_type: The task type
            
        Returns:
            Energy pool type
        """
        from src.forest.energy.models import EnergyPoolType
        
        # Get the pool name from mapping
        pool_name = self.energy_pool_mapping.get(task_type, "reflection")  # Default to reflection
        
        # Map to EnergyPoolType
        try:
            return getattr(EnergyPoolType, pool_name.upper())
        except AttributeError:
            logger.warning(f"Unknown energy pool: {pool_name}, using REFLECTION")
            return EnergyPoolType.REFLECTION
    
    async def _handle_concept_synthesis(self,
                                   user_id: str,
                                   task: ReflectionTask) -> Dict[str, Any]:
        """Handle concept synthesis task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "concepts_created": 0,
            "concept_ids": []
        }
        
        # Get parameters
        topic_id = task.parameters.get("topic_id")
        synthesis_type_str = task.parameters.get("synthesis_type", "integrative")
        target_level_int = task.parameters.get("target_level", 3)
        
        # Parse synthesis type and abstraction level
        try:
            synthesis_type = SynthesisType(synthesis_type_str.lower())
        except (ValueError, AttributeError):
            synthesis_type = SynthesisType.INTEGRATIVE  # Default
            
        try:
            target_level = AbstractionLevel(target_level_int)
        except (ValueError, TypeError):
            target_level = AbstractionLevel.RULE  # Default
        
        # If we have specific node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If we don't have node IDs and we have a topic, find candidates in the topic
        if not node_ids and topic_id:
            candidates = await self.innovation_api.find_synthesis_candidates(
                user_id=user_id,
                topic_id=topic_id,
                max_candidates=3
            )
            
            if candidates:
                # Use the best candidate
                best_candidate = candidates[0]
                node_ids = best_candidate.source_concept_ids
                
                # Use suggested synthesis type if available
                if best_candidate.suggested_synthesis_types:
                    synthesis_type = best_candidate.suggested_synthesis_types[0]
        
        # If we still don't have nodes, fail
        if not node_ids or len(node_ids) < 2:
            result["error"] = "Insufficient nodes for concept synthesis"
            return result
            
        # Create and execute synthesis task
        try:
            # Create synthesis task
            synthesis_task = await self.innovation_api.create_synthesis_task(
                user_id=user_id,
                source_concept_ids=node_ids,
                synthesis_type=synthesis_type,
                target_abstraction_level=target_level,
                priority=task.parameters.get("priority", 1)
            )
            
            # Execute the task
            synthesis_result = await self.innovation_api.execute_synthesis_task(
                task_id=synthesis_task.id
            )
            
            # Update result
            if synthesis_result.id:
                result["success"] = True
                result["concepts_created"] = 1
                result["concept_ids"].append(synthesis_result.id)
                result["concept_label"] = synthesis_result.new_concept_label
                result["concept_summary"] = synthesis_result.new_concept_summary
                result["synthesis_type"] = synthesis_result.synthesis_type
                
                # Evaluate the concept
                evaluation = await self.innovation_api.evaluate_concept(
                    user_id=user_id, 
                    concept_id=synthesis_result.id
                )
                
                # Add evaluation to result
                result["evaluation_score"] = evaluation.overall_score
            else:
                result["error"] = "Synthesis completed but no concept was created"
                
            # Track energy
            self.energy_consumed = task.energy_cost
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to synthesize concept: {str(e)}")
            result["error"] = str(e)
            return result
    
    async def _handle_abstraction_generation(self, 
                                          user_id: str, 
                                          task: ReflectionTask) -> Dict[str, Any]:
        """Handle abstraction generation task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "abstractions_created": 0,
            "abstraction_ids": []
        }
        
        # Get parameters
        topic_id = task.parameters.get("topic_id")
        target_level = task.parameters.get("target_level", 4)  # Default to principle level
        
        # If we have related node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If we have a topic ID, get nodes from that topic
        if topic_id and not node_ids:
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "topic_cluster_id": topic_id,
                    "abstraction_level": {"$lt": target_level}  # Only lower level nodes
                },
                projection={"_id": 1, "label": 1, "summary": 1, "abstraction_level": 1}
            )
            
            node_ids = [node["_id"] for node in nodes]
        
        # If we still don't have nodes, fail
        if not node_ids:
            result["error"] = "No nodes found for abstraction"
            return result
            
        # Find node clusters for abstraction
        clusters = await self._find_abstraction_clusters(
            user_id,
            node_ids,
            target_level
        )
        
        # If no clusters found, report result
        if not clusters:
            result["message"] = "No suitable clusters found for abstraction"
            return result
            
        # Create abstractions for each cluster
        for cluster in clusters:
            abstraction_id = await self._create_abstraction_from_cluster(user_id, cluster)
            
            if abstraction_id:
                result["abstraction_ids"].append(abstraction_id)
        
        # Update result
        result["success"] = True
        result["abstractions_created"] = len(result["abstraction_ids"])
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
        
    async def _get_learning_strategy(self, user_id: str) -> Dict[str, Any]:
        """Get the current learning strategy for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Learning strategy (creates default if none exists)
        """
        # Find existing strategy
        strategies = await self.storage.find_documents(
            "learning_strategies",
            {"user_id": user_id},
            limit=1
        )
        
        if strategies and len(strategies) > 0:
            return strategies[0]
            
        # Create a default strategy
        default_strategy = {
            "user_id": user_id,
            "topic_priorities": {},
            "depth_breadth_balance": 0.5,  # Balanced
            "extraction_detail_level": "standard",
            "extend_threshold": 0.85,
            "branch_threshold": 0.7,
            "reflection_triggers": ["schedule", "idle"],
            "updated_at": datetime.utcnow()
        }
        
        # Save to database
        strategy_id = await self.storage.save_document("learning_strategies", default_strategy)
        
        # Return with ID
        default_strategy["_id"] = strategy_id
        return default_strategy
    
    async def _adapt_learning_strategy(self, 
                                   user_id: str, 
                                   strategy: Dict[str, Any],
                                   recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adapt learning strategy based on recommendations.
        
        Args:
            user_id: The user ID
            strategy: Current learning strategy
            recommendations: Recommendations from analysis
            
        Returns:
            List of adaptations made
        """
        adaptations = []
        
        # Check each recommendation type
        for rec in recommendations:
            rec_type = rec.get("type")
            rec_target = rec.get("target_topic")
            
            # Adjust depth/breadth balance based on depth gaps
            if rec_type == "abstraction_generation":
                # Increase depth focus
                old_value = strategy.get("depth_breadth_balance", 0.5)
                new_value = min(0.8, old_value + 0.1)  # Increase, but cap at 0.8
                
                if new_value != old_value:
                    adaptations.append({
                        "parameter": "depth_breadth_balance",
                        "old_value": old_value,
                        "new_value": new_value,
                        "reason": "Need for more depth and abstraction identified"
                    })
                    
                    strategy["depth_breadth_balance"] = new_value
            
            # Adjust topic priorities based on coverage gaps
            elif rec_type == "topic_expansion":
                # Increase priority for this topic
                topic_priorities = strategy.get("topic_priorities", {})
                old_value = topic_priorities.get(rec_target, 0.5) if rec_target else 0.5
                new_value = min(0.9, old_value + 0.2)  # Increase priority, cap at 0.9
                
                if rec_target and new_value != old_value:
                    if "topic_priorities" not in strategy:
                        strategy["topic_priorities"] = {}
                        
                    strategy["topic_priorities"][rec_target] = new_value
                    
                    adaptations.append({
                        "parameter": f"topic_priorities.{rec_target}",
                        "old_value": old_value,
                        "new_value": new_value,
                        "reason": "Topic needs expansion based on coverage analysis"
                    })
            
            # Add reflection triggers based on connectivity gaps
            elif rec_type == "relation_discovery" or rec_type == "cross_topic_linking":
                # Ensure idle trigger is enabled
                reflection_triggers = strategy.get("reflection_triggers", [])
                if "idle" not in reflection_triggers:
                    old_value = reflection_triggers.copy()
                    reflection_triggers.append("idle")
                    strategy["reflection_triggers"] = reflection_triggers
                    
                    adaptations.append({
                        "parameter": "reflection_triggers",
                        "old_value": old_value,
                        "new_value": reflection_triggers,
                        "reason": "Enable idle reflection to improve knowledge connectivity"
                    })
            
            # Adjust extraction detail based on content quality
            elif rec_type == "content_verification" or rec_type == "summary_enhancement":
                # Increase extraction detail
                old_value = strategy.get("extraction_detail_level", "standard")
                if old_value == "minimal":
                    new_value = "standard"
                elif old_value == "standard":
                    new_value = "detailed"
                else:
                    new_value = old_value  # Already detailed
                
                if new_value != old_value:
                    strategy["extraction_detail_level"] = new_value
                    
                    adaptations.append({
                        "parameter": "extraction_detail_level",
                        "old_value": old_value,
                        "new_value": new_value,
                        "reason": "Improve content detail and quality"
                    })
        
        # If we made any changes, update the strategy
        if adaptations:
            strategy["updated_at"] = datetime.utcnow()
            await self.storage.update_document("learning_strategies", strategy["_id"], strategy)
            
            # Also record the adjustments
            for adjustment in adaptations:
                adjustment_record = {
                    "user_id": user_id,
                    "strategy_type": "extraction" if "extraction" in adjustment["parameter"] else "reflection",
                    "parameter_name": adjustment["parameter"],
                    "old_value": adjustment["old_value"],
                    "new_value": adjustment["new_value"],
                    "adjustment_reason": adjustment["reason"],
                    "adjustment_time": datetime.utcnow()
                }
                
                await self.storage.save_document("strategy_adjustments", adjustment_record)
        
        return adaptations
    
    async def _handle_topic_expansion(self,
                                  user_id: str,
                                  task: ReflectionTask) -> Dict[str, Any]:
        """Handle topic expansion task to cover knowledge gaps.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "nodes_created": 0,
            "node_ids": [],
            "edge_ids": []
        }
        
        # Get parameters
        description = task.parameters.get("description", "")
        topic_id = task.parameters.get("topic_id")
        
        # If we don't have a topic ID, this might be a completely new topic
        if not topic_id:
            # Create a new topic based on the gap description
            if not description:
                result["error"] = "No topic ID or description provided"
                return result
                
            # Extract a topic name from the description
            topic_name = await self._extract_topic_name(description)
            
            # Create a new topic root node
            root_node_id = await self._create_new_topic(user_id, topic_name, description)
            
            if not root_node_id:
                result["error"] = "Failed to create new topic"
                return result
                
            result["nodes_created"] = 1
            result["node_ids"].append(root_node_id)
            
            # Set as topic for further expansion
            topic_id = await self._get_node_topic_id(user_id, root_node_id)
        
        # Generate expansion nodes for the topic
        expansion_results = await self._expand_topic(user_id, topic_id, description)
        
        # Update result
        result["success"] = True
        result["nodes_created"] += expansion_results.get("nodes_created", 0)
        result["node_ids"].extend(expansion_results.get("node_ids", []))
        result["edge_ids"].extend(expansion_results.get("edge_ids", []))
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _extract_topic_name(self, description: str) -> str:
        """Extract a topic name from a description.
        
        Args:
            description: Description text
            
        Returns:
            Topic name
        """
        # Prompt for extracting topic name
        prompt = f"""From the following description, extract a concise topic name (2-5 words):

        Description: {description}

        Topic name: """
        
        # Get response
        response = await self.text_model.generate_text(prompt, max_tokens=50)
        
        # Clean up
        topic_name = response.strip()
        
        # If too long, truncate
        if len(topic_name.split()) > 5:
            words = topic_name.split()[:5]
            topic_name = " ".join(words)
            
        return topic_name
    
    async def _create_new_topic(self, user_id: str, topic_name: str, description: str) -> Optional[str]:
        """Create a new topic root node.
        
        Args:
            user_id: The user ID
            topic_name: Topic name
            description: Topic description
            
        Returns:
            Root node ID or None
        """
        try:
            # Create root node
            root_node = {
                "user_id": user_id,
                "label": topic_name,
                "type": "topic",
                "summary": description,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": AbstractionLevel.CONCEPT,
                "importance_score": 0.7,  # Moderately high initial importance
                "certainty_score": 0.6,  # Moderate certainty
                "metadata": {
                    "source": "reflection",
                    "tags": ["topic_root"],
                    "config": {
                        "auto_prune": False  # Don't auto-prune topic roots
                    }
                }
            }
            
            # Save to database
            root_id = await self.storage.save_document("nodes", root_node)
            
            # Now set its own topic_cluster_id to itself
            await self.storage.update_document(
                "nodes",
                root_id,
                {"topic_cluster_id": root_id}
            )
            
            return root_id
            
        except Exception as e:
            logger.error(f"Failed to create topic: {str(e)}")
            return None
    
    async def _get_node_topic_id(self, user_id: str, node_id: str) -> Optional[str]:
        """Get the topic ID for a node.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            
        Returns:
            Topic ID or None
        """
        node = await self.storage.get_document("nodes", node_id)
        if not node:
            return None
            
        return node.get("topic_cluster_id")
    
    async def _expand_topic(self, user_id: str, topic_id: str, context: str) -> Dict[str, Any]:
        """Expand a topic with new nodes.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            context: Context description
            
        Returns:
            Expansion results
        """
        result = {
            "nodes_created": 0,
            "node_ids": [],
            "edge_ids": []
        }
        
        try:
            # Get the topic name
            topic_name = await self._get_topic_name(user_id, topic_id)
            
            if not topic_name:
                return result
                
            # Generate concepts for this topic
            concepts = await self._generate_topic_concepts(topic_name, context)
            
            if not concepts:
                return result
                
            # Create nodes for concepts
            for concept in concepts:
                # Create the node
                node = {
                    "user_id": user_id,
                    "label": concept["name"],
                    "type": "concept",
                    "summary": concept["description"],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "status": NodeStatus.ACTIVE,
                    "topic_cluster_id": topic_id,
                    "abstraction_level": AbstractionLevel.CONCEPT,
                    "importance_score": 0.5,  # Medium importance
                    "certainty_score": 0.6,  # Moderate certainty
                    "metadata": {
                        "source": "reflection",
                        "tags": ["expansion"]
                    }
                }
                
                # Save to database
                node_id = await self.storage.save_document("nodes", node)
                
                # Create edge to topic root
                edge = {
                    "user_id": user_id,
                    "source_node_id": node_id,
                    "target_node_id": topic_id,
                    "relationship_type": RelationshipType.PART_OF,
                    "strength": 0.9,
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "reflection",
                    "certainty_score": 0.8
                }
                
                edge_id = await self.storage.save_document("edges", edge)
                
                # Update results
                result["nodes_created"] += 1
                result["node_ids"].append(node_id)
                result["edge_ids"].append(edge_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to expand topic: {str(e)}")
            return result
    
    async def _get_topic_name(self, user_id: str, topic_id: str) -> Optional[str]:
        """Get the name of a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            
        Returns:
            Topic name or None
        """
        # Get the topic root node
        node = await self.storage.get_document("nodes", topic_id)
        if not node:
            return None
            
        return node.get("label", f"Topic {topic_id[:8]}")
    
    async def _generate_topic_concepts(self, topic_name: str, context: str) -> List[Dict[str, str]]:
        """Generate concepts for a topic.
        
        Args:
            topic_name: The topic name
            context: Context description
            
        Returns:
            List of concept dictionaries
        """
        # Prompt for generating concepts
        prompt = f"""Generate 3-5 important concepts that would help expand knowledge about the following topic:

        Topic: {topic_name}
        Context: {context}

        For each concept, provide a name and brief description. Ensure the concepts cover different aspects of the topic.

        Format your response as follows (strict JSON format):
        ```json
        [
          {{
            "name": "First Concept Name",
            "description": "Description of first concept"
          }},
          {{
            "name": "Second Concept Name",
            "description": "Description of second concept"
          }}
          // additional concepts...
        ]
        ```
        """
        
        # Get response
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse JSON
        concepts = []
        try:
            # Extract JSON part
            json_text = response
            if "```json" in response:
                parts = response.split("```json")
                if len(parts) > 1:
                    json_part = parts[1].split("```")[0]
                    json_text = json_part
            
            import json
            concepts = json.loads(json_text)
        except Exception as e:
            logger.error(f"Failed to parse concept JSON: {str(e)}")
            
            # Fallback: Create a single concept from the response
            if response:
                concepts = [
                    {
                        "name": topic_name,
                        "description": response[:200]  # Limit length
                    }
                ]
        
        # Ensure we don't exceed a reasonable number
        return concepts[:5]  # Max 5 concepts
        
    async def _find_pruning_candidates(self,
                                    user_id: str,
                                    threshold: float) -> List[Dict[str, Any]]:
        """Find nodes that are candidates for pruning.
        
        Args:
            user_id: The user ID
            threshold: Importance threshold for pruning
            
        Returns:
            List of pruning candidate nodes
        """
        # Find nodes with low importance
        min_age = timedelta(days=settings.knowledge_lifecycle.node_min_age_days)
        min_date = datetime.utcnow() - min_age
        
        candidates = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active",
                "importance_score": {"$lt": threshold},
                "created_at": {"$lt": min_date},  # Ensure minimum age
                "metadata.config.auto_prune": True  # Only auto-prunable nodes
            },
            projection={
                "_id": 1, 
                "label": 1,
                "importance_score": 1,
                "metadata": 1
            },
            limit=20  # Reasonable limit
        )
        
        # Filter out protected nodes
        filtered_candidates = []
        for node in candidates:
            # Check if node is protected
            protected_until = node.get("metadata", {}).get("config", {}).get("protect_until")
            if protected_until and isinstance(protected_until, datetime) and protected_until > datetime.utcnow():
                continue  # Skip protected nodes
                
            filtered_candidates.append(node)
            
        return filtered_candidates
    
    async def _prune_node(self, user_id: str, node_id: str) -> bool:
        """Prune a node by setting it to dormant status.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            
        Returns:
            True if successfully pruned
        """
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            if not node:
                logger.warning(f"Node {node_id} not found for pruning")
                return False
                
            # Skip if already dormant or archived
            if node.get("status") in [NodeStatus.DORMANT, NodeStatus.ARCHIVED]:
                logger.info(f"Node {node_id} already in status {node.get('status')}")
                return False
                
            # Update to dormant status
            await self.storage.update_document(
                "nodes",
                node_id,
                {
                    "status": NodeStatus.DORMANT,
                    "last_status_change": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            
            logger.info(f"Pruned node {node_id} ('{node.get('label', 'Unknown')}') to dormant status")
            return True
            
        except Exception as e:
            logger.error(f"Failed to prune node {node_id}: {str(e)}")
            return False
    
    async def _handle_content_verification(self,
                                       user_id: str,
                                       task: ReflectionTask) -> Dict[str, Any]:
        """Handle content verification task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "nodes_verified": 0,
            "verified_node_ids": [],
            "issues_found": []
        }
        
        # Get node IDs to verify
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If no specific nodes, find candidates with low certainty
        if not node_ids:
            candidates = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "verification_status": "unverified",
                    "certainty_score": {"$lt": 0.7}  # Only uncertain nodes
                },
                projection={"_id": 1},
                limit=10  # Reasonable limit
            )
            
            node_ids = [node["_id"] for node in candidates]
        
        # If no candidates, return empty result
        if not node_ids:
            result["message"] = "No nodes found for verification"
            result["success"] = True
            return result
            
        # Verify the nodes
        verified_nodes = []
        issues = []
        
        for node_id in node_ids:
            verified, issue = await self._verify_node_content(user_id, node_id)
            if verified:
                verified_nodes.append(node_id)
            if issue:
                issues.append({"node_id": node_id, "issue": issue})
                
        # Update result
        result["success"] = True
        result["nodes_verified"] = len(verified_nodes)
        result["verified_node_ids"] = verified_nodes
        result["issues_found"] = issues
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _verify_node_content(self, user_id: str, node_id: str) -> tuple[bool, Optional[str]]:
        """Verify the content of a node for accuracy and consistency.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            
        Returns:
            Tuple of (verified, issue_description)
        """
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            if not node:
                return False, "Node not found"
                
            # Skip if already verified
            if node.get("verification_status") == "verified":
                return True, None
                
            # Get node data for verification
            label = node.get("label", "Unknown")
            content = node.get("content", "")
            summary = node.get("summary", "")
            
            # If no content to verify, skip
            if not content and not summary:
                return False, "No content to verify"
            
            # Check for internal consistency first
            consistency_issue = await self._check_consistency(label, summary, content)
            if consistency_issue:
                # Update node with issue
                await self.storage.update_document(
                    "nodes",
                    node_id,
                    {
                        "verification_status": "contradicted",
                        "verified_at": datetime.utcnow(),
                        "verified_by": "reflection_system",
                        "updated_at": datetime.utcnow(),
                        "certainty_score": 0.4  # Lower certainty due to issue
                    }
                )
                
                return False, consistency_issue
            
            # If no issues found, mark as verified
            await self.storage.update_document(
                "nodes",
                node_id,
                {
                    "verification_status": "verified",
                    "verified_at": datetime.utcnow(),
                    "verified_by": "reflection_system",
                    "updated_at": datetime.utcnow(),
                    "certainty_score": 0.9  # High certainty after verification
                }
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Failed to verify node {node_id}: {str(e)}")
            return False, f"Verification error: {str(e)}"
    
    async def _check_consistency(self, label: str, summary: str, content: str) -> Optional[str]:
        """Check for internal consistency issues in node content.
        
        Args:
            label: Node label
            summary: Node summary
            content: Node content
            
        Returns:
            Description of consistency issue or None
        """
        # If either summary or content is missing, no consistency to check
        if not summary or not content:
            return None
            
        # Prepare the prompt
        prompt = f"""Please check the following content for internal consistency issues:

        Title: {label}
        
        Summary: {summary}
        
        Content: {content}
        
        Are there any contradictions, factual inconsistencies, or logical problems between 
        the title, summary, and content? If yes, please describe the specific issues.
        If no inconsistencies are found, respond with "No inconsistencies found."
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=300)
        
        # Parse the response
        if "no inconsistencies" in response.lower() or "no issues" in response.lower():
            return None
        else:
            return response.strip()
    
    async def _handle_importance_redistribution(self,
                                           user_id: str,
                                           task: ReflectionTask) -> Dict[str, Any]:
        """Handle importance redistribution task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "nodes_updated": 0
        }
        
        # Get active nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active"
            },
            projection={
                "_id": 1, 
                "importance_score": 1,
                "metadata.access_count": 1,
                "created_at": 1
            }
        )
        
        if not nodes:
            result["message"] = "No active nodes found"
            result["success"] = True
            return result
        
        # Redistribute importance based on connectivity
        await self._redistribute_node_importance(user_id, nodes)
        
        # Update result
        result["success"] = True
        result["nodes_updated"] = len(nodes)
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _redistribute_node_importance(self, user_id: str, nodes: List[Dict[str, Any]]) -> None:
        """Redistribute importance scores across nodes.
        
        Args:
            user_id: The user ID
            nodes: List of nodes
        """
        try:
            # Calculate connectivity for each node
            node_connectivity = {}
            node_access_counts = {}
            node_ages = {}
            
            # Get current values
            for node in nodes:
                node_id = node["_id"]
                node_access_counts[node_id] = node.get("metadata", {}).get("access_count", 0)
                
                # Calculate age factor (newer nodes get slight boost)
                created_at = node.get("created_at", datetime.utcnow())
                age_days = (datetime.utcnow() - created_at).total_seconds() / (60 * 60 * 24)
                node_ages[node_id] = max(1, age_days)  # At least 1 day old
            
            # Calculate connectivity (edges per node)
            for node_id in node_access_counts.keys():
                edge_count = await self.storage.count_documents(
                    "edges",
                    {
                        "user_id": user_id,
                        "$or": [
                            {"source_node_id": node_id},
                            {"target_node_id": node_id}
                        ],
                        "is_active": True
                    }
                )
                
                node_connectivity[node_id] = edge_count
            
            # Calculate new importance scores
            total_importance = 100.0  # Fixed total importance to distribute
            new_scores = {}
            
            # Normalize factors
            max_connectivity = max(node_connectivity.values()) if node_connectivity else 1
            max_access_count = max(node_access_counts.values()) if node_access_counts else 1
            max_age = max(node_ages.values())
            
            # Calculate raw scores
            raw_scores = {}
            for node_id in node_connectivity.keys():
                # Normalize each factor to 0-1 range
                conn_factor = node_connectivity[node_id] / max_connectivity if max_connectivity > 0 else 0
                access_factor = node_access_counts[node_id] / max_access_count if max_access_count > 0 else 0
                recency_factor = 1.0 - (node_ages[node_id] / max_age) if max_age > 0 else 0
                
                # Weight the factors
                raw_score = (
                    conn_factor * 0.6 +    # Connectivity: 60%
                    access_factor * 0.3 +  # Usage: 30%
                    recency_factor * 0.1   # Recency: 10%
                )
                
                raw_scores[node_id] = raw_score
            
            # Normalize to sum to total_importance
            sum_raw = sum(raw_scores.values()) or 1.0
            for node_id, raw_score in raw_scores.items():
                new_scores[node_id] = (raw_score / sum_raw) * total_importance
            
            # Scale to 0-1 range
            for node_id, score in new_scores.items():
                normalized_score = min(1.0, score / 100.0)
                
                # Update the node
                await self.storage.update_document(
                    "nodes",
                    node_id,
                    {
                        "importance_score": normalized_score,
                        "updated_at": datetime.utcnow()
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to redistribute importance: {str(e)}")
    
    async def _handle_lifecycle_management(self,
                                      user_id: str,
                                      task: ReflectionTask) -> Dict[str, Any]:
        """Handle knowledge lifecycle management task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "actions_taken": []
        }
        
        # Use lifecycle manager if available
        if self.lifecycle_manager:
            try:
                # Run lifecycle maintenance directly
                lifecycle_results = await self.lifecycle_manager.run_lifecycle_maintenance(user_id)
                
                # Process results
                for action, count in lifecycle_results.items():
                    if count > 0:
                        result["actions_taken"].append({
                            "action": action,
                            "count": count
                        })
                        
                result["success"] = True
                self.energy_consumed = task.energy_cost
                return result
            except Exception as e:
                logger.error(f"Error using lifecycle manager: {str(e)}")
                # Fall back to internal implementation
        
        # Get the operation
        operation = task.parameters.get("operation", "prune_low_importance")
        
        if operation == "prune_low_importance":
            # This is just a wrapper for _handle_knowledge_pruning
            pruning_result = await self._handle_knowledge_pruning(
                user_id,
                task
            )
            
            result["success"] = pruning_result["success"]
            result["actions_taken"].append({
                "action": "pruned_nodes",
                "count": pruning_result["nodes_pruned"],
                "node_ids": pruning_result["pruned_node_ids"]
            })
            
        elif operation == "revive_nodes":
            revived = await self._revive_important_dormant_nodes(user_id)
            
            result["success"] = True
            result["actions_taken"].append({
                "action": "revived_nodes",
                "count": len(revived),
                "node_ids": revived
            })
            
        # Could add more lifecycle operations here
            
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _revive_important_dormant_nodes(self, user_id: str) -> List[str]:
        """Revive dormant nodes that might be important again.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of revived node IDs
        """
        revival_threshold = settings.knowledge_lifecycle.revival_threshold
        
        # Find dormant nodes with increased access recently
        dormant_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": NodeStatus.DORMANT
            },
            projection={
                "_id": 1, 
                "label": 1, 
                "metadata": 1,
                "importance_score": 1
            }
        )
        
        revived_nodes = []
        
        for node in dormant_nodes:
            node_id = node["_id"]
            revival_probability = node.get("metadata", {}).get("config", {}).get("revival_probability", 1.0)
            importance = node.get("importance_score", 0.0)
            
            # If importance exceeds threshold and passes revival probability check
            if importance >= revival_threshold and revival_probability >= 0.5:
                # Revive the node
                await self.storage.update_document(
                    "nodes",
                    node_id,
                    {
                        "status": NodeStatus.ACTIVE,
                        "last_status_change": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
                
                revived_nodes.append(node_id)
                logger.info(f"Revived dormant node {node_id} ('{node.get('label', 'Unknown')}')")
                
        return revived_nodes
    
    async def _handle_strategy_adaptation(self,
                                     user_id: str,
                                     task: ReflectionTask) -> Dict[str, Any]:
        """Handle learning strategy adaptation task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "adaptations_made": []
        }
        
        # Get recommendations
        recommendations = task.parameters.get("recommendations", [])
        
        if not recommendations:
            result["message"] = "No recommendations for adaptation"
            result["success"] = True
            return result
            
        # Get current learning strategy
        strategy = await self._get_learning_strategy(user_id)
        
        # Apply adaptations based on recommendations
        adaptations = await self._adapt_learning_strategy(user_id, strategy, recommendations)
        
        # Update result
        result["success"] = True
        result["adaptations_made"] = adaptations
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _find_abstraction_clusters(self, 
                                      user_id: str,
                                      node_ids: List[str],
                                      target_level: int) -> List[AbstractionCluster]:
        """Find clusters of nodes that can be abstracted.
        
        Args:
            user_id: The user ID
            node_ids: List of node IDs to consider
            target_level: Target abstraction level
            
        Returns:
            List of abstraction clusters
        """
        # Get full node data
        nodes = []
        for node_id in node_ids:
            node = await self.storage.get_document("nodes", node_id)
            if node and node.get("status") == "active":
                nodes.append(node)
        
        # Skip if we have too few nodes
        if len(nodes) < settings.abstraction.min_cluster_size:
            return []
            
        # Group nodes by abstraction level
        nodes_by_level = {}
        for node in nodes:
            level = node.get("abstraction_level", 2)  # Default to CONCEPT
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node)
        
        # Generate abstraction from each level
        clusters = []
        
        # Start with one level below target
        source_level = target_level - 1
        if source_level in nodes_by_level and len(nodes_by_level[source_level]) >= settings.abstraction.min_cluster_size:
            level_clusters = await self._cluster_nodes_for_abstraction(
                user_id,
                nodes_by_level[source_level],
                target_level
            )
            clusters.extend(level_clusters)
            
        # If no clusters from optimal level, try two levels below
        if not clusters and source_level - 1 > 0:
            source_level = target_level - 2
            if source_level in nodes_by_level and len(nodes_by_level[source_level]) >= settings.abstraction.min_cluster_size:
                level_clusters = await self._cluster_nodes_for_abstraction(
                    user_id,
                    nodes_by_level[source_level],
                    target_level
                )
                clusters.extend(level_clusters)
                
        return clusters
    
    async def _cluster_nodes_for_abstraction(self,
                                         user_id: str,
                                         nodes: List[Dict[str, Any]],
                                         target_level: int) -> List[AbstractionCluster]:
        """Cluster nodes for abstraction.
        
        Args:
            user_id: The user ID
            nodes: List of nodes to cluster
            target_level: Target abstraction level
            
        Returns:
            List of abstraction clusters
        """
        # This is a simplified implementation - in a real system, this would use
        # vector similarity clustering or another sophisticated approach
        
        # For now, we'll just check if nodes are in the same topic
        topic_groups = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id", "unknown")
            if topic_id not in topic_groups:
                topic_groups[topic_id] = []
            topic_groups[topic_id].append(node)
            
        # Create clusters for topics with enough nodes
        clusters = []
        for topic_id, topic_nodes in topic_groups.items():
            if len(topic_nodes) >= settings.abstraction.min_cluster_size:
                # Create an abstraction cluster
                node_ids = [node["_id"] for node in topic_nodes]
                node_labels = [node.get("label", "Unknown") for node in topic_nodes]
                node_summaries = [node.get("summary", "") for node in topic_nodes if node.get("summary")]
                
                # Generate an abstraction using AI
                suggested_label, suggested_summary = await self._generate_abstraction_content(
                    node_labels,
                    node_summaries,
                    target_level
                )
                
                # Create the cluster
                clusters.append(
                    AbstractionCluster(
                        source_node_ids=node_ids,
                        centroid_vector=[],  # Placeholder - would be actual vector in real system
                        coherence_score=0.8,  # Placeholder
                        common_topic_id=topic_id if topic_id != "unknown" else None,
                        suggested_label=suggested_label,
                        suggested_summary=suggested_summary,
                        abstraction_level=target_level
                    )
                )
                
        return clusters
    
    async def _generate_abstraction_content(self,
                                        node_labels: List[str],
                                        node_summaries: List[str],
                                        target_level: int) -> tuple[str, str]:
        """Generate label and summary for an abstraction.
        
        Args:
            node_labels: List of node labels
            node_summaries: List of node summaries
            target_level: Target abstraction level
            
        Returns:
            Tuple of (label, summary)
        """
        # Prepare the input
        level_names = {
            3: "rule or relationship",
            4: "principle or theory",
            5: "paradigm or framework"
        }
        level_name = level_names.get(target_level, "higher-level concept")
        
        # Prepare the prompt
        prompt = f"""I'll provide you with several related concepts and their descriptions. 
        Please identify a {level_name} that these concepts exemplify or are part of.

        Concepts:
        {', '.join(node_labels)}

        Details:
        {'; '.join(node_summaries[:5])}

        Based on these concepts, please provide:
        1. A concise label for the {level_name} (3-5 words)
        2. A brief summary explaining this {level_name} (2-3 sentences)

        Format your response as:
        Label: [your label]
        Summary: [your summary]
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Parse the response
        label = "Abstract Concept"
        summary = "Generated abstraction from related concepts."
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                if line.startswith("Label:"):
                    label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    summary = line.replace("Summary:", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse abstraction response: {str(e)}")
            
        return label, summary
    
    async def _create_abstraction_from_cluster(self,
                                           user_id: str,
                                           cluster: AbstractionCluster) -> Optional[str]:
        """Create an abstraction node from a cluster.
        
        Args:
            user_id: The user ID
            cluster: The abstraction cluster
            
        Returns:
            Abstraction node ID or None
        """
        try:
            # Create the node
            abstraction_node = {
                "user_id": user_id,
                "label": cluster.suggested_label,
                "type": "abstraction",
                "summary": cluster.suggested_summary,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": cluster.abstraction_level,
                "abstraction_source_ids": cluster.source_node_ids,
                "abstraction_method": "reflection",
                "topic_cluster_id": cluster.common_topic_id,
                "importance_score": 0.7,  # Start with moderately high importance
                "certainty_score": 0.6,  # Moderate certainty
                "metadata": {
                    "source": "reflection",
                    "tags": ["abstraction", f"level_{cluster.abstraction_level}"],
                    "config": {
                        "auto_prune": False,  # Don't auto-prune abstractions
                        "importance_decay_rate": 0.005  # Slower decay for abstractions
                    }
                }
            }
            
            # Save to database
            abstraction_id = await self.storage.save_document("nodes", abstraction_node)
            
            # Create edges connecting source nodes to this abstraction
            for source_id in cluster.source_node_ids:
                edge = {
                    "user_id": user_id,
                    "source_node_id": source_id,
                    "target_node_id": abstraction_id,
                    "relationship_type": RelationshipType.ABSTRACTED_BY,
                    "strength": 0.8,  # Strong connection for abstractions
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "reflection",
                    "certainty_score": 0.7
                }
                
                await self.storage.save_document("edges", edge)
                
            return abstraction_id
            
        except Exception as e:
            logger.error(f"Failed to create abstraction: {str(e)}")
            return None
    
    async def _handle_relation_discovery(self,
                                     user_id: str,
                                     task: ReflectionTask) -> Dict[str, Any]:
        """Handle relation discovery task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "relations_created": 0,
            "relation_ids": []
        }
        
        # Get parameters
        topic_id = task.parameters.get("topic_id")
        
        # If we have related node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If we have a topic ID, get nodes from that topic
        if topic_id and not node_ids:
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "topic_cluster_id": topic_id
                },
                projection={"_id": 1, "label": 1}
            )
            
            node_ids = [node["_id"] for node in nodes]
        
        # If we still don't have enough nodes, fail
        if len(node_ids) < 2:
            result["error"] = "Not enough nodes for relation discovery"
            return result
            
        # Discover relations
        discovered_relations = await self._discover_relations(user_id, node_ids)
        
        # Update result
        result["success"] = True
        result["relations_created"] = len(discovered_relations)
        result["relation_ids"] = discovered_relations
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _discover_relations(self,
                               user_id: str,
                               node_ids: List[str]) -> List[str]:
        """Discover relations between nodes.
        
        Args:
            user_id: The user ID
            node_ids: List of node IDs
            
        Returns:
            List of created edge IDs
        """
        # Get full node data
        nodes = {}
        for node_id in node_ids:
            node = await self.storage.get_document("nodes", node_id)
            if node and node.get("status") == "active":
                nodes[str(node_id)] = node
                
        # Skip if we have too few nodes
        if len(nodes) < 2:
            return []
            
        # Check which pairs already have relationships
        existing_relations = set()
        for source_id in nodes:
            for target_id in nodes:
                if source_id != target_id:
                    # Check if an edge exists in either direction
                    count = await self.storage.count_documents(
                        "edges",
                        {
                            "user_id": user_id,
                            "$or": [
                                {"source_node_id": source_id, "target_node_id": target_id},
                                {"source_node_id": target_id, "target_node_id": source_id}
                            ]
                        }
                    )
                    
                    if count > 0:
                        existing_relations.add(frozenset([source_id, target_id]))
        
        # For remaining pairs, discover relationships
        created_edge_ids = []
        node_id_list = list(nodes.keys())
        
        # Limit number of pairs to analyze to avoid excessive computation
        max_pairs = 10
        pair_count = 0
        
        for i in range(len(node_id_list)):
            for j in range(i+1, len(node_id_list)):
                source_id = node_id_list[i]
                target_id = node_id_list[j]
                
                # Skip if already related
                if frozenset([source_id, target_id]) in existing_relations:
                    continue
                    
                # Discover relationship
                edge_id = await self._analyze_and_create_relationship(
                    user_id,
                    nodes[source_id],
                    nodes[target_id]
                )
                
                if edge_id:
                    created_edge_ids.append(edge_id)
                    
                # Increment pair count
                pair_count += 1
                if pair_count >= max_pairs:
                    break
                    
            if pair_count >= max_pairs:
                break
                
        return created_edge_ids
    
    async def _analyze_and_create_relationship(self,
                                           user_id: str,
                                           source_node: Dict[str, Any],
                                           target_node: Dict[str, Any]) -> Optional[str]:
        """Analyze and create a relationship between two nodes.
        
        Args:
            user_id: The user ID
            source_node: Source node
            target_node: Target node
            
        Returns:
            Edge ID or None
        """
        try:
            # Get node information
            source_label = source_node.get("label", "Unknown")
            source_summary = source_node.get("summary", "")
            
            target_label = target_node.get("label", "Unknown")
            target_summary = target_node.get("summary", "")
            
            # Prepare the prompt
            prompt = f"""I'll provide you with two concepts. Please analyze their relationship.

            Concept 1: {source_label}
            {source_summary}

            Concept 2: {target_label}
            {target_summary}

            What is the most appropriate relationship between these concepts?
            Choose from: relates_to, extends, part_of, causes, explains, contradicts, instance_of, precedes

            Format your response as:
            Relationship: [relationship type]
            Direction: [1->2 or 2->1]
            Explanation: [brief explanation]
            Strength: [a number between 0.0 and 1.0]
            """
            
            # Get the response
            response = await self.text_model.generate_text(prompt, max_tokens=300)
            
            # Parse the response
            relationship_type = RelationshipType.RELATES_TO
            direction = "1->2"
            explanation = ""
            strength = 0.5
            
            try:
                lines = response.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("Relationship:"):
                        rel_text = line.replace("Relationship:", "").strip().lower()
                        # Map to valid RelationshipType
                        for rel_type in RelationshipType:
                            if rel_type.value in rel_text:
                                relationship_type = rel_type
                                break
                    elif line.startswith("Direction:"):
                        direction = line.replace("Direction:", "").strip()
                    elif line.startswith("Explanation:"):
                        explanation = line.replace("Explanation:", "").strip()
                    elif line.startswith("Strength:"):
                        strength_text = line.replace("Strength:", "").strip()
                        try:
                            strength_value = float(strength_text)
                            strength = min(1.0, max(0.0, strength_value))
                        except ValueError:
                            pass
            except Exception as e:
                logger.error(f"Failed to parse relationship response: {str(e)}")
                
            # Create the edge based on direction
            if direction == "2->1":
                # Swap source and target
                source_id = target_node["_id"]
                target_id = source_node["_id"]
            else:
                source_id = source_node["_id"]
                target_id = target_node["_id"]
                
            # Create the edge
            edge = {
                "user_id": user_id,
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": relationship_type,
                "strength": strength,
                "context_summary": explanation,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "source": "reflection",
                "certainty_score": 0.6
            }
            
            # Save to database
            edge_id = await self.storage.save_document("edges", edge)
            
            return edge_id
            
        except Exception as e:
            logger.error(f"Failed to create relationship: {str(e)}")
            return None
    
    async def _handle_knowledge_pruning(self,
                                     user_id: str,
                                     task: ReflectionTask) -> Dict[str, Any]:
        """Handle knowledge pruning task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "nodes_pruned": 0,
            "pruned_node_ids": []
        }
        
        # Get parameters
        threshold = task.parameters.get("threshold", settings.knowledge_lifecycle.node_dormancy_threshold)
        
        # If we have specific node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # Use lifecycle manager if available and no specific nodes requested
        if self.lifecycle_manager and not node_ids:
            try:
                # Find dormancy candidates
                candidates = await self.lifecycle_manager.find_dormancy_candidates(user_id, limit=20)
                node_ids = [node["_id"] for node in candidates]
                
                # Change status for each node
                pruned_nodes = []
                for node_id in node_ids:
                    success, reason = await self.lifecycle_manager.change_node_status(
                        node_id=node_id,
                        target_status="dormant"
                    )
                    
                    if success:
                        pruned_nodes.append(node_id)
                
                # Update result
                result["success"] = True
                result["nodes_pruned"] = len(pruned_nodes)
                result["pruned_node_ids"] = pruned_nodes
                
                # Track energy
                self.energy_consumed = task.energy_cost
                
                return result
            except Exception as e:
                logger.error(f"Error using lifecycle manager for pruning: {str(e)}")
                # Fall back to internal implementation
        
        # If no specific nodes, find candidates
        if not node_ids:
            # Find nodes eligible for pruning
            candidates = await self._find_pruning_candidates(user_id, threshold)
            node_ids = [node["_id"] for node in candidates]
        
        # If no candidates, return empty result
        if not node_ids:
            result["message"] = "No nodes found for pruning"
            result["success"] = True
            return result
            
        # Prune the nodes
        pruned_nodes = []
        for node_id in node_ids:
            success = await self._prune_node(user_id, node_id)
            if success:
                pruned_nodes.append(node_id)
                
        # Update result
        result["success"] = True
        result["nodes_pruned"] = len(pruned_nodes)
        result["pruned_node_ids"] = pruned_nodes
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result