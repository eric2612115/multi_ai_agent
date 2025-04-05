"""Parameter tuning optimization strategy for AI Knowledge Forest.

This module provides a strategy for optimizing system parameters 
to improve performance and knowledge quality.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from forest.evaluation.strategies.base import BaseOptimizationStrategy
from common.decorators import track_energy, handle_errors
from common.exceptions import OptimizationError
from common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ParameterTuningStrategy(BaseOptimizationStrategy):
    """Strategy for tuning system parameters based on performance metrics."""
    
    @track_energy(10.0)
    @handle_errors(OptimizationError)
    async def evaluate(self, user_id: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate current parameters and recommend adjustments.
        
        Args:
            user_id: User ID
            current_metrics: Current system metrics
            
        Returns:
            Evaluation results with parameter tuning recommendations
        """
        results = {
            "recommendations": [],
            "expected_improvements": {},
            "risk_level": "low",
            "priority": 0
        }
        
        # Get user settings
        user_settings = await self.storage.find_one(
            "user_settings",
            {"user_id": user_id}
        )
        
        if not user_settings:
            logger.warning(f"No user settings found for user {user_id}")
            return results
        
        # Get historical metrics
        recent_metrics = await self.storage.find_documents(
            "metrics_records",
            {
                "user_id": user_id,
                "timestamp": {
                    "$gte": datetime.utcnow() - timedelta(days=7)
                }
            },
            sort=[("timestamp", -1)]
        )
        
        if not recent_metrics:
            logger.info(f"Not enough historical metrics for user {user_id}")
            return results
        
        # Analyze potential parameter adjustments
        recommendations = []
        
        # Check extraction detail level
        if current_metrics.get("extraction_success_rate", 1.0) < 0.8:
            recommendations.append({
                "parameter": "extraction_detail_level",
                "current_value": user_settings.get("extraction_detail_level", "standard"),
                "recommended_value": "detailed",
                "expected_improvement": "Increase extraction success rate by ~15%",
                "reason": "Low extraction success rate indicates need for more detail"
            })
        
        # Check dormancy threshold
        if current_metrics.get("dormant_node_ratio", 0.0) > 0.3:
            current_threshold = user_settings.get("lifecycle", {}).get(
                "dormancy_threshold", settings.lifecycle.node_dormancy_threshold
            )
            
            recommendations.append({
                "parameter": "lifecycle.dormancy_threshold",
                "current_value": current_threshold,
                "recommended_value": current_threshold - 0.05,
                "expected_improvement": "Reduce dormant node ratio by ~10%",
                "reason": "High dormancy rate indicates threshold may be too aggressive"
            })
        
        # Check energy replenishment
        if current_metrics.get("avg_node_degree", 0.0) < 3.0:
            current_rate = user_settings.get("energy", {}).get(
                "replenish_rate", settings.energy.replenish_rate
            )
            
            recommendations.append({
                "parameter": "energy.replenish_rate",
                "current_value": current_rate,
                "recommended_value": current_rate * 1.2,  # Increase by 20%
                "expected_improvement": "Increase connectivity by allowing more operations",
                "reason": "Low connectivity indicates need for more energy for operations"
            })
        
        # Check abstraction threshold
        if current_metrics.get("topic_entropy", 0.0) < 0.5:
            current_threshold = user_settings.get("abstraction", {}).get(
                "similarity_threshold", settings.abstraction.similarity_threshold
            )
            
            recommendations.append({
                "parameter": "abstraction.similarity_threshold",
                "current_value": current_threshold,
                "recommended_value": max(0.5, current_threshold - 0.1),  # Lower threshold but not too much
                "expected_improvement": "Increase topic diversity and abstraction formation",
                "reason": "Low topic entropy indicates knowledge silos"
            })
        
        results["recommendations"] = recommendations
        results["priority"] = len(recommendations)
        
        if recommendations:
            expected_improvements = {
                "extraction_success_rate": "+15%" if any(r["parameter"] == "extraction_detail_level" for r in recommendations) else "0%",
                "dormant_node_ratio": "-10%" if any(r["parameter"] == "lifecycle.dormancy_threshold" for r in recommendations) else "0%",
                "avg_node_degree": "+20%" if any(r["parameter"] == "energy.replenish_rate" for r in recommendations) else "0%",
                "topic_entropy": "+25%" if any(r["parameter"] == "abstraction.similarity_threshold" for r in recommendations) else "0%",
            }
            results["expected_improvements"] = expected_improvements
        
        return results
    
    @track_energy(15.0)
    @handle_errors(OptimizationError)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply parameter tuning optimizations.
        
        Args:
            user_id: User ID
            parameters: Parameters to adjust
            
        Returns:
            Optimization results
        """
        result = {
            "parameters_adjusted": [],
            "success": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get current user settings
        user_settings = await self.storage.find_one(
            "user_settings",
            {"user_id": user_id}
        )
        
        if not user_settings:
            # Create new settings document
            user_settings = {"user_id": user_id}
        
        # Get current metrics for before/after comparison
        current_metrics = await self._get_current_metrics(user_id)
        
        adjustments = []
        for param_name, new_value in parameters.items():
            try:
                # Handle nested parameters (e.g., "energy.replenish_rate")
                if "." in param_name:
                    category, field = param_name.split(".", 1)
                    
                    # Ensure category exists
                    if category not in user_settings:
                        user_settings[category] = {}
                    
                    # Get old value
                    old_value = user_settings[category].get(field)
                    
                    # Update value
                    user_settings[category][field] = new_value
                    
                else:
                    # Direct field
                    old_value = user_settings.get(param_name)
                    user_settings[param_name] = new_value
                
                adjustments.append({
                    "parameter": param_name,
                    "old_value": old_value,
                    "new_value": new_value
                })
                
            except Exception as e:
                logger.error(f"Error adjusting parameter {param_name}: {str(e)}")
        
        if adjustments:
            # Save updated settings
            if "_id" in user_settings:
                await self.storage.update_document(
                    "user_settings",
                    user_settings["_id"],
                    user_settings
                )
            else:
                await self.storage.save_document("user_settings", user_settings)
            
            # Record the optimization
            optimization_id = await self.record_optimization(
                user_id,
                self.name,
                parameters,
                current_metrics,
                {"adjustments": adjustments}
            )
            
            result["parameters_adjusted"] = adjustments
            result["optimization_id"] = optimization_id
            result["success"] = True
        
        return result
    
    async def revert(self, user_id: str, optimization_id: str) -> bool:
        """Revert parameter changes.
        
        Args:
            user_id: User ID
            optimization_id: ID of the optimization to revert
            
        Returns:
            True if successfully reverted
        """
        # Get the optimization record
        optimization = await self.storage.find_one(
            "optimizations",
            {"_id": optimization_id, "user_id": user_id}
        )
        
        if not optimization:
            logger.error(f"Optimization {optimization_id} not found for user {user_id}")
            return False
        
        # Get adjustments from the result
        adjustments = optimization.get("result", {}).get("adjustments", [])
        
        if not adjustments:
            logger.warning(f"No adjustments to revert for optimization {optimization_id}")
            return False
        
        # Get current settings
        user_settings = await self.storage.find_one(
            "user_settings",
            {"user_id": user_id}
        )
        
        if not user_settings:
            logger.error(f"User settings not found for user {user_id}")
            return False
        
        # Revert each adjustment
        for adjustment in adjustments:
            param_name = adjustment.get("parameter")
            old_value = adjustment.get("old_value")
            
            if param_name and old_value is not None:
                try:
                    # Handle nested parameters
                    if "." in param_name:
                        category, field = param_name.split(".", 1)
                        if category in user_settings:
                            user_settings[category][field] = old_value
                    else:
                        # Direct field
                        user_settings[param_name] = old_value
                except Exception as e:
                    logger.error(f"Error reverting parameter {param_name}: {str(e)}")
        
        # Save updated settings
        await self.storage.update_document(
            "user_settings",
            user_settings["_id"],
            user_settings
        )
        
        # Update optimization record
        await self.storage.update_document(
            "optimizations",
            optimization_id,
            {"status": "reverted"}
        )
        
        return True
    
    async def _get_current_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get current system metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Current metrics
        """
        # Get most recent metrics record
        metrics = await self.storage.find_one(
            "metrics_records",
            {"user_id": user_id},
            sort=[("timestamp", -1)]
        )
        
        if not metrics:
            return {}
        
        return {
            "node_count": metrics.get("node_count", 0),
            "edge_count": metrics.get("edge_count", 0),
            "topic_count": metrics.get("topic_count", 0),
            "avg_node_degree": metrics.get("avg_node_degree", 0.0),
            "graph_density": metrics.get("graph_density", 0.0),
            "avg_certainty_score": metrics.get("avg_certainty_score", 0.0),
            "verified_node_ratio": metrics.get("verified_node_ratio", 0.0),
            "dormant_node_ratio": metrics.get("dormant_node_ratio", 0.0),
            "topic_entropy": metrics.get("topic_entropy", 0.0),
            "health_score": metrics.get("health_score", 0.0),
            "extraction_success_rate": metrics.get("extraction_success_rate", 0.0)
        }