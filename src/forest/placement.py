"""Knowledge placement service.

This module provides functionality for deciding how to place new knowledge
in the existing knowledge graph.
"""
import logging
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from ai.base import TextGenerationModel
from ai.factory import get_text_generation_model
from storage.mongodb import MongoDBProvider
from storage.vector_search import MongoDBVectorProvider
from forest.models import PlacementDecision, KnowledgeExtractionResult, Node, PlacementStrategy, PlacementAction, RelationshipType
from common.config import get_settings
from common.exceptions import PlacementError

settings = get_settings()
logger = logging.getLogger(__name__)

class KnowledgePlacementService:
    """Knowledge placement service for deciding how to add new knowledge to the graph."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBVectorProvider] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the knowledge placement service.
        
        Args:
            storage_provider: Optional storage provider with vector search capability.
            text_model: Optional text generation model.
        """
        self.storage = storage_provider
        self.text_model = text_model
        
        # Thresholds from configuration
        self.threshold_extend = settings.knowledge_forest.threshold_extend
        self.threshold_branch = settings.knowledge_forest.threshold_branch
        self.threshold_crosslink = settings.knowledge_forest.threshold_crosslink
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBVectorProvider()
            
        # Lazy initialize text model if not provided
        if self.text_model is None:
            try:
                # 直接初始化一个Gemini实例而不是使用工厂方法（避免可能的循环依赖）
                from src.ai.gemini import GeminiAI
                self.text_model = GeminiAI()
                logger.info("Successfully initialized GeminiAI directly as text model for placement service")
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiAI directly: {str(e)}")
                # Try with Claude
                try:
                    from src.ai.claude import ClaudeModel
                    self.text_model = ClaudeModel()
                    logger.info("Successfully initialized ClaudeModel directly as text model for placement service")
                except Exception as e2:
                    logger.warning(f"Failed to initialize Claude directly: {str(e2)}")
                    self.text_model = None
    
    async def decide_placement(self, extraction_result: KnowledgeExtractionResult, 
                             user_id: str) -> PlacementDecision:
        """Decide how to place new knowledge in the graph with duplicate prevention.
        
        Args:
            extraction_result: The extraction result.
            user_id: The user ID.
            
        Returns:
            The placement decision.
            
        Raises:
            PlacementError: If placement decision fails.
        """
        try:
            # Ensure storage is connected
            if not await self.storage.is_connected():
                await self.storage.connect()
                
            # Get embedding vector from extraction result
            embedding_vector = extraction_result.embedding
            
            # Get entities and summary for duplicate detection
            entities = extraction_result.entities
            summary = extraction_result.summary
            
            # Extract key terms from entities for text-based duplicate detection
            key_terms = [entity["text"].lower() for entity in entities 
                         if entity["type"] in ["keyword", "concept", "entity"]]
            
            # Search for similar nodes using vector similarity
            similar_nodes = await self.storage.search_vectors(
                collection="nodes",
                vector=embedding_vector,
                filter={"user_id": user_id},
                top_k=10,  # Get more candidates for better duplicate detection
                min_similarity=self.threshold_branch * 0.8  # Lower threshold to catch more potential duplicates
            )
            
            # Default placement is new tree
            placement = PlacementStrategy.NEW_TREE
            parent_node_info = None
            relationship_to_parent = None
            target_topic_cluster_id = str(uuid.uuid4())  # Generate new topic ID for new trees
            action_type = PlacementAction.CREATE_NEW
            
            # Check for exact or near-duplicates first
            duplicate_node = None
            if similar_nodes and len(similar_nodes) > 0:
                for node in similar_nodes:
                    # Exact summary match is likely a duplicate
                    if node.get("summary", "").lower() == summary.lower():
                        duplicate_node = node
                        break
                        
                    # Check for high term overlap indicating potential duplicate
                    node_entities = node.get("entities", [])
                    if node_entities:
                        node_terms = [entity.get("text", "").lower() for entity in node_entities 
                                      if entity.get("type") in ["keyword", "concept", "entity"]]
                        # Calculate term overlap ratio
                        if key_terms and node_terms:
                            common_terms = set(key_terms).intersection(set(node_terms))
                            overlap_ratio = len(common_terms) / min(len(key_terms), len(node_terms))
                            # If high overlap and high similarity score, consider it a duplicate
                            if overlap_ratio > 0.7 and node.get("searchScore", 0) > 0.85:
                                duplicate_node = node
                                break
            
            # If we found a duplicate, update it instead of creating a new node
            if duplicate_node:
                placement = PlacementStrategy.DUPLICATE
                parent_node_info = duplicate_node
                target_topic_cluster_id = duplicate_node.get("topic_cluster_id", target_topic_cluster_id)
                action_type = PlacementAction.UPDATE_EXISTING
                logger.info(f"Detected duplicate content - updating existing node instead of creating new one")
            
            # If no duplicates but similar nodes found, determine placement
            elif similar_nodes and len(similar_nodes) > 0:
                top_node = similar_nodes[0]
                top_score = top_node.get("searchScore", 0)
                
                if top_score >= self.threshold_extend:
                    # Candidate for extension
                    placement = PlacementStrategy.EXTEND
                    parent_node_info = top_node
                    target_topic_cluster_id = parent_node_info.get("topic_cluster_id", target_topic_cluster_id)
                    
                    # Ask AI to decide whether to update parent or create child
                    extend_decision = await self._decide_extend_action(
                        new_info=extraction_result, 
                        existing_node=parent_node_info
                    )
                    
                    if extend_decision == "update_parent":
                        action_type = PlacementAction.UPDATE_EXISTING
                    else:  # extend_decision == "create_child"
                        action_type = PlacementAction.CREATE_CHILD
                        relationship_to_parent = RelationshipType.EXTENDS
                        
                elif top_score >= self.threshold_branch:
                    # Create a branch
                    placement = PlacementStrategy.BRANCH
                    action_type = PlacementAction.CREATE_CHILD
                    parent_node_info = top_node
                    relationship_to_parent = RelationshipType.BRANCHES_FROM
                    target_topic_cluster_id = parent_node_info.get("topic_cluster_id", target_topic_cluster_id)
            
            # Check if we have enough content to create a meaningful node
            # A good node should have at least a few entities and a meaningful summary
            if action_type in [PlacementAction.CREATE_NEW, PlacementAction.CREATE_CHILD] and (
                len(entities) < 2 or 
                len(summary) < 20 or 
                summary.lower() in ["empty", "no content", "no information"]
            ):
                logger.warning(f"Insufficient content for node creation - entities: {len(entities)}, summary length: {len(summary)}")
                # Fallback to not adding a node or updating the parent if possible
                if parent_node_info:
                    action_type = PlacementAction.UPDATE_EXISTING
                    placement = PlacementStrategy.INSUFFICIENT_CONTENT
                else:
                    # No parent to update and insufficient content, so don't create a node
                    action_type = PlacementAction.NO_ACTION
                    placement = PlacementStrategy.INSUFFICIENT_CONTENT
            
            # Create the placement decision
            decision = PlacementDecision(
                placement=placement,
                action_type=action_type,
                parent_node_info=parent_node_info,
                relationship_to_parent=relationship_to_parent,
                target_topic_cluster_id=target_topic_cluster_id
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"Placement decision failed: {str(e)}")
            raise PlacementError(f"Failed to decide placement: {str(e)}")
    
    async def _decide_extend_action(self, new_info: KnowledgeExtractionResult, 
                                 existing_node: Dict[str, Any]) -> str:
        """Decide whether to update an existing node or create a child node.
        
        Args:
            new_info: The new information.
            existing_node: The existing node.
            
        Returns:
            "update_parent" or "create_child".
        """
        # Extract relevant information
        new_summary = new_info.summary
        existing_summary = existing_node.get("summary", "")
        existing_label = existing_node.get("label", "")
        
        # Create prompt for AI decision
        prompt = f"""
        I need to decide whether new information should:
        1. UPDATE an existing knowledge node (if it's repeating or only slightly extending the same concept)
        2. Create a NEW CHILD node connected to the existing node (if it adds significant new information)
        
        Existing node: 
        - Label: {existing_label}
        - Summary: {existing_summary}
        
        New information:
        - Summary: {new_summary}
        
        The similarity score between these is high ({existing_node.get("searchScore", 0):.2f}).
        
        If the new information mostly repeats, clarifies, or only slightly extends the existing information,
        respond with "UPDATE_PARENT".
        
        If the new information adds significant new details, a new perspective, or meaningfully extends
        the concept with information not present in the existing node, respond with "CREATE_CHILD".
        
        Your decision (UPDATE_PARENT or CREATE_CHILD):
        """
        
        try:
            # Get AI decision
            response = await self.text_model.generate_text(prompt, max_tokens=50)
            
            # Parse the decision
            response = response.strip().upper()
            
            if "UPDATE_PARENT" in response or "UPDATE PARENT" in response:
                return "update_parent"
            else:
                return "create_child"
        except Exception as e:
            logger.error(f"Error in decide_extend_action: {str(e)}")
            # Default to creating a child node if AI decision fails
            return "create_child"
    
    async def detect_cross_links(self, node_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Detect potential cross-links between topics.
        
        Args:
            node_id: The node ID to find cross-links for.
            user_id: The user ID.
            
        Returns:
            List of potential cross-link targets.
            
        Raises:
            PlacementError: If cross-link detection fails.
        """
        try:
            # Ensure storage is connected
            if not await self.storage.is_connected():
                await self.storage.connect()
                
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            if not node:
                raise PlacementError(f"Node not found: {node_id}")
                
            # Get the node's topic cluster
            topic_cluster_id = node.get("topic_cluster_id")
            if not topic_cluster_id:
                return []
                
            # Get the node's embedding
            embedding = node.get("embedding")
            if not embedding:
                return []
                
            # Search for similar nodes in different topic clusters
            similar_nodes = await self.storage.search_vectors(
                collection="nodes",
                vector=embedding,
                filter={
                    "user_id": user_id,
                    "topic_cluster_id": {"$ne": topic_cluster_id}
                },
                top_k=5,
                min_similarity=self.threshold_crosslink
            )
            
            return similar_nodes
            
        except Exception as e:
            logger.error(f"Cross-link detection failed: {str(e)}")
            raise PlacementError(f"Failed to detect cross-links: {str(e)}")
