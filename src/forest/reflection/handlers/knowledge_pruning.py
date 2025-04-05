"""Knowledge pruning task handler.

This module provides the handler for knowledge pruning tasks.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from forest.models import (
    ReflectionTask, NodeStatus
)
from forest.reflection.handlers.base import TaskHandler
from common.exceptions import ExecutionError
from common.decorators import handle_errors
from common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class KnowledgePruningHandler(TaskHandler):
    """Handler for knowledge pruning tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "knowledge_pruning"
    
    @handle_errors(error_type=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle knowledge pruning task."""
        result = {
            "success": False,
            "nodes_pruned": 0,
            "pruned_node_ids": []
        }
        
        # Use lifecycle manager if available
        lifecycle_manager = getattr(self.executor, 'lifecycle_manager', None)
        if lifecycle_manager:
            try:
                # Find dormancy candidates
                candidates = await lifecycle_manager.find_dormancy_candidates(user_id, limit=20)
                node_ids = [node["_id"] for node in candidates]
                
                # Change status for each node
                pruned_nodes = []
                for node_id in node_ids:
                    success, reason = await lifecycle_manager.change_node_status(
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
                
        # Get parameters
        threshold = task.parameters.get("threshold", settings.knowledge_lifecycle.node_dormancy_threshold)
        
        # If we have specific node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
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
        
    async def _find_pruning_candidates(self,
                                  user_id: str,
                                  threshold: float) -> List[Dict[str, Any]]:
        """Find nodes that are candidates for pruning."""
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
        """Prune a node by setting it to dormant status."""
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
