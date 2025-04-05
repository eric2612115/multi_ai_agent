"""Lifecycle management system for knowledge nodes.

This module provides functionality for managing the lifecycle of knowledge nodes,
including state transitions, aging, and cleaning processes.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Callable

from forest.models import Node, NodeStatus, StringId
from forest.lifecycle.state_transition_combined import StateTransitionEngine
from storage.mongodb import MongoDBProvider
from forest.graph import KnowledgeGraphManager
from common.config import get_settings
from common.exceptions import LifecycleError

settings = get_settings()
logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manager for node lifecycle operations."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None):
        """Initialize the lifecycle manager.
        
        Args:
            storage_provider: Optional storage provider
            graph_manager: Optional knowledge graph manager
        """
        self.storage = storage_provider
        self.graph_manager = graph_manager
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize graph manager if not provided
        if self.graph_manager is None:
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
            
        # Create state transition engine
        self.transition_engine = StateTransitionEngine()
    
    #--------------------------------------------------------------------------
    # Core state transition methods
    #--------------------------------------------------------------------------
    
    async def change_node_status(self, 
                              node_id: str, 
                              target_status: NodeStatus,
                              context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Change the status of a knowledge node.
        
        Args:
            node_id: The node ID
            target_status: Target status to transition to
            context: Optional context information for the transition
            
        Returns:
            Tuple of (success, message)
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            # Get the node
            node_dict = await self.storage.get_document("nodes", node_id)
            if not node_dict:
                raise LifecycleError(f"Node not found: {node_id}")
                
            # Convert to Node model
            node = Node(**node_dict)
            
            # Check if the transition is allowed
            allowed, reason = self.transition_engine.check_transition_rule(
                node=node, 
                target_status=target_status,
                context=context or {}
            )
            
            if not allowed:
                logger.info(f"Transition from {node.status} to {target_status} not allowed: {reason}")
                return False, reason
                
            # Update the node status
            update_data = {
                "status": target_status,
                "last_status_change": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Special case for MERGED status: add merge target info
            if target_status == NodeStatus.MERGED and context and "target_node_id" in context:
                update_data["merged_into_node_id"] = context["target_node_id"]
                update_data["metadata"] = node.metadata.dict()
                update_data["metadata"]["merge_timestamp"] = datetime.utcnow().isoformat()
                
            # Update node in database
            await self.storage.update_document("nodes", node_id, update_data)
            
            logger.info(f"Node {node_id} status changed from {node.status} to {target_status}: {reason}")
            
            # If merged, create a relationship to the target node
            if target_status == NodeStatus.MERGED and context and "target_node_id" in context:
                await self._handle_merge_relationship(
                    source_id=node_id,
                    target_id=context["target_node_id"]
                )
                
            return True, reason
            
        except Exception as e:
            logger.error(f"Failed to change node status: {str(e)}")
            raise LifecycleError(f"Failed to change node status: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Candidate identification methods
    #--------------------------------------------------------------------------
    
    async def find_dormancy_candidates(self, 
                                    user_id: str, 
                                    limit: int = 20) -> List[Dict[str, Any]]:
        """Find nodes that are candidates for dormancy.
        
        Args:
            user_id: The user ID
            limit: Maximum number of candidates to return
            
        Returns:
            List of dormancy candidate nodes
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            # Get settings
            dormancy_threshold = settings.knowledge_lifecycle.node_dormancy_threshold
            min_age_days = settings.knowledge_lifecycle.node_min_age_days
            
            # Calculate minimum age
            min_age_date = datetime.utcnow() - timedelta(days=min_age_days)
            
            # Find candidates
            query = {
                "user_id": user_id,
                "status": NodeStatus.ACTIVE,
                "importance_score": {"$lt": dormancy_threshold},
                "created_at": {"$lt": min_age_date},
                "metadata.config.auto_prune": True
            }
            
            # Exclude protected nodes
            query["$or"] = [
                {"metadata.config.protect_until": {"$exists": False}},
                {"metadata.config.protect_until": None},
                {"metadata.config.protect_until": {"$lt": datetime.utcnow()}}
            ]
            
            # Find candidates
            candidates = await self.storage.find_documents(
                "nodes",
                query,
                sort=[("importance_score", 1)],  # Lowest importance first
                limit=limit
            )
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to find dormancy candidates: {str(e)}")
            raise LifecycleError(f"Failed to find dormancy candidates: {str(e)}")
    
    async def find_archive_candidates(self, 
                                   user_id: str, 
                                   limit: int = 20) -> List[Dict[str, Any]]:
        """Find dormant nodes that are candidates for archiving.
        
        Args:
            user_id: The user ID
            limit: Maximum number of candidates to return
            
        Returns:
            List of archive candidate nodes
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            # Calculate minimum dormancy time
            min_dormant_days = 30
            min_dormant_date = datetime.utcnow() - timedelta(days=min_dormant_days)
            
            # Find candidates
            query = {
                "user_id": user_id,
                "status": NodeStatus.DORMANT,
                "last_status_change": {"$lt": min_dormant_date},
                "importance_score": {"$lt": 0.2}
            }
            
            # Find candidates
            candidates = await self.storage.find_documents(
                "nodes",
                query,
                sort=[("importance_score", 1)],  # Lowest importance first
                limit=limit
            )
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to find archive candidates: {str(e)}")
            raise LifecycleError(f"Failed to find archive candidates: {str(e)}")
    
    async def find_revival_candidates(self, 
                                   user_id: str, 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Find dormant nodes that are candidates for revival.
        
        Args:
            user_id: The user ID
            limit: Maximum number of candidates to return
            
        Returns:
            List of revival candidate nodes
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            # Get revival threshold
            revival_threshold = settings.knowledge_lifecycle.revival_threshold
            
            # Find candidates
            query = {
                "user_id": user_id,
                "status": NodeStatus.DORMANT,
                "importance_score": {"$gte": revival_threshold}
            }
            
            # Find candidates
            candidates = await self.storage.find_documents(
                "nodes",
                query,
                sort=[("importance_score", -1)],  # Highest importance first
                limit=limit
            )
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to find revival candidates: {str(e)}")
            raise LifecycleError(f"Failed to find revival candidates: {str(e)}")
    
    async def find_merge_candidates(self, 
                                 user_id: str,
                                 threshold: float = 0.85,
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """Find pairs of nodes that are candidates for merging.
        
        Args:
            user_id: The user ID
            threshold: Similarity threshold
            limit: Maximum number of candidate pairs to return
            
        Returns:
            List of merge candidate pairs (each with two nodes and similarity)
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            # This is a simplified implementation
            # In a real system, you'd need a more sophisticated approach for finding duplicates
            
            # Get active nodes
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": NodeStatus.ACTIVE
                },
                projection={
                    "_id": 1,
                    "label": 1,
                    "summary": 1,
                    "embedding": 1,
                    "importance_score": 1,
                    "topic_cluster_id": 1
                }
            )
            
            # Find node pairs from same topic with similar embeddings
            candidates = []
            
            for i in range(len(nodes)):
                node1 = nodes[i]
                
                # Skip nodes without embeddings
                if not node1.get("embedding"):
                    continue
                    
                for j in range(i + 1, len(nodes)):
                    node2 = nodes[j]
                    
                    # Skip nodes without embeddings
                    if not node2.get("embedding"):
                        continue
                        
                    # Skip nodes from different topics
                    if node1.get("topic_cluster_id") != node2.get("topic_cluster_id"):
                        continue
                        
                    # Calculate similarity (cosine similarity of embeddings)
                    similarity = self._calculate_similarity(
                        node1.get("embedding", []),
                        node2.get("embedding", [])
                    )
                    
                    if similarity >= threshold:
                        # Determine which node should be merged into which
                        # Typically the less important one is merged into the more important one
                        if node1.get("importance_score", 0) >= node2.get("importance_score", 0):
                            source_node = node2
                            target_node = node1
                        else:
                            source_node = node1
                            target_node = node2
                            
                        candidates.append({
                            "source_node": source_node,
                            "target_node": target_node,
                            "similarity": similarity
                        })
                        
                        # Break if we have enough candidates
                        if len(candidates) >= limit:
                            break
                            
                if len(candidates) >= limit:
                    break
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to find merge candidates: {str(e)}")
            raise LifecycleError(f"Failed to find merge candidates: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Maintenance operations
    #--------------------------------------------------------------------------
    
    async def run_lifecycle_maintenance(self, user_id: str) -> Dict[str, Any]:
        """Run periodic lifecycle maintenance tasks.
        
        Args:
            user_id: The user ID
            
        Returns:
            Summary of maintenance actions taken
            
        Raises:
            LifecycleError: If the operation fails
        """
        try:
            results = {
                "nodes_to_dormant": 0,
                "dormant_to_archive": 0,
                "dormant_to_active": 0,
                "nodes_merged": 0
            }
            
            # 1. Move low importance nodes to dormant
            if settings.knowledge_lifecycle.enable_auto_pruning:
                dormancy_candidates = await self.find_dormancy_candidates(user_id, limit=20)
                
                for node in dormancy_candidates:
                    node_id = node["_id"]
                    
                    # Add some context data for the transition
                    context = {
                        "days_since_access": 30,  # Default high value
                        "recent_update_count": 0
                    }
                    
                    # Check last_accessed if available
                    if node.get("metadata", {}).get("last_accessed"):
                        days_since_access = (datetime.utcnow() - node["metadata"]["last_accessed"]).total_seconds() / (24 * 3600)
                        context["days_since_access"] = days_since_access
                    
                    # Try to change status
                    success, _ = await self.change_node_status(
                        node_id=node_id,
                        target_status=NodeStatus.DORMANT,
                        context=context
                    )
                    
                    if success:
                        results["nodes_to_dormant"] += 1
            
            # 2. Archive long-dormant nodes
            archive_candidates = await self.find_archive_candidates(user_id, limit=10)
            
            for node in archive_candidates:
                node_id = node["_id"]
                
                # Add context data
                context = {
                    "days_in_dormant": 0,
                    "revival_attempts": 0
                }
                
                # Calculate days in dormant state
                if node.get("last_status_change"):
                    days_in_dormant = (datetime.utcnow() - node["last_status_change"]).total_seconds() / (24 * 3600)
                    context["days_in_dormant"] = days_in_dormant
                
                # Try to change status
                success, _ = await self.change_node_status(
                    node_id=node_id,
                    target_status=NodeStatus.ARCHIVED,
                    context=context
                )
                
                if success:
                    results["dormant_to_archive"] += 1
            
            # 3. Revive important dormant nodes
            revival_candidates = await self.find_revival_candidates(user_id, limit=10)
            
            for node in revival_candidates:
                node_id = node["_id"]
                
                # Add context data with random factor for revival probability
                context = {
                    "random_factor": random.random(),  # Value between 0-1
                    "recently_accessed": False,
                    "new_connections": 0,
                }
                
                # Try to change status
                success, _ = await self.change_node_status(
                    node_id=node_id,
                    target_status=NodeStatus.ACTIVE,
                    context=context
                )
                
                if success:
                    results["dormant_to_active"] += 1
            
            # 4. Merge similar nodes
            merge_candidates = await self.find_merge_candidates(user_id, limit=5)
            
            for candidate in merge_candidates:
                source_node = candidate["source_node"]
                target_node = candidate["target_node"]
                
                # Add context data
                context = {
                    "target_node_id": target_node["_id"],
                    "similarity": candidate["similarity"],
                    "target_importance": target_node.get("importance_score", 0)
                }
                
                # Try to change status
                success, _ = await self.change_node_status(
                    node_id=source_node["_id"],
                    target_status=NodeStatus.MERGED,
                    context=context
                )
                
                if success:
                    results["nodes_merged"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to run lifecycle maintenance: {str(e)}")
            raise LifecycleError(f"Failed to run lifecycle maintenance: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Context and analysis methods
    #--------------------------------------------------------------------------
    
    async def get_node_context(self, node_id: str) -> Dict[str, Any]:
        """Get context information for a node to assist in lifecycle decisions.
        
        Args:
            node_id: The node ID
            
        Returns:
            Context dictionary with relevant information
        """
        context = {}
        
        try:
            # Get node
            node = await self.storage.get_document("nodes", node_id)
            if not node:
                return context
                
            # Get recent updates (within past 30 days)
            cutoff = datetime.utcnow() - timedelta(days=30)
            
            # Count recent updates
            update_count = 0
            if node.get("updated_at") and node.get("updated_at") > cutoff:
                update_count = 1
                
            context["recent_update_count"] = update_count
            
            # Check recent access
            recently_accessed = False
            days_since_access = 30
            
            if node.get("metadata", {}).get("last_accessed"):
                days_since_access = (datetime.utcnow() - node["metadata"]["last_accessed"]).total_seconds() / (24 * 3600)
                recently_accessed = days_since_access < 7
                
            context["recently_accessed"] = recently_accessed
            context["days_since_access"] = days_since_access
            
            # Count connected nodes
            edges = await self.storage.count_documents(
                "edges", 
                {
                    "$or": [
                        {"source_node_id": node_id},
                        {"target_node_id": node_id}
                    ],
                    "is_active": True
                }
            )
            
            context["connection_count"] = edges
            
            # Add random factor (for probabilistic decisions)
            context["random_factor"] = random.random()
            
            # Calculate importance change (if we have history)
            context["importance_change"] = 0
            
            # Get topic info
            if node.get("topic_cluster_id"):
                topic_node = await self.storage.get_document("nodes", node["topic_cluster_id"])
                if topic_node:
                    context["topic_label"] = topic_node.get("label", "Unknown")
                    
            return context
            
        except Exception as e:
            logger.error(f"Failed to get node context: {str(e)}")
            return context
    
    #--------------------------------------------------------------------------
    # Private helper methods
    #--------------------------------------------------------------------------
    
    async def _handle_merge_relationship(self, source_id: str, target_id: str) -> None:
        """Create a merged_into relationship between nodes.
        
        Args:
            source_id: Source node ID (being merged)
            target_id: Target node ID (surviving node)
        """
        # Get nodes
        source_node = await self.storage.get_document("nodes", source_id)
        target_node = await self.storage.get_document("nodes", target_id)
        
        if not source_node or not target_node:
            logger.warning(f"Cannot create merge relationship: node not found")
            return
            
        try:
            # Create edge
            edge_data = {
                "user_id": source_node["user_id"],
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": "merged_into",
                "strength": 1.0,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "context_summary": f"Node {source_node.get('label', 'Unknown')} was merged into {target_node.get('label', 'Unknown')}"
            }
            
            await self.storage.save_document("edges", edge_data)
            
            # Transfer incoming edges from source to target
            await self._transfer_relationships(source_id, target_id)
            
        except Exception as e:
            logger.error(f"Failed to handle merge relationship: {str(e)}")
    
    async def _transfer_relationships(self, source_id: str, target_id: str) -> None:
        """Transfer relationships from source node to target node.
        
        Args:
            source_id: Source node ID (being merged)
            target_id: Target node ID (surviving node)
        """
        try:
            # Find incoming edges to the source node
            incoming_edges = await self.storage.find_documents(
                "edges",
                {
                    "target_node_id": source_id,
                    "is_active": True,
                    "relationship_type": {"$ne": "merged_into"}  # Skip merge relationships
                }
            )
            
            # Redirect edges to the target node
            for edge in incoming_edges:
                edge_id = edge["_id"]
                
                # Skip self-referential edges
                if edge.get("source_node_id") == target_id:
                    continue
                    
                # Update edge target
                await self.storage.update_document(
                    "edges",
                    edge_id,
                    {
                        "target_node_id": target_id,
                        "updated_at": datetime.utcnow(),
                        "context_summary": (edge.get("context_summary", "") or "") + 
                                          " [Redirected due to node merge]"
                    }
                )
                
            # Find outgoing edges from the source node
            outgoing_edges = await self.storage.find_documents(
                "edges",
                {
                    "source_node_id": source_id,
                    "is_active": True,
                    "relationship_type": {"$ne": "merged_into"}  # Skip merge relationships
                }
            )
            
            # Redirect edges from the target node
            for edge in outgoing_edges:
                edge_id = edge["_id"]
                
                # Skip self-referential edges
                if edge.get("target_node_id") == target_id:
                    continue
                    
                # Update edge source
                await self.storage.update_document(
                    "edges",
                    edge_id,
                    {
                        "source_node_id": target_id,
                        "updated_at": datetime.utcnow(),
                        "context_summary": (edge.get("context_summary", "") or "") + 
                                          " [Redirected due to node merge]"
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to transfer relationships: {str(e)}")
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0-1)
        """
        # Handle empty embeddings
        if not embedding1 or not embedding2:
            return 0.0
            
        # Handle different lengths
        if len(embedding1) != len(embedding2):
            return 0.0
            
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Calculate magnitudes
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        # Handle zero magnitudes
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
            
        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Ensure result is in valid range
        return max(0.0, min(1.0, similarity))
