"""Strategy adaptation task handler.

This module provides the handler for learning strategy adaptation tasks.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.forest.models import ReflectionTask
from src.forest.reflection.handlers.base import TaskHandler
from src.common.exceptions import ExecutionError
from src.common.decorators import handle_errors

logger = logging.getLogger(__name__)

class StrategyAdaptationHandler(TaskHandler):
    """Handler for learning strategy adaptation tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "learning_strategy_adaptation"
    
    @handle_errors(error_class=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle learning strategy adaptation task."""
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
        
    async def _get_learning_strategy(self, user_id: str) -> Dict[str, Any]:
        """Get the current learning strategy for a user."""
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
        """Adapt learning strategy based on recommendations."""
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
