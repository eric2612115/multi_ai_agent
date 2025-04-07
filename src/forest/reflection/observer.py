"""System observer for reflection cycle.

This module provides functionality for collecting and monitoring the system state,
which forms the Observe phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from src.forest.models import SystemStateSnapshot
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import ObservationError

settings = get_settings()
logger = logging.getLogger(__name__)

class SystemObserver:
    """System observer that collects and monitors the system state."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the system observer.
        
        Args:
            storage_provider: Optional storage provider
        """
        self.storage = storage_provider
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Energy cost for observation
        self._energy_cost = 5.0  # Base cost
    
    async def collect_system_state(self, user_id: str) -> SystemStateSnapshot:
        """Collect a snapshot of the system state.
        
        Args:
            user_id: The user ID
            
        Returns:
            System state snapshot
            
        Raises:
            ObservationError: If state collection fails
        """
        try:
            start_time = datetime.utcnow()
            
            # Collect node statistics
            node_count = await self._count_nodes(user_id)
            active_node_count = await self._count_active_nodes(user_id)
            dormant_node_count = await self._count_dormant_nodes(user_id)
            
            # Collect edge statistics
            edge_count = await self._count_edges(user_id)
            
            # Collect topic statistics
            topic_distribution = await self._get_topic_distribution(user_id)
            topics_count = len(topic_distribution)
            
            # Collect abstraction level distribution
            abstraction_level_distribution = await self._get_abstraction_level_distribution(user_id)
            
            # Calculate connectivity metrics
            avg_node_connectivity = await self._calculate_avg_connectivity(user_id)
            
            # Get recently active topics
            recently_active_topics = await self._get_recently_active_topics(user_id)
            
            # Get most accessed nodes
            top_accessed_nodes = await self._get_top_accessed_nodes(user_id)
            
            # Calculate health indicators
            health_indicators = await self._calculate_health_indicators(
                user_id, 
                node_count, 
                edge_count, 
                active_node_count,
                topic_distribution,
                abstraction_level_distribution
            )
            
            # Adjust energy cost based on system size
            self._energy_cost = 5.0 + (node_count / 100)
            
            # Create the snapshot
            snapshot = SystemStateSnapshot(
                timestamp=datetime.utcnow(),
                node_count=node_count,
                edge_count=edge_count,
                active_node_count=active_node_count,
                dormant_node_count=dormant_node_count,
                topics_count=topics_count,
                avg_node_connectivity=avg_node_connectivity,
                topic_distribution=topic_distribution,
                abstraction_level_distribution=abstraction_level_distribution,
                recently_active_topics=recently_active_topics,
                top_accessed_nodes=top_accessed_nodes,
                health_indicators=health_indicators
            )
            
            # Log the duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Collected system state for user {user_id} in {duration:.2f}s")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to collect system state: {str(e)}")
            raise ObservationError(f"Failed to collect system state: {str(e)}")
    
    def get_energy_cost(self) -> float:
        """Get the energy cost of the last observation.
        
        Returns:
            Energy cost
        """
        return self._energy_cost
    
    async def _count_nodes(self, user_id: str) -> int:
        """Count all nodes for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Node count
        """
        return await self.storage.count_documents("nodes", {"user_id": user_id})
    
    async def _count_active_nodes(self, user_id: str) -> int:
        """Count active nodes for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Active node count
        """
        return await self.storage.count_documents(
            "nodes", 
            {
                "user_id": user_id,
                "status": "active"
            }
        )
    
    async def _count_dormant_nodes(self, user_id: str) -> int:
        """Count dormant nodes for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dormant node count
        """
        return await self.storage.count_documents(
            "nodes", 
            {
                "user_id": user_id,
                "status": {"$in": ["dormant", "archived"]}
            }
        )
    
    async def _count_edges(self, user_id: str) -> int:
        """Count all edges for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Edge count
        """
        return await self.storage.count_documents("edges", {"user_id": user_id})
    
    async def _get_topic_distribution(self, user_id: str) -> Dict[str, int]:
        """Get the distribution of nodes across topics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dictionary mapping topic IDs to node counts
        """
        # Aggregation pipeline to count nodes per topic
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$topic_cluster_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        result = await self.storage.aggregate("nodes", pipeline)
        
        # Convert to dictionary
        distribution = {}
        for item in result:
            topic_id = str(item["_id"]) if item["_id"] else "uncategorized"
            distribution[topic_id] = item["count"]
            
        return distribution
    
    async def _get_abstraction_level_distribution(self, user_id: str) -> Dict[int, int]:
        """Get the distribution of nodes across abstraction levels.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dictionary mapping abstraction levels to node counts
        """
        # Aggregation pipeline to count nodes per abstraction level
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$abstraction_level", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        result = await self.storage.aggregate("nodes", pipeline)
        
        # Convert to dictionary
        distribution = {}
        for item in result:
            level = item["_id"] if item["_id"] is not None else 2  # Default to CONCEPT level
            distribution[level] = item["count"]
            
        # Ensure all levels are represented
        for level in range(1, 6):  # Levels 1-5
            if level not in distribution:
                distribution[level] = 0
                
        return distribution
    
    async def _calculate_avg_connectivity(self, user_id: str) -> float:
        """Calculate the average connectivity (degree) of nodes.
        
        Args:
            user_id: The user ID
            
        Returns:
            Average node connectivity
        """
        # Get the node count
        node_count = await self._count_nodes(user_id)
        if node_count == 0:
            return 0.0
            
        # Get the edge count
        edge_count = await self._count_edges(user_id)
        
        # Calculate average connectivity (2 * edges / nodes)
        # Each edge connects 2 nodes, so multiply by 2
        avg_connectivity = (2 * edge_count) / node_count
        
        return avg_connectivity
    
    async def _get_recently_active_topics(self, user_id: str, days: int = 7) -> List[str]:
        """Get topics with recent activity.
        
        Args:
            user_id: The user ID
            days: Number of days to consider recent
            
        Returns:
            List of recently active topic IDs
        """
        # Calculate the cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find nodes updated recently
        recent_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "updated_at": {"$gte": cutoff_date}
            },
            projection={"topic_cluster_id": 1}
        )
        
        # Extract unique topic IDs
        topic_ids = set()
        for node in recent_nodes:
            if "topic_cluster_id" in node and node["topic_cluster_id"]:
                topic_ids.add(str(node["topic_cluster_id"]))
                
        return list(topic_ids)
    
    async def _get_top_accessed_nodes(self, user_id: str, limit: int = 10) -> List[str]:
        """Get the most frequently accessed nodes.
        
        Args:
            user_id: The user ID
            limit: Maximum number of nodes to return
            
        Returns:
            List of node IDs
        """
        # Find nodes with the highest access count
        top_nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id},
            projection={"_id": 1},
            sort=[("metadata.access_count", -1)],
            limit=limit
        )
        
        # Extract node IDs
        node_ids = [str(node["_id"]) for node in top_nodes]
        
        return node_ids
    
    async def _calculate_health_indicators(self, 
                                       user_id: str,
                                       node_count: int,
                                       edge_count: int,
                                       active_node_count: int,
                                       topic_distribution: Dict[str, int],
                                       abstraction_level_distribution: Dict[int, int]) -> Dict[str, float]:
        """Calculate health indicators for the knowledge graph.
        
        Args:
            user_id: The user ID
            node_count: Total node count
            edge_count: Total edge count
            active_node_count: Active node count
            topic_distribution: Topic distribution
            abstraction_level_distribution: Abstraction level distribution
            
        Returns:
            Dictionary of health indicators
        """
        indicators = {}
        
        # Avoid division by zero
        if node_count == 0:
            return {
                "activity_ratio": 0.0,
                "connectivity_ratio": 0.0,
                "topic_balance": 0.0,
                "abstraction_balance": 0.0,
                "overall_health": 0.0
            }
        
        # Activity ratio: active nodes / total nodes
        indicators["activity_ratio"] = active_node_count / node_count if node_count > 0 else 0.0
        
        # Connectivity ratio: edges / nodes (normalized to 0-1)
        max_expected_edges = node_count * (node_count - 1) / 2  # Maximum possible edges in a complete graph
        indicators["connectivity_ratio"] = min(1.0, edge_count / max_expected_edges) if max_expected_edges > 0 else 0.0
        
        # Topic balance: entropy-based measure of topic distribution
        # Higher entropy = more balanced distribution
        topic_counts = list(topic_distribution.values())
        if topic_counts:
            total = sum(topic_counts)
            if total > 0:
                proportions = [count / total for count in topic_counts]
                entropy = -sum(p * (p and self._log2(p) or 0) for p in proportions)  # Avoid log(0)
                max_entropy = self._log2(len(topic_counts))  # Maximum possible entropy
                indicators["topic_balance"] = entropy / max_entropy if max_entropy > 0 else 1.0
            else:
                indicators["topic_balance"] = 0.0
        else:
            indicators["topic_balance"] = 0.0
        
        # Abstraction balance: measure of distribution across abstraction levels
        # Ideal: pyramid shape with more instances (L1) and fewer paradigms (L5)
        if sum(abstraction_level_distribution.values()) > 0:
            # Check if there's a reasonable distribution across levels
            level_counts = [abstraction_level_distribution.get(level, 0) for level in range(1, 6)]
            
            # Calculate the abstraction balance score
            # - Penalize if higher levels have more nodes than lower levels
            # - Reward if there's at least some representation at each level
            
            balance_score = 0.0
            ideal_ratios = [0.5, 0.25, 0.15, 0.07, 0.03]  # Ideal distribution
            
            # Convert to percentages
            total = sum(level_counts)
            actual_ratios = [count / total if total > 0 else 0 for count in level_counts]
            
            # Calculate distance from ideal (lower is better)
            distances = [abs(actual - ideal) for actual, ideal in zip(actual_ratios, ideal_ratios)]
            avg_distance = sum(distances) / len(distances)
            
            # Convert to 0-1 score (1 is best)
            balance_score = 1.0 - min(1.0, avg_distance * 2)
            
            indicators["abstraction_balance"] = balance_score
        else:
            indicators["abstraction_balance"] = 0.0
        
        # Overall health: weighted average of indicators
        indicators["overall_health"] = (
            indicators["activity_ratio"] * 0.25 +
            indicators["connectivity_ratio"] * 0.25 +
            indicators["topic_balance"] * 0.25 +
            indicators["abstraction_balance"] * 0.25
        )
        
        return indicators
    
    def _log2(self, x: float) -> float:
        """Calculate log base 2.
        
        Args:
            x: Value to calculate log for
            
        Returns:
            Log base 2 of x
        """
        import math
        return math.log(x) / math.log(2) if x > 0 else 0.0
