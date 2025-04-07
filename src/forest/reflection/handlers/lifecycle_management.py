"""Lifecycle management task handler.

This module provides the handler for lifecycle management tasks.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.forest.models import (
    ReflectionTask, NodeStatus
)
from src.forest.reflection.handlers.base import TaskHandler
from src.common.exceptions import ExecutionError
from src.common.decorators import handle_errors
from src.common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class LifecycleManagementHandler(TaskHandler):
    """Handler for lifecycle management tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "knowledge_lifecycle_management"
    
    @handle_errors(error_class=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle knowledge lifecycle management task."""
        result = {
            "success": False,
            "actions_taken": []
        }
        
        # Use lifecycle manager if available
        if hasattr(self.executor, 'lifecycle_manager') and self.executor.lifecycle_manager:
            try:
                # Run lifecycle maintenance directly
                lifecycle_results = await self.executor.lifecycle_manager.run_lifecycle_maintenance(user_id)
                
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
            # This is just a wrapper for knowledge_pruning
            pruning_task = ReflectionTask(
                type="knowledge_pruning",
                priority=task.priority,
                energy_cost=task.energy_cost * 0.8,  # Slightly lower cost
                parameters=task.parameters,
                target_node_ids=task.target_node_ids
            )
            
            # Create handler and execute
            from src.forest.reflection.handlers.knowledge_pruning import KnowledgePruningHandler
            pruning_handler = KnowledgePruningHandler(self.executor)
            pruning_result = await pruning_handler.handle(user_id, pruning_task)
            
            if pruning_result["success"]:
                result["success"] = True
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
        """Revive dormant nodes that might be important again."""
        revival_threshold = settings.lifecycle.revival_threshold
        
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
