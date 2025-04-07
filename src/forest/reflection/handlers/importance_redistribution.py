"""Importance redistribution task handler.

This module provides the handler for importance redistribution tasks.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.forest.models import ReflectionTask
from src.forest.reflection.handlers.base import TaskHandler
from src.common.exceptions import ExecutionError
from src.common.decorators import handle_errors

logger = logging.getLogger(__name__)

class ImportanceRedistributionHandler(TaskHandler):
    """Handler for importance redistribution tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "importance_redistribution"
    
    @handle_errors(error_class=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle importance redistribution task."""
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
        """Redistribute importance scores across nodes."""
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
