"""Hierarchy management for the abstraction system.

This module provides functionality for managing hierarchical relationships
between nodes at different abstraction levels.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple

from forest.models import (
    Node, AbstractionLevel, NodeStatus, 
    StringId, RelationshipType
)
from storage.mongodb import MongoDBProvider
from forest.graph import KnowledgeGraphManager
from common.config import get_settings
from common.exceptions import HierarchyError

settings = get_settings()
logger = logging.getLogger(__name__)


class HierarchyManager:
    """Manager for abstraction hierarchies."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None):
        """Initialize the hierarchy manager.
        
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
    
    #--------------------------------------------------------------------------
    # Hierarchy traversal methods
    #--------------------------------------------------------------------------
    
    async def get_node_descendants(self,
                                user_id: str,
                                node_id: str,
                                max_levels: int = 3) -> List[Dict[str, Any]]:
        """Get descendants of a node in the abstraction hierarchy.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            max_levels: Maximum number of levels to traverse down
            
        Returns:
            List of descendant nodes
            
        Raises:
            HierarchyError: If retrieval fails
        """
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            
            if not node:
                raise HierarchyError(f"Node not found: {node_id}")
                
            # Find nodes directly instantiated from this node
            descendants = []
            visited = set()
            
            # BFS traversal
            current_level = [node_id]
            levels_traversed = 0
            
            while current_level and levels_traversed < max_levels:
                next_level = []
                
                for current_id in current_level:
                    # Skip if already visited
                    if current_id in visited:
                        continue
                        
                    visited.add(current_id)
                    
                    # Find nodes with abstract_by relation to current node
                    descendant_edges = await self.storage.find_documents(
                        "edges",
                        {
                            "user_id": user_id,
                            "target_node_id": current_id,
                            "relationship_type": RelationshipType.ABSTRACTED_BY,
                            "is_active": True
                        }
                    )
                    
                    for edge in descendant_edges:
                        descendant_id = edge.get("source_node_id")
                        
                        if descendant_id and descendant_id not in visited:
                            descendant = await self.storage.get_document("nodes", descendant_id)
                            
                            if descendant and descendant.get("status") == NodeStatus.ACTIVE:
                                descendants.append(descendant)
                                next_level.append(descendant_id)
                
                # Move to next level
                current_level = next_level
                levels_traversed += 1
                
            return descendants
            
        except Exception as e:
            logger.error(f"Failed to get node descendants: {str(e)}")
            raise HierarchyError(f"Failed to get node descendants: {str(e)}")
    
    async def get_node_ancestors(self,
                              user_id: str,
                              node_id: str,
                              max_levels: int = 3) -> List[Dict[str, Any]]:
        """Get ancestors of a node in the abstraction hierarchy.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            max_levels: Maximum number of levels to traverse up
            
        Returns:
            List of ancestor nodes
            
        Raises:
            HierarchyError: If retrieval fails
        """
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            
            if not node:
                raise HierarchyError(f"Node not found: {node_id}")
                
            # Find abstraction nodes this node is part of
            ancestors = []
            visited = set()
            
            # BFS traversal
            current_level = [node_id]
            levels_traversed = 0
            
            while current_level and levels_traversed < max_levels:
                next_level = []
                
                for current_id in current_level:
                    # Skip if already visited
                    if current_id in visited:
                        continue
                        
                    visited.add(current_id)
                    
                    # Find nodes with abstract_by relation from current node
                    ancestor_edges = await self.storage.find_documents(
                        "edges",
                        {
                            "user_id": user_id,
                            "source_node_id": current_id,
                            "relationship_type": RelationshipType.ABSTRACTED_BY,
                            "is_active": True
                        }
                    )
                    
                    for edge in ancestor_edges:
                        ancestor_id = edge.get("target_node_id")
                        
                        if ancestor_id and ancestor_id not in visited:
                            ancestor = await self.storage.get_document("nodes", ancestor_id)
                            
                            if ancestor and ancestor.get("status") == NodeStatus.ACTIVE:
                                ancestors.append(ancestor)
                                next_level.append(ancestor_id)
                
                # Move to next level
                current_level = next_level
                levels_traversed += 1
                
            return ancestors
            
        except Exception as e:
            logger.error(f"Failed to get node ancestors: {str(e)}")
            raise HierarchyError(f"Failed to get node ancestors: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Hierarchy tree methods
    #--------------------------------------------------------------------------
    
    async def get_abstraction_tree(self,
                                user_id: str,
                                root_id: str,
                                max_depth: int = 5) -> Dict[str, Any]:
        """Get a hierarchical tree of abstractions starting from a root.
        
        Args:
            user_id: The user ID
            root_id: The root node ID
            max_depth: Maximum depth to traverse
            
        Returns:
            Tree structure of abstractions
            
        Raises:
            HierarchyError: If retrieval fails
        """
        try:
            # Get the root node
            root_node = await self.storage.get_document("nodes", root_id)
            
            if not root_node:
                raise HierarchyError(f"Root node not found: {root_id}")
                
            # Build tree recursively
            tree = await self._build_tree(user_id, root_id, max_depth, 0, set())
            
            return tree
            
        except Exception as e:
            logger.error(f"Failed to get abstraction tree: {str(e)}")
            raise HierarchyError(f"Failed to get abstraction tree: {str(e)}")
    
    async def _build_tree(self,
                       user_id: str,
                       node_id: str,
                       max_depth: int,
                       current_depth: int,
                       visited: Set[str]) -> Dict[str, Any]:
        """Recursively build a tree of abstractions.
        
        Args:
            user_id: The user ID
            node_id: Current node ID
            max_depth: Maximum depth to traverse
            current_depth: Current depth
            visited: Set of visited node IDs
            
        Returns:
            Tree structure for this node
        """
        # Prevent cycles and limit depth
        if node_id in visited or current_depth >= max_depth:
            return None
            
        visited.add(node_id)
        
        # Get the node
        node = await self.storage.get_document("nodes", node_id)
        if not node:
            return None
            
        # Create node data
        node_data = {
            "id": node_id,
            "label": node.get("label", "Unknown"),
            "type": node.get("type", "node"),
            "abstraction_level": node.get("abstraction_level", 2),
            "children": []
        }
        
        # Find descendants
        descendant_edges = await self.storage.find_documents(
            "edges",
            {
                "user_id": user_id,
                "target_node_id": node_id,
                "relationship_type": RelationshipType.ABSTRACTED_BY,
                "is_active": True
            }
        )
        
        # Recursively add children
        for edge in descendant_edges:
            child_id = edge.get("source_node_id")
            
            if child_id:
                child_tree = await self._build_tree(
                    user_id=user_id,
                    node_id=child_id,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                    visited=visited.copy()  # Create copy to avoid cross-branch interference
                )
                
                if child_tree:
                    node_data["children"].append(child_tree)
        
        return node_data
    
    #--------------------------------------------------------------------------
    # Hierarchy manipulation methods
    #--------------------------------------------------------------------------
    
    async def link_nodes_in_hierarchy(self,
                                   user_id: str,
                                   source_id: str,
                                   target_id: str) -> bool:
        """Link two nodes in the abstraction hierarchy.
        
        Args:
            user_id: The user ID
            source_id: Source node ID (lower abstraction)
            target_id: Target node ID (higher abstraction)
            
        Returns:
            True if successful
            
        Raises:
            HierarchyError: If link creation fails
        """
        try:
            # Get the nodes
            source_node = await self.storage.get_document("nodes", source_id)
            target_node = await self.storage.get_document("nodes", target_id)
            
            if not source_node or not target_node:
                raise HierarchyError(f"Node not found: {source_id if not source_node else target_id}")
                
            # Check if nodes are at appropriate levels
            source_level = source_node.get("abstraction_level", 2)
            target_level = target_node.get("abstraction_level", 2)
            
            if source_level >= target_level:
                raise HierarchyError(
                    f"Invalid hierarchy: source level ({source_level}) should be lower than target level ({target_level})"
                )
                
            # Check if link already exists
            existing = await self.storage.find_documents(
                "edges",
                {
                    "user_id": user_id,
                    "source_node_id": source_id,
                    "target_node_id": target_id,
                    "relationship_type": RelationshipType.ABSTRACTED_BY,
                    "is_active": True
                },
                limit=1
            )
            
            if existing:
                # Link already exists
                return True
                
            # Create the edge
            edge = {
                "user_id": user_id,
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": RelationshipType.ABSTRACTED_BY,
                "strength": 0.8,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "source": "hierarchy_manager",
                "certainty_score": 0.7
            }
            
            await self.storage.save_document("edges", edge)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to link nodes in hierarchy: {str(e)}")
            raise HierarchyError(f"Failed to link nodes in hierarchy: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Abstraction level classification methods
    #--------------------------------------------------------------------------
    
    async def classify_node_level(self,
                               user_id: str,
                               node_id: str) -> AbstractionLevel:
        """Classify a node's abstraction level.
        
        Args:
            user_id: The user ID
            node_id: The node ID
            
        Returns:
            Abstraction level classification
            
        Raises:
            HierarchyError: If classification fails
        """
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            
            if not node:
                raise HierarchyError(f"Node not found: {node_id}")
                
            # If node already has a level, return it
            if node.get("abstraction_level"):
                return node.get("abstraction_level")
                
            # Classify based on node properties
            return await self._estimate_abstraction_level(node)
            
        except Exception as e:
            logger.error(f"Failed to classify node level: {str(e)}")
            raise HierarchyError(f"Failed to classify node level: {str(e)}")
    
    async def _estimate_abstraction_level(self, node: Dict[str, Any]) -> AbstractionLevel:
        """Estimate abstraction level based on node properties.
        
        Args:
            node: Node data
            
        Returns:
            Estimated abstraction level
        """
        # Simple heuristic-based classification
        # In a real system, you might use AI to analyze the content
        
        # Check node type
        node_type = node.get("type", "").lower()
        
        if node_type == "instance" or node_type == "example":
            return AbstractionLevel.INSTANCE
            
        if node_type == "abstraction":
            # Default abstractions to PRINCIPLE level
            return AbstractionLevel.PRINCIPLE
            
        # Check label and summary for keywords
        label = node.get("label", "").lower()
        summary = node.get("summary", "").lower()
        content = f"{label} {summary}"
        
        # Check for paradigm indicators
        paradigm_keywords = ["paradigm", "worldview", "framework", "philosophy", "school of thought"]
        if any(keyword in content for keyword in paradigm_keywords):
            return AbstractionLevel.PARADIGM
            
        # Check for principle indicators
        principle_keywords = ["principle", "theory", "law", "model", "system"]
        if any(keyword in content for keyword in principle_keywords):
            return AbstractionLevel.PRINCIPLE
            
        # Check for rule indicators
        rule_keywords = ["rule", "relationship", "pattern", "correlation", "association", "if then"]
        if any(keyword in content for keyword in rule_keywords):
            return AbstractionLevel.RULE
            
        # Default to concept level
        return AbstractionLevel.CONCEPT
