"""Resource allocation optimization strategy for AI Knowledge Forest.

This module provides a strategy for optimizing resource allocation
across system components to improve overall performance.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.forest.evaluation.strategies.base import BaseOptimizationStrategy
from src.common.decorators import track_energy, handle_errors
from src.common.exceptions import OptimizationError
from src.common.config import get_settings
from src.forest.energy.models import EnergyPoolType

logger = logging.getLogger(__name__)
settings = get_settings()


class ResourceAllocationStrategy(BaseOptimizationStrategy):
    """Strategy for optimizing resource allocation across system components."""
    
    @track_energy(10.0)
    @handle_errors(OptimizationError)
    async def evaluate(self, user_id: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate current resource allocation and recommend adjustments.
        
        Args:
            user_id: User ID
            current_metrics: Current system metrics
            
        Returns:
            Evaluation results with resource allocation recommendations
        """
        results = {
            "recommendations": [],
            "expected_improvements": {},
            "risk_level": "low",
            "priority": 0
        }
        
        # Get energy transaction history
        recent_transactions = await self.storage.find_documents(
            "energy_transactions",
            {
                "user_id": user_id,
                "timestamp": {
                    "$gte": datetime.utcnow() - timedelta(days=7)
                }
            }
        )
        
        if not recent_transactions:
            logger.info(f"Not enough energy transaction history for user {user_id}")
            return results
        
        # Analyze energy consumption by component
        component_usage = {}
        total_energy = 0
        
        for tx in recent_transactions:
            component = tx.get("component", "unknown")
            amount = tx.get("amount", 0)
            
            if amount < 0:  # Consumption (negative amount)
                amount = abs(amount)
                if component not in component_usage:
                    component_usage[component] = 0
                component_usage[component] += amount
                total_energy += amount
        
        if total_energy == 0:
            logger.info(f"No energy consumption detected for user {user_id}")
            return results
        
        # Calculate usage percentages
        component_percentages = {}
        for component, usage in component_usage.items():
            component_percentages[component] = usage / total_energy
        
        # Get current energy pool allocations
        energy_allocations = await self.storage.find_one(
            "energy_allocations",
            {"user_id": user_id, "type": EnergyPoolType.COMPONENT.value}
        )
        
        current_allocations = {}
        if energy_allocations and "allocations" in energy_allocations:
            current_allocations = energy_allocations["allocations"]
        
        # For any missing allocations, assume an even distribution
        total_components = len(component_usage)
        default_allocation = 1.0 / total_components if total_components > 0 else 0
        
        recommendations = []
        for component, usage_pct in component_percentages.items():
            current_allocation = current_allocations.get(component, default_allocation)
            
            # Determine if allocation needs adjustment
            # Strategy: allocation should roughly match usage pattern, but with some buffer
            ideal_allocation = usage_pct * 1.2  # Add a 20% buffer
            
            # If there's a significant difference, recommend adjustment
            if abs(current_allocation - ideal_allocation) > 0.1:
                recommendations.append({
                    "component": component,
                    "current_allocation": current_allocation,
                    "recommended_allocation": ideal_allocation,
                    "usage_percentage": usage_pct,
                    "reason": "Allocation does not match usage pattern"
                })
        
        results["recommendations"] = recommendations
        results["priority"] = len(recommendations)
        
        if recommendations:
            results["expected_improvements"] = {
                "resource_efficiency": "+20%",
                "component_performance": "+15%",
                "energy_utilization": "+25%"
            }
        
        return results
    
    @track_energy(15.0)
    @handle_errors(OptimizationError)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply resource allocation optimizations.
        
        Args:
            user_id: User ID
            parameters: Parameters including component allocations
            
        Returns:
            Optimization results
        """
        result = {
            "allocations_adjusted": [],
            "success": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get current metrics for before/after comparison
        current_metrics = await self._get_component_usage_metrics(user_id)
        
        # Get current energy pool allocations
        energy_allocations = await self.storage.find_one(
            "energy_allocations",
            {"user_id": user_id, "type": EnergyPoolType.COMPONENT.value}
        )
        
        if not energy_allocations:
            # Create new allocations document
            energy_allocations = {
                "user_id": user_id,
                "type": EnergyPoolType.COMPONENT.value,
                "allocations": {},
                "updated_at": datetime.utcnow()
            }
        
        # Update allocations
        allocations = energy_allocations.get("allocations", {})
        adjustments = []
        
        new_allocations = parameters.get("component_allocations", {})
        for component, new_allocation in new_allocations.items():
            old_allocation = allocations.get(component, 0.0)
            allocations[component] = new_allocation
            
            adjustments.append({
                "component": component,
                "old_allocation": old_allocation,
                "new_allocation": new_allocation
            })
        
        # Save updated allocations
        energy_allocations["allocations"] = allocations
        energy_allocations["updated_at"] = datetime.utcnow()
        
        if "_id" in energy_allocations:
            await self.storage.update_document(
                "energy_allocations",
                energy_allocations["_id"],
                {"allocations": allocations, "updated_at": datetime.utcnow()}
            )
        else:
            await self.storage.save_document("energy_allocations", energy_allocations)
        
        # Record the optimization
        optimization_id = await self.record_optimization(
            user_id,
            self.name,
            parameters,
            current_metrics,
            {"adjustments": adjustments}
        )
        
        result["allocations_adjusted"] = adjustments
        result["optimization_id"] = optimization_id
        result["success"] = True
        
        return result
    
    async def revert(self, user_id: str, optimization_id: str) -> bool:
        """Revert resource allocation changes.
        
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
        
        # Get current allocations
        energy_allocations = await self.storage.find_one(
            "energy_allocations",
            {"user_id": user_id, "type": EnergyPoolType.COMPONENT.value}
        )
        
        if not energy_allocations:
            logger.error(f"Energy allocations not found for user {user_id}")
            return False
        
        # Revert each adjustment
        allocations = energy_allocations.get("allocations", {})
        for adjustment in adjustments:
            component = adjustment.get("component")
            old_allocation = adjustment.get("old_allocation")
            
            if component and old_allocation is not None:
                allocations[component] = old_allocation
        
        # Save updated allocations
        await self.storage.update_document(
            "energy_allocations",
            energy_allocations["_id"],
            {"allocations": allocations, "updated_at": datetime.utcnow()}
        )
        
        # Update optimization record
        await self.storage.update_document(
            "optimizations",
            optimization_id,
            {"status": "reverted"}
        )
        
        return True
    
    async def _get_component_usage_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get component usage metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Component usage metrics
        """
        # Define date ranges
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)
        
        # Get energy transactions for the past day and week
        day_transactions = await self.storage.find_documents(
            "energy_transactions",
            {
                "user_id": user_id,
                "timestamp": {"$gte": one_day_ago}
            }
        )
        
        week_transactions = await self.storage.find_documents(
            "energy_transactions",
            {
                "user_id": user_id,
                "timestamp": {"$gte": one_week_ago, "$lt": one_day_ago}
            }
        )
        
        # Calculate metrics
        day_usage = self._calculate_component_usage(day_transactions)
        week_usage = self._calculate_component_usage(week_transactions)
        
        # Calculate efficiency (return on energy investment)
        efficiency_metrics = await self._calculate_efficiency_metrics(user_id)
        
        return {
            "day_usage": day_usage,
            "week_usage": week_usage,
            "efficiency": efficiency_metrics,
            "timestamp": now.isoformat()
        }
    
    def _calculate_component_usage(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate component usage from transactions.
        
        Args:
            transactions: List of energy transactions
            
        Returns:
            Component usage metrics
        """
        component_usage = {}
        total_consumption = 0
        total_generation = 0
        
        for tx in transactions:
            component = tx.get("component", "unknown")
            amount = tx.get("amount", 0)
            
            if component not in component_usage:
                component_usage[component] = {
                    "consumption": 0,
                    "generation": 0,
                    "net": 0
                }
            
            if amount < 0:  # Consumption (negative amount)
                amount_abs = abs(amount)
                component_usage[component]["consumption"] += amount_abs
                total_consumption += amount_abs
            else:  # Generation (positive amount)
                component_usage[component]["generation"] += amount
                total_generation += amount
            
            component_usage[component]["net"] += amount
        
        # Calculate percentages
        for component, metrics in component_usage.items():
            if total_consumption > 0:
                metrics["consumption_pct"] = metrics["consumption"] / total_consumption
            else:
                metrics["consumption_pct"] = 0
                
            if total_generation > 0:
                metrics["generation_pct"] = metrics["generation"] / total_generation
            else:
                metrics["generation_pct"] = 0
        
        return {
            "components": component_usage,
            "total_consumption": total_consumption,
            "total_generation": total_generation,
            "net": total_generation - total_consumption
        }
    
    async def _calculate_efficiency_metrics(self, user_id: str) -> Dict[str, Any]:
        """Calculate efficiency metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Efficiency metrics
        """
        # This would typically involve comparing energy usage to system growth
        # and improvements. For a simple implementation, we'll return placeholder metrics.
        return {
            "energy_roi": 0.8,  # Return on investment (value generated per energy unit)
            "idle_energy_pct": 0.1,  # Percentage of energy that's idle
            "waste_pct": 0.05  # Percentage of energy that's wasted
        }