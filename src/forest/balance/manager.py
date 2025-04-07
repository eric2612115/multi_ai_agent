"""Self-balancing manager for knowledge forest.

This module provides functionality for automatically balancing the knowledge forest
to maintain optimal knowledge distribution, growth rate, and connection density.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from src.common.base_service import BaseService
from src.common.decorators import track_energy, handle_errors, log_operation
from src.common.exceptions import BalanceError
from src.storage.mongodb import MongoDBProvider
from src.forest.energy.manager_combined import EnergyManager
from src.forest.energy.models import EnergyPoolType
from src.forest.lifecycle.manager_combined import LifecycleManager
from src.forest.graph import KnowledgeGraphManager
from src.common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class BalanceManager(BaseService):
    """Knowledge forest self-balancing manager.
    
    This class is responsible for maintaining optimal balance in the knowledge forest,
    including topic distribution, growth rate control, and connection density optimization.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                energy_manager: Optional[EnergyManager] = None,
                lifecycle_manager: Optional[LifecycleManager] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None):
        """Initialize the balance manager.
        
        Args:
            storage_provider: Optional storage provider
            energy_manager: Optional energy manager
            lifecycle_manager: Optional lifecycle manager
            graph_manager: Optional graph manager
        """
        super().__init__("balance_manager", storage_provider)
        self.energy_manager = energy_manager
        self.lifecycle_manager = lifecycle_manager
        self.graph_manager = graph_manager
        
        # Lazy initialize components if not provided
        if self.energy_manager is None and self.storage is not None:
            self.energy_manager = EnergyManager(storage_provider=self.storage)
            
        if self.lifecycle_manager is None and self.storage is not None:
            self.lifecycle_manager = LifecycleManager(
                storage_provider=self.storage,
                graph_manager=self.graph_manager
            )
            
        if self.graph_manager is None and self.storage is not None:
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing balance manager")
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup."""
        logger.info("Cleaning up balance manager")
    
    @track_energy(5.0)
    @handle_errors(BalanceError)
    @log_operation("balance_topic_distribution")
    async def balance_topic_distribution(self, user_id: str) -> Dict[str, Any]:
        """Balance topic distribution to ensure even knowledge coverage.
        
        Args:
            user_id: The user ID
            
        Returns:
            Balance operation results
            
        Raises:
            BalanceError: If balancing fails
        """
        result = {
            "topics_balanced": 0,
            "importance_changes": [],
            "energy_adjustments": []
        }
        
        try:
            # Get topic distribution
            topics = await self._get_topic_distribution(user_id)
            
            if not topics:
                logger.info(f"No topics found for user {user_id}")
                return result
                
            # Calculate distribution metrics
            total_nodes = sum(topic["node_count"] for topic in topics)
            target_ratio = 1.0 / len(topics)  # Ideal even distribution
            
            # Find over-represented and under-represented topics
            over_topics = []
            under_topics = []
            
            for topic in topics:
                actual_ratio = topic["node_count"] / total_nodes
                topic["ratio"] = actual_ratio
                topic["target_ratio"] = target_ratio
                topic["ratio_difference"] = actual_ratio - target_ratio
                
                if topic["ratio_difference"] > 0.1:  # 10% over-represented
                    over_topics.append(topic)
                elif topic["ratio_difference"] < -0.1:  # 10% under-represented
                    under_topics.append(topic)
            
            # Sort by difference magnitude
            over_topics.sort(key=lambda t: t["ratio_difference"], reverse=True)
            under_topics.sort(key=lambda t: t["ratio_difference"])
            
            # Balance topics (limit to max 5 topics to avoid over-correction)
            balanced_count = 0
            max_adjustments = 5
            
            for topic in over_topics[:max_adjustments]:
                # Reduce importance of over-represented topics
                await self._adjust_topic_importance(user_id, topic["topic_id"], -0.1)
                result["importance_changes"].append({
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["topic_name"],
                    "change": -0.1,
                    "reason": "over-represented"
                })
                balanced_count += 1
                
                # Adjust energy allocation to reduce growth
                if self.energy_manager:
                    pool_adjustment = -0.2  # Reduce energy allocation by 20%
                    await self._adjust_topic_energy(user_id, topic["topic_id"], pool_adjustment)
                    result["energy_adjustments"].append({
                        "topic_id": topic["topic_id"],
                        "topic_name": topic["topic_name"],
                        "adjustment": pool_adjustment,
                        "reason": "over-represented"
                    })
            
            for topic in under_topics[:max_adjustments]:
                # Increase importance of under-represented topics
                await self._adjust_topic_importance(user_id, topic["topic_id"], 0.1)
                result["importance_changes"].append({
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["topic_name"],
                    "change": 0.1,
                    "reason": "under-represented"
                })
                balanced_count += 1
                
                # Adjust energy allocation to promote growth
                if self.energy_manager:
                    pool_adjustment = 0.2  # Increase energy allocation by 20%
                    await self._adjust_topic_energy(user_id, topic["topic_id"], pool_adjustment)
                    result["energy_adjustments"].append({
                        "topic_id": topic["topic_id"],
                        "topic_name": topic["topic_name"],
                        "adjustment": pool_adjustment,
                        "reason": "under-represented"
                    })
            
            result["topics_balanced"] = balanced_count
            return result
            
        except Exception as e:
            logger.error(f"Failed to balance topic distribution: {str(e)}")
            raise BalanceError(f"Failed to balance topic distribution: {str(e)}")
    
    @track_energy(5.0)
    @handle_errors(BalanceError)
    @log_operation("regulate_growth_rate")
    async def regulate_growth_rate(self, user_id: str, recent_days: int = 7) -> Dict[str, Any]:
        """Regulate knowledge growth rate to prevent runaway growth or stagnation.
        
        Args:
            user_id: The user ID
            recent_days: Number of recent days to analyze
            
        Returns:
            Regulation operation results
            
        Raises:
            BalanceError: If regulation fails
        """
        result = {
            "current_growth_rate": 0.0,
            "target_growth_rate": 0.0,
            "energy_adjusted": False,
            "action_taken": "none",
            "dormancy_threshold_adjusted": False
        }
        
        try:
            # Calculate current growth rate
            growth_metrics = await self._calculate_growth_metrics(user_id, recent_days)
            current_rate = growth_metrics["daily_growth_rate"]
            result["current_growth_rate"] = current_rate
            
            # Get target growth rate from configuration
            target_rate = 0.05  # Default if setting is not available
            if hasattr(settings, 'balance'):
                target_rate = settings.balance.target_growth_rate
            result["target_growth_rate"] = target_rate
            
            # Determine if adjustment is needed
            if abs(current_rate - target_rate) < 0.01:  # Within 1% is acceptable
                result["action_taken"] = "none"
                return result
                
            # Handle excessive growth
            if current_rate > target_rate + 0.05:  # Growth is too fast
                # Reduce available energy
                if self.energy_manager:
                    await self._adjust_global_energy(user_id, -0.2)  # Reduce by 20%
                    result["energy_adjusted"] = True
                
                # Make dormancy threshold stricter
                if self.lifecycle_manager:
                    await self._adjust_dormancy_threshold(user_id, 0.1)  # Increase threshold by 0.1
                    result["dormancy_threshold_adjusted"] = True
                    
                result["action_taken"] = "slow_growth"
                
            # Handle stagnation
            elif current_rate < target_rate - 0.02:  # Growth is too slow
                # Increase available energy
                if self.energy_manager:
                    await self._adjust_global_energy(user_id, 0.2)  # Increase by 20%
                    result["energy_adjusted"] = True
                
                # Make dormancy threshold more lenient
                if self.lifecycle_manager:
                    await self._adjust_dormancy_threshold(user_id, -0.05)  # Decrease threshold by 0.05
                    result["dormancy_threshold_adjusted"] = True
                    
                result["action_taken"] = "promote_growth"
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to regulate growth rate: {str(e)}")
            raise BalanceError(f"Failed to regulate growth rate: {str(e)}")
    
    @track_energy(5.0)
    @handle_errors(BalanceError)
    @log_operation("adjust_connection_density")
    async def adjust_connection_density(self, user_id: str) -> Dict[str, Any]:
        """Adjust connection density to maintain optimal network topology.
        
        Args:
            user_id: The user ID
            
        Returns:
            Adjustment operation results
            
        Raises:
            BalanceError: If adjustment fails
        """
        result = {
            "current_density": 0.0,
            "target_density": 0.0,
            "connections_affected": 0,
            "action_taken": "none"
        }
        
        try:
            # Calculate current connection density
            density_metrics = await self._calculate_connection_density(user_id)
            current_density = density_metrics["global_density"]
            result["current_density"] = current_density
            
            # Get target density from configuration
            target_density = 0.1  # Default if setting is not available
            if hasattr(settings, 'balance'):
                target_density = settings.balance.target_connection_density
            result["target_density"] = target_density
            
            # Determine if adjustment is needed
            if abs(current_density - target_density) < 0.02:  # Within 2% is acceptable
                result["action_taken"] = "none"
                return result
                
            if current_density > target_density + 0.05:  # Too dense
                # Identify and remove low-value connections
                edges_removed = await self._reduce_connection_density(user_id, density_metrics)
                result["connections_affected"] = edges_removed
                result["action_taken"] = "reduce_density"
                
            elif current_density < target_density - 0.03:  # Too sparse
                # Identify and add potential valuable connections
                edges_added = await self._increase_connection_density(user_id, density_metrics)
                result["connections_affected"] = edges_added
                result["action_taken"] = "increase_density"
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to adjust connection density: {str(e)}")
            raise BalanceError(f"Failed to adjust connection density: {str(e)}")
    
    @track_energy(12.0)
    @handle_errors(BalanceError)
    @log_operation("run_balance_cycle")
    async def run_balance_cycle(self, user_id: str) -> Dict[str, Any]:
        """Run a complete balance cycle.
        
        Args:
            user_id: The user ID
            
        Returns:
            Comprehensive balance results
            
        Raises:
            BalanceError: If cycle fails
        """
        result = {
            "topic_balance_results": None,
            "growth_regulation_results": None,
            "connection_density_results": None,
            "timestamp": datetime.utcnow().isoformat(),
            "success": False
        }
        
        try:
            # Run all balancing operations
            topic_results = await self.balance_topic_distribution(user_id)
            growth_results = await self.regulate_growth_rate(user_id)
            density_results = await self.adjust_connection_density(user_id)
            
            # Collect results
            result["topic_balance_results"] = topic_results
            result["growth_regulation_results"] = growth_results
            result["connection_density_results"] = density_results
            result["success"] = True
            
            # Persist balance cycle history
            await self._record_balance_cycle(user_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to run balance cycle: {str(e)}")
            raise BalanceError(f"Failed to run balance cycle: {str(e)}")
    
    async def _get_topic_distribution(self, user_id: str) -> List[Dict[str, Any]]:
        """Get current topic distribution for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of topics with metrics
        """
        # Get all active nodes for the user
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Group by topic
        topics_dict = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if not topic_id:
                continue
                
            if topic_id not in topics_dict:
                # Find the topic name (the label of the topic node)
                topic_node = await self.storage.get_document("nodes", topic_id)
                topic_name = topic_node.get("label", f"Topic {topic_id[:8]}") if topic_node else f"Topic {topic_id[:8]}"
                
                topics_dict[topic_id] = {
                    "topic_id": topic_id,
                    "topic_name": topic_name,
                    "node_count": 0,
                    "avg_importance": 0.0,
                    "nodes": []
                }
                
            topics_dict[topic_id]["node_count"] += 1
            topics_dict[topic_id]["nodes"].append(node["_id"])
            topics_dict[topic_id]["avg_importance"] += node.get("importance_score", 0.5)
        
        # Calculate averages
        for topic_id, topic in topics_dict.items():
            if topic["node_count"] > 0:
                topic["avg_importance"] /= topic["node_count"]
        
        # Convert to list
        return list(topics_dict.values())
    
    async def _adjust_topic_importance(self, user_id: str, topic_id: str, change: float) -> bool:
        """Adjust importance of all nodes in a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            change: Importance score change (positive or negative)
            
        Returns:
            True if adjustment succeeded
        """
        # Get all nodes in the topic
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "topic_cluster_id": topic_id, "status": "active"}
        )
        
        for node in nodes:
            current_importance = node.get("importance_score", 0.5)
            new_importance = max(0.1, min(1.0, current_importance + change))
            
            await self.storage.update_document(
                "nodes",
                node["_id"],
                {"importance_score": new_importance, "updated_at": datetime.utcnow()}
            )
        
        return True
    
    async def _adjust_topic_energy(self, user_id: str, topic_id: str, adjustment: float) -> bool:
        """Adjust energy allocation for a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            adjustment: Energy allocation adjustment factor
            
        Returns:
            True if adjustment succeeded
        """
        # Get current topic allocations
        topic_allocations = await self.storage.find_one(
            "energy_allocations",
            {"user_id": user_id, "type": "topic"}
        )
        
        if not topic_allocations:
            # Create default allocation
            topic_allocations = {
                "user_id": user_id,
                "type": "topic",
                "allocations": {},
                "updated_at": datetime.utcnow()
            }
        
        # Adjust allocation for the topic
        allocations = topic_allocations.get("allocations", {})
        current_allocation = allocations.get(topic_id, 1.0)
        new_allocation = max(0.5, min(2.0, current_allocation * (1.0 + adjustment)))
        allocations[topic_id] = new_allocation
        
        # Update in database
        if "_id" in topic_allocations:
            await self.storage.update_document(
                "energy_allocations",
                topic_allocations["_id"],
                {"allocations": allocations, "updated_at": datetime.utcnow()}
            )
        else:
            topic_allocations["allocations"] = allocations
            await self.storage.save_document("energy_allocations", topic_allocations)
        
        return True
    
    async def _calculate_growth_metrics(self, user_id: str, recent_days: int = 7) -> Dict[str, Any]:
        """Calculate knowledge growth metrics.
        
        Args:
            user_id: The user ID
            recent_days: Number of recent days to analyze
            
        Returns:
            Growth metrics
        """
        # Get current active node count
        current_count = await self.storage.count_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Get node count from recent_days ago
        past_date = datetime.utcnow() - timedelta(days=recent_days)
        
        # This is an approximation since we don't store historical counts explicitly
        # We're counting nodes that existed before past_date and are still active
        past_count = await self.storage.count_documents(
            "nodes",
            {
                "user_id": user_id, 
                "status": "active",
                "created_at": {"$lt": past_date}
            }
        )
        
        # Calculate metrics
        total_growth = current_count - past_count
        daily_growth_rate = total_growth / (current_count * recent_days) if current_count > 0 and recent_days > 0 else 0
        
        # Calculate creation rate per day
        creation_by_day = {}
        recent_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "created_at": {"$gte": past_date}
            }
        )
        
        for node in recent_nodes:
            day = node["created_at"].strftime("%Y-%m-%d")
            if day not in creation_by_day:
                creation_by_day[day] = 0
            creation_by_day[day] += 1
        
        return {
            "current_node_count": current_count,
            "past_node_count": past_count,
            "total_growth": total_growth,
            "daily_growth_rate": daily_growth_rate,
            "creation_by_day": creation_by_day,
            "period_days": recent_days
        }
    
    async def _adjust_global_energy(self, user_id: str, adjustment_factor: float) -> bool:
        """Adjust global energy replenishment rate.
        
        Args:
            user_id: The user ID
            adjustment_factor: Factor to adjust energy replenishment rate
            
        Returns:
            True if adjustment succeeded
        """
        if not self.energy_manager:
            return False
            
        try:
            # Get current replenishment rates
            user_settings = await self.storage.find_one(
                "user_settings",
                {"user_id": user_id}
            )
            
            if not user_settings:
                # Create default settings
                user_settings = {
                    "user_id": user_id,
                    "energy": {
                        "replenish_rate": settings.energy.replenish_rate,
                        "max_energy": settings.energy.max_energy
                    }
                }
            
            # Adjust replenishment rate
            current_rate = user_settings.get("energy", {}).get("replenish_rate", settings.energy.replenish_rate)
            new_rate = current_rate * (1.0 + adjustment_factor)
            
            # Ensure rate is within reasonable bounds
            min_rate = settings.energy.replenish_rate * 0.5
            max_rate = settings.energy.replenish_rate * 2.0
            new_rate = max(min_rate, min(max_rate, new_rate))
            
            # Update settings
            if not user_settings.get("energy"):
                user_settings["energy"] = {}
            
            user_settings["energy"]["replenish_rate"] = new_rate
            
            # Save settings
            if "_id" in user_settings:
                await self.storage.update_document(
                    "user_settings",
                    user_settings["_id"],
                    {"energy.replenish_rate": new_rate}
                )
            else:
                await self.storage.save_document("user_settings", user_settings)
            
            # Update energy manager settings
            await self.energy_manager.update_replenish_rate(user_id, new_rate)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to adjust global energy: {str(e)}")
            return False
    
    async def _adjust_dormancy_threshold(self, user_id: str, adjustment: float) -> bool:
        """Adjust dormancy threshold for lifecycle management.
        
        Args:
            user_id: The user ID
            adjustment: Adjustment to dormancy threshold
            
        Returns:
            True if adjustment succeeded
        """
        if not self.lifecycle_manager:
            return False
            
        try:
            # Get current threshold
            user_settings = await self.storage.find_one(
                "user_settings",
                {"user_id": user_id}
            )
            
            if not user_settings:
                # Create default settings
                user_settings = {
                    "user_id": user_id,
                    "lifecycle": {
                        "dormancy_threshold": settings.lifecycle.node_dormancy_threshold
                    }
                }
            
            # Adjust threshold
            current_threshold = user_settings.get("lifecycle", {}).get(
                "dormancy_threshold", settings.lifecycle.node_dormancy_threshold
            )
            new_threshold = current_threshold + adjustment
            
            # Ensure threshold is within reasonable bounds
            min_threshold = 0.1
            max_threshold = 0.5
            new_threshold = max(min_threshold, min(max_threshold, new_threshold))
            
            # Update settings
            if not user_settings.get("lifecycle"):
                user_settings["lifecycle"] = {}
            
            user_settings["lifecycle"]["dormancy_threshold"] = new_threshold
            
            # Save settings
            if "_id" in user_settings:
                await self.storage.update_document(
                    "user_settings",
                    user_settings["_id"],
                    {"lifecycle.dormancy_threshold": new_threshold}
                )
            else:
                await self.storage.save_document("user_settings", user_settings)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to adjust dormancy threshold: {str(e)}")
            return False
    
    async def _calculate_connection_density(self, user_id: str) -> Dict[str, Any]:
        """Calculate connection density metrics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Connection density metrics
        """
        # Get active nodes and edges
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        node_count = len(nodes)
        edge_count = len(edges)
        
        # Calculate global density
        # In a directed graph, max possible edges is n*(n-1) for n nodes
        max_possible_edges = node_count * (node_count - 1) if node_count > 1 else 1
        global_density = edge_count / max_possible_edges if max_possible_edges > 0 else 0
        
        # Calculate topic-specific densities
        topic_densities = {}
        node_by_id = {node["_id"]: node for node in nodes}
        
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if not topic_id:
                continue
                
            if topic_id not in topic_densities:
                topic_densities[topic_id] = {
                    "nodes": 0,
                    "edges": 0,
                    "density": 0.0
                }
                
            topic_densities[topic_id]["nodes"] += 1
        
        # Count edges within each topic
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            source_node = node_by_id.get(source_id)
            target_node = node_by_id.get(target_id)
            
            if not source_node or not target_node:
                continue
                
            source_topic = source_node.get("topic_cluster_id")
            target_topic = target_node.get("topic_cluster_id")
            
            if source_topic and source_topic == target_topic:
                if source_topic in topic_densities:
                    topic_densities[source_topic]["edges"] += 1
        
        # Calculate density for each topic
        for topic_id, data in topic_densities.items():
            node_count = data["nodes"]
            edge_count = data["edges"]
            max_possible = node_count * (node_count - 1) if node_count > 1 else 1
            data["density"] = edge_count / max_possible if max_possible > 0 else 0
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "global_density": global_density,
            "topic_densities": topic_densities
        }
    
    async def _reduce_connection_density(self, user_id: str, density_metrics: Dict[str, Any]) -> int:
        """Reduce connection density by removing low-value edges.
        
        Args:
            user_id: The user ID
            density_metrics: Connection density metrics
            
        Returns:
            Number of edges removed
        """
        # Identify over-dense topics
        topic_densities = density_metrics.get("topic_densities", {})
        target_density = 0.1  # Default if setting is not available
        if hasattr(settings, 'balance'):
            target_density = settings.balance.target_connection_density
            
        over_dense_topics = [
            topic_id for topic_id, data in topic_densities.items() 
            if data["density"] > target_density + 0.05
        ]
        
        if not over_dense_topics:
            return 0
            
        # Find low-value edges in over-dense topics
        removed_count = 0
        for topic_id in over_dense_topics:
            # Get nodes in this topic
            nodes = await self.storage.find_documents(
                "nodes",
                {"user_id": user_id, "topic_cluster_id": topic_id, "status": "active"}
            )
            
            node_ids = [node["_id"] for node in nodes]
            
            # Find edges within this topic with low strength or certainty
            low_value_edges = await self.storage.find_documents(
                "edges",
                {
                    "user_id": user_id,
                    "source_node_id": {"$in": node_ids},
                    "target_node_id": {"$in": node_ids},
                    "is_active": True,
                    "$or": [
                        {"strength": {"$lt": 0.4}},
                        {"certainty_score": {"$lt": 0.4}}
                    ]
                },
                sort=[("strength", 1)],  # Sort by strength ascending (lowest first)
                limit=5  # Limit to prevent excessive pruning
            )
            
            # Mark edges as inactive
            for edge in low_value_edges:
                await self.storage.update_document(
                    "edges",
                    edge["_id"],
                    {"is_active": False, "updated_at": datetime.utcnow()}
                )
                removed_count += 1
        
        return removed_count
    
    async def _increase_connection_density(self, user_id: str, density_metrics: Dict[str, Any]) -> int:
        """Increase connection density by suggesting new connections.
        
        Args:
            user_id: The user ID
            density_metrics: Connection density metrics
            
        Returns:
            Number of edges added
        """
        # Identify under-dense topics
        topic_densities = density_metrics.get("topic_densities", {})
        target_density = 0.1  # Default if setting is not available
        if hasattr(settings, 'balance'):
            target_density = settings.balance.target_connection_density
            
        under_dense_topics = [
            topic_id for topic_id, data in topic_densities.items() 
            if data["density"] < target_density - 0.03 and data["nodes"] >= 5
        ]
        
        if not under_dense_topics:
            return 0
            
        # For each under-dense topic, find potential new connections
        added_count = 0
        for topic_id in under_dense_topics:
            # Get nodes in this topic
            nodes = await self.storage.find_documents(
                "nodes",
                {"user_id": user_id, "topic_cluster_id": topic_id, "status": "active"}
            )
            
            if len(nodes) < 5:  # Skip if too few nodes
                continue
                
            # Build a map of existing connections
            existing_connections = set()
            node_ids = [node["_id"] for node in nodes]
            
            edges = await self.storage.find_documents(
                "edges",
                {
                    "user_id": user_id,
                    "source_node_id": {"$in": node_ids},
                    "target_node_id": {"$in": node_ids}
                }
            )
            
            for edge in edges:
                source_id = edge["source_node_id"]
                target_id = edge["target_node_id"]
                existing_connections.add(f"{source_id}:{target_id}")
            
            # Find nodes with similar content but no direct connection
            for i, node1 in enumerate(nodes):
                for node2 in nodes[i+1:]:
                    conn_key1 = f"{node1['_id']}:{node2['_id']}"
                    conn_key2 = f"{node2['_id']}:{node1['_id']}"
                    
                    # Skip if connection already exists
                    if conn_key1 in existing_connections or conn_key2 in existing_connections:
                        continue
                    
                    # Check for potential semantic similarity
                    similarity = await self._calculate_node_similarity(node1, node2)
                    
                    if similarity > 0.6:  # Threshold for creating new connection
                        # Create new edge
                        new_edge = {
                            "user_id": user_id,
                            "source_node_id": node1["_id"],
                            "target_node_id": node2["_id"],
                            "relationship_type": "relates_to",
                            "strength": similarity,
                            "created_at": datetime.utcnow(),
                            "is_active": True,
                            "source": "balance_system",
                            "certainty_score": 0.6
                        }
                        
                        await self.storage.save_document("edges", new_edge)
                        added_count += 1
                        
                        # Limit the number of new connections per topic
                        if added_count >= 5:
                            break
                            
                if added_count >= 5:
                    break
        
        return added_count
    
    async def _calculate_node_similarity(self, node1: Dict[str, Any], node2: Dict[str, Any]) -> float:
        """Calculate semantic similarity between two nodes.
        
        Args:
            node1: First node
            node2: Second node
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Use embeddings if available
        if node1.get("embedding") and node2.get("embedding"):
            from numpy import dot, linalg
            
            vec1 = node1["embedding"]
            vec2 = node2["embedding"]
            
            # Calculate cosine similarity
            try:
                similarity = dot(vec1, vec2) / (linalg.norm(vec1) * linalg.norm(vec2))
                return max(0.0, min(1.0, similarity))
            except Exception:
                pass
        
        # Fallback to basic text similarity
        text1 = (node1.get("label", "") + " " + (node1.get("summary", "") or "")).lower()
        text2 = (node2.get("label", "") + " " + (node2.get("summary", "") or "")).lower()
        
        # Simple overlap coefficient
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        min_size = min(len(words1), len(words2))
        
        if min_size == 0:
            return 0.0
            
        return intersection / min_size
    
    async def _record_balance_cycle(self, user_id: str, results: Dict[str, Any]) -> bool:
        """Record balance cycle for historical tracking.
        
        Args:
            user_id: The user ID
            results: Balance cycle results
            
        Returns:
            True if recording succeeded
        """
        try:
            # Create cycle record
            record = {
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "topic_balance": {
                    "topics_balanced": results.get("topic_balance_results", {}).get("topics_balanced", 0),
                    "importance_changes": results.get("topic_balance_results", {}).get("importance_changes", [])
                },
                "growth_regulation": {
                    "current_rate": results.get("growth_regulation_results", {}).get("current_growth_rate", 0.0),
                    "target_rate": results.get("growth_regulation_results", {}).get("target_growth_rate", 0.0),
                    "action_taken": results.get("growth_regulation_results", {}).get("action_taken", "none")
                },
                "connection_density": {
                    "current_density": results.get("connection_density_results", {}).get("current_density", 0.0),
                    "target_density": results.get("connection_density_results", {}).get("target_density", 0.0),
                    "connections_affected": results.get("connection_density_results", {}).get("connections_affected", 0),
                    "action_taken": results.get("connection_density_results", {}).get("action_taken", "none")
                },
                "success": results.get("success", False)
            }
            
            # Save to database
            await self.storage.save_document("balance_cycles", record)
            return True
            
        except Exception as e:
            logger.error(f"Failed to record balance cycle: {str(e)}")
            return False