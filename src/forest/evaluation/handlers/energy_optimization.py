"""Energy optimization handler for AI Knowledge Forest evaluation system.

This module provides a handler for optimizing energy usage and allocation within the system.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.forest.evaluation.handlers.base import BaseOptimizationHandler
from src.common.decorators import track_energy, handle_errors
from src.common.exceptions import OptimizationError
from src.forest.energy.models import EnergyPoolType, EnergyTransactionType
from src.common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EnergyOptimizationHandler(BaseOptimizationHandler):
    """Handler for optimizing energy system performance."""
    
    @track_energy(5.0)
    async def collect_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect energy system metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Energy system metrics
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
        
        # Get energy pools
        pools = await self.storage.find_documents(
            "energy_pools",
            {"user_id": user_id}
        )
        
        # Calculate day metrics
        day_metrics = self._calculate_transaction_metrics(day_transactions)
        
        # Calculate week metrics
        week_metrics = self._calculate_transaction_metrics(week_transactions)
        
        # Calculate pool metrics
        pool_metrics = self._calculate_pool_metrics(pools)
        
        # Calculate component efficiency
        efficiency_metrics = self._calculate_efficiency_metrics(day_transactions)
        
        return {
            "day_metrics": day_metrics,
            "week_metrics": week_metrics,
            "pool_metrics": pool_metrics,
            "efficiency_metrics": efficiency_metrics,
            "timestamp": now.isoformat(),
            "total_energy_available": sum(pool.get("current_energy", 0) for pool in pools)
        }
    
    @track_energy(8.0)
    async def analyze_metrics(self, user_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze energy metrics and identify issues.
        
        Args:
            user_id: User ID
            metrics: Energy metrics
            
        Returns:
            Analysis results with identified issues
        """
        issues = []
        recommendations = []
        
        # Look for high energy consumers with low value
        efficiency_metrics = metrics.get("efficiency_metrics", {})
        inefficient_components = []
        
        for component, data in efficiency_metrics.items():
            if data.get("energy_consumed", 0) > 50 and data.get("efficiency_score", 1.0) < 0.4:
                inefficient_components.append({
                    "component": component,
                    "energy_consumed": data.get("energy_consumed", 0),
                    "efficiency_score": data.get("efficiency_score", 0)
                })
        
        if inefficient_components:
            issues.append({
                "type": "inefficient_components",
                "severity": "medium",
                "components": inefficient_components
            })
            
            recommendations.append({
                "type": "adjust_component_allocations",
                "details": "Reduce energy allocation to inefficient components",
                "components": [c["component"] for c in inefficient_components]
            })
        
        # Check for energy starvation
        day_metrics = metrics.get("day_metrics", {})
        energy_depletion_count = day_metrics.get("depletion_count", 0)
        
        if energy_depletion_count > 3:
            issues.append({
                "type": "energy_starvation",
                "severity": "high",
                "depletion_count": energy_depletion_count
            })
            
            recommendations.append({
                "type": "increase_replenishment_rate",
                "details": "Increase energy replenishment rate to avoid starvation",
                "current_rate": metrics.get("pool_metrics", {}).get("replenishment_rate", 0),
                "recommended_rate": metrics.get("pool_metrics", {}).get("replenishment_rate", 0) * 1.3
            })
        
        # Check for energy waste
        energy_available = metrics.get("total_energy_available", 0)
        max_energy = metrics.get("pool_metrics", {}).get("max_energy", 150)
        
        if energy_available > max_energy * 0.9 and energy_depletion_count == 0:
            issues.append({
                "type": "energy_waste",
                "severity": "low",
                "available_energy": energy_available,
                "max_energy": max_energy
            })
            
            recommendations.append({
                "type": "adjust_max_energy",
                "details": "Reduce max energy to prevent waste",
                "current_max": max_energy,
                "recommended_max": max_energy * 0.8
            })
        
        # Check for imbalanced pool allocations
        pool_metrics = metrics.get("pool_metrics", {})
        pool_allocations = pool_metrics.get("pool_allocations", {})
        
        if pool_allocations:
            # Check for very small or very large allocations
            imbalanced_pools = []
            
            for pool_type, allocation in pool_allocations.items():
                if allocation < 0.05 or allocation > 0.6:
                    imbalanced_pools.append({
                        "pool_type": pool_type,
                        "allocation": allocation
                    })
            
            if imbalanced_pools:
                issues.append({
                    "type": "imbalanced_pool_allocations",
                    "severity": "medium",
                    "pools": imbalanced_pools
                })
                
                # Prepare recommended allocations
                recommended_allocations = {}
                for pool in imbalanced_pools:
                    pool_type = pool["pool_type"]
                    current = pool["allocation"]
                    
                    if current < 0.05:
                        recommended_allocations[pool_type] = 0.1
                    elif current > 0.6:
                        recommended_allocations[pool_type] = 0.4
                
                recommendations.append({
                    "type": "adjust_pool_allocations",
                    "details": "Balance energy pool allocations",
                    "recommended_allocations": recommended_allocations
                })
        
        return {
            "issues": issues,
            "recommendations": recommendations,
            "metrics_summary": {
                "daily_consumption": day_metrics.get("total_consumption", 0),
                "weekly_consumption": week_metrics.get("total_consumption", 0),
                "avg_efficiency": metrics.get("efficiency_metrics", {}).get("overall_efficiency", 0),
                "depletion_frequency": energy_depletion_count
            },
            "health_score": await self.calculate_health_score(metrics)
        }
    
    @track_energy(10.0)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply energy optimizations.
        
        Args:
            user_id: User ID
            parameters: Optimization parameters
            
        Returns:
            Optimization results
        """
        optimization_type = parameters.get("type")
        if not optimization_type:
            raise OptimizationError("No optimization type specified")
        
        results = {
            "type": optimization_type,
            "changes": [],
            "success": False
        }
        
        if optimization_type == "adjust_component_allocations":
            components = parameters.get("components", [])
            if not components:
                raise OptimizationError("No components specified for allocation adjustment")
                
            # Get current allocations
            allocations = await self.storage.find_one(
                "energy_allocations",
                {"user_id": user_id, "type": EnergyPoolType.COMPONENT.value}
            )
            
            if not allocations:
                allocations = {
                    "user_id": user_id,
                    "type": EnergyPoolType.COMPONENT.value,
                    "allocations": {},
                    "updated_at": datetime.utcnow()
                }
            
            # Adjust allocations
            allocation_map = allocations.get("allocations", {})
            for component in components:
                current = allocation_map.get(component, 1.0)
                new_value = max(0.5, current * 0.7)  # Reduce by 30%, but not below 50%
                
                allocation_map[component] = new_value
                
                results["changes"].append({
                    "component": component,
                    "old_value": current,
                    "new_value": new_value
                })
            
            # Save updated allocations
            allocations["allocations"] = allocation_map
            allocations["updated_at"] = datetime.utcnow()
            
            if "_id" in allocations:
                await self.storage.update_document(
                    "energy_allocations", 
                    allocations["_id"], 
                    allocations
                )
            else:
                await self.storage.save_document("energy_allocations", allocations)
                
            results["success"] = True
            
        elif optimization_type == "increase_replenishment_rate":
            rate = parameters.get("recommended_rate")
            if not rate:
                raise OptimizationError("No replenishment rate specified")
                
            # Update user settings
            user_settings = await self.storage.find_one(
                "user_settings",
                {"user_id": user_id}
            )
            
            if not user_settings:
                user_settings = {"user_id": user_id}
            
            if "energy" not in user_settings:
                user_settings["energy"] = {}
            
            old_rate = user_settings.get("energy", {}).get("replenish_rate", settings.energy.replenish_rate)
            user_settings["energy"]["replenish_rate"] = rate
            
            if "_id" in user_settings:
                await self.storage.update_document(
                    "user_settings",
                    user_settings["_id"],
                    user_settings
                )
            else:
                await self.storage.save_document("user_settings", user_settings)
            
            results["changes"].append({
                "setting": "energy.replenish_rate",
                "old_value": old_rate,
                "new_value": rate
            })
            
            results["success"] = True
            
        elif optimization_type == "adjust_max_energy":
            max_energy = parameters.get("recommended_max")
            if not max_energy:
                raise OptimizationError("No max energy specified")
                
            # Update user settings
            user_settings = await self.storage.find_one(
                "user_settings",
                {"user_id": user_id}
            )
            
            if not user_settings:
                user_settings = {"user_id": user_id}
            
            if "energy" not in user_settings:
                user_settings["energy"] = {}
            
            old_max = user_settings.get("energy", {}).get("max_energy", settings.energy.max_energy)
            user_settings["energy"]["max_energy"] = max_energy
            
            if "_id" in user_settings:
                await self.storage.update_document(
                    "user_settings",
                    user_settings["_id"],
                    user_settings
                )
            else:
                await self.storage.save_document("user_settings", user_settings)
            
            results["changes"].append({
                "setting": "energy.max_energy",
                "old_value": old_max,
                "new_value": max_energy
            })
            
            results["success"] = True
            
        elif optimization_type == "adjust_pool_allocations":
            recommended = parameters.get("recommended_allocations", {})
            if not recommended:
                raise OptimizationError("No pool allocations specified")
                
            # Get current pool allocations
            allocations = await self.storage.find_one(
                "energy_allocations",
                {"user_id": user_id, "type": EnergyPoolType.POOL.value}
            )
            
            if not allocations:
                allocations = {
                    "user_id": user_id,
                    "type": EnergyPoolType.POOL.value,
                    "allocations": {},
                    "updated_at": datetime.utcnow()
                }
            
            # Adjust allocations
            allocation_map = allocations.get("allocations", {})
            for pool_type, new_value in recommended.items():
                current = allocation_map.get(pool_type, 0.25)  # Default to 25% if not set
                allocation_map[pool_type] = new_value
                
                results["changes"].append({
                    "pool_type": pool_type,
                    "old_value": current,
                    "new_value": new_value
                })
            
            # Save updated allocations
            allocations["allocations"] = allocation_map
            allocations["updated_at"] = datetime.utcnow()
            
            if "_id" in allocations:
                await self.storage.update_document(
                    "energy_allocations", 
                    allocations["_id"], 
                    allocations
                )
            else:
                await self.storage.save_document("energy_allocations", allocations)
                
            results["success"] = True
            
        else:
            raise OptimizationError(f"Unknown optimization type: {optimization_type}")
        
        return results
    
    async def calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate energy system health score from metrics.
        
        Args:
            metrics: Energy system metrics
            
        Returns:
            Health score (0.0 to 1.0)
        """
        scores = []
        
        # Score energy efficiency
        efficiency = metrics.get("efficiency_metrics", {}).get("overall_efficiency", 0.5)
        scores.append(efficiency)
        
        # Score energy depletion issues
        day_metrics = metrics.get("day_metrics", {})
        depletion_count = day_metrics.get("depletion_count", 0)
        depletion_score = max(0, min(1, 1.0 - (depletion_count / 10)))
        scores.append(depletion_score)
        
        # Score energy utilization
        energy_available = metrics.get("total_energy_available", 0)
        max_energy = metrics.get("pool_metrics", {}).get("max_energy", 150)
        
        # Best utilization is around 50-70% of max
        if max_energy == 0:
            utilization_score = 0
        else:
            utilization_ratio = energy_available / max_energy
            if utilization_ratio < 0.2:
                utilization_score = utilization_ratio * 5  # Linearly increase from 0 to 1
            elif utilization_ratio < 0.7:
                utilization_score = 1.0  # Optimal range
            else:
                utilization_score = max(0, 1.0 - (utilization_ratio - 0.7) * 3)  # Drop quickly above 70%
                
        scores.append(utilization_score)
        
        # Calculate overall score with equal weights
        return sum(scores) / len(scores) if scores else 0.5
    
    def _calculate_transaction_metrics(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from energy transactions.
        
        Args:
            transactions: List of energy transactions
            
        Returns:
            Transaction metrics
        """
        metrics = {
            "total_consumption": 0,
            "total_generation": 0,
            "net_change": 0,
            "component_usage": {},
            "transaction_types": {},
            "depletion_count": 0
        }
        
        for tx in transactions:
            amount = tx.get("amount", 0)
            component = tx.get("component", "unknown")
            tx_type = tx.get("transaction_type", "unknown")
            reason = tx.get("reason", "unknown")
            
            # Update component usage
            if component not in metrics["component_usage"]:
                metrics["component_usage"][component] = {
                    "consumption": 0,
                    "generation": 0,
                    "net": 0,
                    "transaction_count": 0
                }
                
            # Update transaction types
            if tx_type not in metrics["transaction_types"]:
                metrics["transaction_types"][tx_type] = {
                    "amount": 0,
                    "count": 0
                }
            
            # Update metrics
            metrics["component_usage"][component]["transaction_count"] += 1
            metrics["transaction_types"][tx_type]["count"] += 1
            
            if amount < 0:  # Consumption
                abs_amount = abs(amount)
                metrics["total_consumption"] += abs_amount
                metrics["component_usage"][component]["consumption"] += abs_amount
                
                # Check for depletion errors
                if reason == "insufficient_energy":
                    metrics["depletion_count"] += 1
                
            else:  # Generation
                metrics["total_generation"] += amount
                metrics["component_usage"][component]["generation"] += amount
                
            # Update net changes
            metrics["net_change"] += amount
            metrics["component_usage"][component]["net"] += amount
            metrics["transaction_types"][tx_type]["amount"] += amount
        
        return metrics
    
    def _calculate_pool_metrics(self, pools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from energy pools.
        
        Args:
            pools: List of energy pools
            
        Returns:
            Pool metrics
        """
        metrics = {
            "pool_count": len(pools),
            "total_energy": 0,
            "total_max": 0,
            "fill_percentage": 0,
            "replenishment_rate": 0,
            "decay_rate": 0,
            "pool_allocations": {}
        }
        
        if not pools:
            return metrics
        
        # Calculate totals
        for pool in pools:
            current = pool.get("current_energy", 0)
            max_energy = pool.get("max_energy", 0)
            replenish_rate = pool.get("replenish_rate", 0)
            decay_rate = pool.get("decay_rate", 0)
            pool_type = pool.get("pool_type", "unknown")
            
            metrics["total_energy"] += current
            metrics["total_max"] += max_energy
            metrics["replenishment_rate"] += replenish_rate
            
            if pool_type and max_energy > 0:
                metrics["pool_allocations"][pool_type] = max_energy / metrics["total_max"] if metrics["total_max"] > 0 else 0
        
        # Calculate averages
        metrics["fill_percentage"] = metrics["total_energy"] / metrics["total_max"] if metrics["total_max"] > 0 else 0
        metrics["replenishment_rate"] = metrics["replenishment_rate"] / len(pools)
        metrics["decay_rate"] = decay_rate  # Use the last one (should be same for all)
        
        return metrics
    
    def _calculate_efficiency_metrics(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate component efficiency metrics.
        
        Args:
            transactions: List of energy transactions
            
        Returns:
            Efficiency metrics
        """
        metrics = {
            "component_efficiency": {},
            "overall_efficiency": 0.0
        }
        
        # Calculate energy consumed by each component
        component_energy = {}
        component_value = {}
        total_consumed = 0
        total_value = 0
        
        for tx in transactions:
            amount = tx.get("amount", 0)
            component = tx.get("component", "unknown")
            value_generated = tx.get("value_generated", 0)  # This would be set by components
            
            if component not in component_energy:
                component_energy[component] = 0
                component_value[component] = 0
            
            if amount < 0:  # Consumption
                abs_amount = abs(amount)
                component_energy[component] += abs_amount
                total_consumed += abs_amount
                
            # Accumulate value
            component_value[component] += value_generated
            total_value += value_generated
        
        # Calculate efficiency scores
        for component, energy in component_energy.items():
            value = component_value.get(component, 0)
            
            if energy > 0:
                efficiency = value / energy
            else:
                efficiency = 1.0  # No energy used, assume perfect efficiency
                
            metrics["component_efficiency"][component] = {
                "energy_consumed": energy,
                "value_generated": value,
                "efficiency_score": efficiency
            }
        
        # Calculate overall efficiency
        if total_consumed > 0:
            metrics["overall_efficiency"] = total_value / total_consumed
        else:
            metrics["overall_efficiency"] = 1.0  # No energy used, assume perfect efficiency
        
        return metrics