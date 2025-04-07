"""Knowledge graph analyzer for reflection cycle.

This module provides functionality for analyzing the knowledge graph structure,
which forms the Orient phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.forest.models import SystemStateSnapshot
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import AnalysisError

settings = get_settings()
logger = logging.getLogger(__name__)

class KnowledgeAnalyzer:
    """Analyzer for knowledge graph structure and characteristics."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the knowledge analyzer.
        
        Args:
            storage_provider: Optional storage provider
        """
        self.storage = storage_provider
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Energy cost for analysis
        self._energy_cost = 10.0  # Base cost
    
    async def analyze_knowledge_graph(self, 
                                   user_id: str, 
                                   system_state: SystemStateSnapshot) -> Dict[str, Any]:
        """Analyze the knowledge graph structure and identify patterns.
        
        Args:
            user_id: The user ID
            system_state: Current system state
            
        Returns:
            Analysis results
            
        Raises:
            AnalysisError: If analysis fails
        """
        try:
            start_time = datetime.utcnow()
            
            # Initialize results
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "summary": {},
                "topics": [],
                "structure": {},
                "content_quality": {},
                "recommendations": []
            }
            
            # Use system state for basic metrics
            node_count = system_state.node_count
            edge_count = system_state.edge_count
            
            # Skip analysis if the graph is too small
            if node_count < 5:
                results["summary"] = {
                    "status": "insufficient_data",
                    "message": f"Knowledge graph too small for analysis ({node_count} nodes)"
                }
                return results
            
            # Perform topic analysis
            topic_analysis = await self._analyze_topics(
                user_id, 
                system_state.topic_distribution
            )
            results["topics"] = topic_analysis
            
            # Analyze graph structure
            structure_analysis = await self._analyze_structure(
                user_id, 
                system_state
            )
            results["structure"] = structure_analysis
            
            # Analyze content quality
            quality_analysis = await self._analyze_content_quality(
                user_id
            )
            results["content_quality"] = quality_analysis
            
            # Generate recommendations based on the analysis
            recommendations = self._generate_recommendations(
                topic_analysis,
                structure_analysis,
                quality_analysis,
                system_state
            )
            results["recommendations"] = recommendations
            
            # Create summary
            results["summary"] = {
                "status": "analysis_complete",
                "node_count": node_count,
                "edge_count": edge_count,
                "top_topics": [t["topic_id"] for t in topic_analysis[:3]] if topic_analysis else [],
                "health_score": system_state.health_indicators.get("overall_health", 0.0),
                "recommendation_count": len(recommendations)
            }
            
            # Adjust energy cost based on graph size
            self._energy_cost = 10.0 + (node_count / 50)
            
            # Log the duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Analyzed knowledge graph for user {user_id} in {duration:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to analyze knowledge graph: {str(e)}")
            raise AnalysisError(f"Failed to analyze knowledge graph: {str(e)}")
    
    def get_energy_cost(self) -> float:
        """Get the energy cost of the last analysis.
        
        Returns:
            Energy cost
        """
        return self._energy_cost
    
    async def _analyze_topics(self, 
                           user_id: str, 
                           topic_distribution: Dict[str, int]) -> List[Dict[str, Any]]:
        """Analyze topics in the knowledge graph.
        
        Args:
            user_id: The user ID
            topic_distribution: Distribution of nodes across topics
            
        Returns:
            Topic analysis results
        """
        results = []
        
        # Skip if no topics
        if not topic_distribution:
            return results
            
        # Calculate total nodes
        total_nodes = sum(topic_distribution.values())
        
        # Process each topic
        for topic_id, node_count in topic_distribution.items():
            # Skip "uncategorized" or empty topics
            if topic_id == "uncategorized" or topic_id is None or topic_id == "None":
                continue
                
            # Get basic topic info
            topic_info = await self._get_topic_info(user_id, topic_id)
            
            # Calculate topic stats
            percentage = (node_count / total_nodes) * 100 if total_nodes > 0 else 0
            
            # Calculate abstraction distribution for this topic
            abstraction_distribution = await self._get_topic_abstraction_distribution(user_id, topic_id)
            
            # Check abstraction balance
            abstraction_balance = self._calculate_abstraction_balance(abstraction_distribution)
            
            # Get connectivity within the topic
            connectivity = await self._get_topic_connectivity(user_id, topic_id)
            
            # Assess topic health
            health_score = (
                min(1.0, (node_count / 10) * 0.2) +  # Size: 20% weight, max at 10 nodes
                abstraction_balance * 0.4 +           # Abstraction balance: 40% weight
                connectivity * 0.4                    # Connectivity: 40% weight
            )
            
            # Add to results
            results.append({
                "topic_id": topic_id,
                "label": topic_info.get("label", f"Topic {topic_id[:8]}"),
                "node_count": node_count,
                "percentage": percentage,
                "abstraction_distribution": abstraction_distribution,
                "abstraction_balance": abstraction_balance,
                "connectivity": connectivity,
                "health_score": health_score
            })
        
        # Sort by node count (descending)
        results.sort(key=lambda x: x["node_count"], reverse=True)
        
        return results
    
    async def _get_topic_info(self, user_id: str, topic_id: str) -> Dict[str, Any]:
        """Get information about a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            
        Returns:
            Topic information
        """
        # Find the root node of the topic (has no parent)
        root_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id,
                "parent_node_id": {"$exists": False}
            },
            limit=1
        )
        
        if root_nodes and len(root_nodes) > 0:
            root = root_nodes[0]
            return {
                "label": root.get("label", f"Topic {topic_id[:8]}"),
                "summary": root.get("summary", ""),
                "type": root.get("type", "topic")
            }
        
        # If no root found, fall back to any node in the topic
        topic_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id
            },
            limit=1
        )
        
        if topic_nodes and len(topic_nodes) > 0:
            node = topic_nodes[0]
            return {
                "label": node.get("label", f"Topic {topic_id[:8]}"),
                "summary": node.get("summary", ""),
                "type": node.get("type", "unknown")
            }
            
        return {
            "label": f"Topic {topic_id[:8]}",
            "summary": "",
            "type": "unknown"
        }
    
    async def _get_topic_abstraction_distribution(self, 
                                              user_id: str, 
                                              topic_id: str) -> Dict[int, int]:
        """Get the distribution of abstraction levels within a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            
        Returns:
            Distribution of abstraction levels
        """
        # Aggregation pipeline to count nodes per abstraction level
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "topic_cluster_id": topic_id
                }
            },
            {
                "$group": {
                    "_id": "$abstraction_level",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id": 1}
            }
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
    
    def _calculate_abstraction_balance(self, abstraction_distribution: Dict[int, int]) -> float:
        """Calculate how well-balanced the abstraction levels are.
        
        Args:
            abstraction_distribution: Distribution of abstraction levels
            
        Returns:
            Balance score (0.0-1.0)
        """
        # Ideal abstraction pyramid has more lower-level nodes and fewer higher-level nodes
        ideal_ratios = {
            1: 0.5,   # Instances: 50%
            2: 0.25,  # Concepts: 25%
            3: 0.15,  # Rules: 15%
            4: 0.07,  # Principles: 7%
            5: 0.03   # Paradigms: 3%
        }
        
        # Calculate total nodes
        total = sum(abstraction_distribution.values())
        if total == 0:
            return 0.0
            
        # Calculate actual ratios
        actual_ratios = {
            level: (abstraction_distribution.get(level, 0) / total)
            for level in range(1, 6)
        }
        
        # Calculate distance from ideal
        distances = [
            abs(actual_ratios.get(level, 0) - ideal_ratios.get(level, 0))
            for level in range(1, 6)
        ]
        
        # Average distance (lower is better)
        avg_distance = sum(distances) / len(distances)
        
        # Convert to score (0.0-1.0, higher is better)
        balance_score = 1.0 - min(1.0, avg_distance * 2)
        
        return balance_score
    
    async def _get_topic_connectivity(self, user_id: str, topic_id: str) -> float:
        """Calculate connectivity within a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            
        Returns:
            Connectivity score (0.0-1.0)
        """
        # Get nodes in the topic
        nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id
            },
            projection={"_id": 1}
        )
        
        node_count = len(nodes)
        if node_count <= 1:
            return 0.0
            
        # Get node IDs
        node_ids = [node["_id"] for node in nodes]
        
        # Count edges between these nodes
        edge_count = await self.storage.count_documents(
            "edges",
            {
                "user_id": user_id,
                "source_node_id": {"$in": node_ids},
                "target_node_id": {"$in": node_ids}
            }
        )
        
        # Calculate density
        # For a complete graph with n nodes, max edges = n(n-1)/2
        max_edges = (node_count * (node_count - 1)) / 2
        density = edge_count / max_edges if max_edges > 0 else 0.0
        
        # Scale density to a reasonable range
        # Even well-connected graphs rarely approach 100% density
        # A density of 0.2 (20%) is already quite high for most knowledge graphs
        scaled_connectivity = min(1.0, density * 5)
        
        return scaled_connectivity
    
    async def _analyze_structure(self, 
                              user_id: str, 
                              system_state: SystemStateSnapshot) -> Dict[str, Any]:
        """Analyze overall structure of the knowledge graph.
        
        Args:
            user_id: The user ID
            system_state: Current system state
            
        Returns:
            Structure analysis results
        """
        # Extract metrics from system state
        node_count = system_state.node_count
        edge_count = system_state.edge_count
        connectivity = system_state.avg_node_connectivity
        
        # Calculate graph density
        max_edges = (node_count * (node_count - 1)) / 2
        density = edge_count / max_edges if max_edges > 0 else 0.0
        
        # Analyze abstraction level distribution
        abstraction_distribution = system_state.abstraction_level_distribution
        abstraction_balance = self._calculate_abstraction_balance(abstraction_distribution)
        
        # Check for isolated components
        isolated_component_count = await self._count_isolated_components(user_id)
        
        # Calculate cross-topic connections
        cross_topic_connections = await self._count_cross_topic_connections(user_id)
        
        # Calculate a structural health score
        structural_health = (
            min(1.0, connectivity / 4) * 0.3 +          # Connectivity: 30% weight, target avg degree 4
            (1.0 - (isolated_component_count / max(10, node_count/10))) * 0.2 +  # Isolation: 20% weight
            abstraction_balance * 0.3 +                 # Abstraction balance: 30% weight
            min(1.0, cross_topic_connections / max(5, system_state.topics_count)) * 0.2  # Cross-connections: 20% weight
        )
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": density,
            "avg_connectivity": connectivity,
            "abstraction_distribution": abstraction_distribution,
            "abstraction_balance": abstraction_balance,
            "isolated_component_count": isolated_component_count,
            "cross_topic_connections": cross_topic_connections,
            "structural_health": structural_health
        }
    
    async def _count_isolated_components(self, user_id: str) -> int:
        """Count the number of isolated components in the graph.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of isolated components
        """
        # This is a simplified estimate - a full component analysis would require
        # a graph traversal algorithm, which is complex in a database context
        
        # Get all active nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active"
            },
            projection={"_id": 1}
        )
        
        if not nodes:
            return 0
            
        # Count nodes with no connections
        isolated_count = 0
        for node in nodes:
            node_id = node["_id"]
            
            # Check if this node has any edges
            edge_count = await self.storage.count_documents(
                "edges",
                {
                    "user_id": user_id,
                    "$or": [
                        {"source_node_id": node_id},
                        {"target_node_id": node_id}
                    ]
                }
            )
            
            if edge_count == 0:
                isolated_count += 1
                
        return isolated_count
    
    async def _count_cross_topic_connections(self, user_id: str) -> int:
        """Count connections between different topics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of cross-topic connections
        """
        # This requires a more complex query to count edges where source and target
        # are in different topic clusters
        
        # Get all edges
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id},
            projection={"source_node_id": 1, "target_node_id": 1}
        )
        
        if not edges:
            return 0
            
        # For each edge, check if source and target are in different topics
        cross_topic_count = 0
        for edge in edges:
            source_id = edge["source_node_id"]
            target_id = edge["target_node_id"]
            
            # Get source node's topic
            source_node = await self.storage.get_document("nodes", source_id)
            if not source_node:
                continue
                
            source_topic = source_node.get("topic_cluster_id")
            
            # Get target node's topic
            target_node = await self.storage.get_document("nodes", target_id)
            if not target_node:
                continue
                
            target_topic = target_node.get("topic_cluster_id")
            
            # Check if they're different
            if source_topic and target_topic and source_topic != target_topic:
                cross_topic_count += 1
                
        return cross_topic_count
    
    async def _analyze_content_quality(self, user_id: str) -> Dict[str, Any]:
        """Analyze the quality of content in the knowledge graph.
        
        Args:
            user_id: The user ID
            
        Returns:
            Content quality analysis results
        """
        # Get active nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active"
            },
            projection={
                "certainty_score": 1, 
                "verification_status": 1,
                "summary": 1
            }
        )
        
        if not nodes:
            return {
                "avg_certainty": 0.0,
                "verified_ratio": 0.0,
                "avg_summary_length": 0,
                "content_quality_score": 0.0
            }
            
        # Calculate metrics
        node_count = len(nodes)
        
        # Average certainty score
        certainty_scores = [
            node.get("certainty_score", 0.5) 
            for node in nodes
        ]
        avg_certainty = sum(certainty_scores) / node_count if node_count > 0 else 0
        
        # Ratio of verified nodes
        verified_count = sum(
            1 for node in nodes
            if node.get("verification_status") == "verified"
        )
        verified_ratio = verified_count / node_count if node_count > 0 else 0
        
        # Average summary length
        summary_lengths = [
            len(node.get("summary", "")) 
            for node in nodes
            if node.get("summary")
        ]
        avg_summary_length = sum(summary_lengths) / len(summary_lengths) if summary_lengths else 0
        
        # Content quality score
        content_quality = (
            avg_certainty * 0.4 +
            verified_ratio * 0.3 +
            min(1.0, avg_summary_length / 150) * 0.3  # Target 150+ chars
        )
        
        return {
            "avg_certainty": avg_certainty,
            "verified_ratio": verified_ratio,
            "avg_summary_length": avg_summary_length,
            "content_quality_score": content_quality
        }
    
    def _generate_recommendations(self,
                               topic_analysis: List[Dict[str, Any]],
                               structure_analysis: Dict[str, Any],
                               quality_analysis: Dict[str, Any],
                               system_state: SystemStateSnapshot) -> List[Dict[str, Any]]:
        """Generate recommendations based on analysis results.
        
        Args:
            topic_analysis: Topic analysis results
            structure_analysis: Structure analysis results
            quality_analysis: Content quality analysis results
            system_state: Current system state
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Topic-level recommendations
        for topic in topic_analysis:
            topic_id = topic["topic_id"]
            
            # Check abstraction balance
            if topic["abstraction_balance"] < 0.4 and topic["node_count"] >= 5:
                # Which levels are missing?
                abs_dist = topic["abstraction_distribution"]
                
                if abs_dist.get(4, 0) == 0 and abs_dist.get(3, 0) > 0:
                    # Missing principles level
                    recommendations.append({
                        "type": "abstraction_generation",
                        "priority": "high",
                        "target_topic": topic_id,
                        "target_level": 4,
                        "description": f"Generate principle-level abstractions for topic '{topic['label']}'"
                    })
                    
                elif abs_dist.get(3, 0) == 0 and abs_dist.get(2, 0) > 0:
                    # Missing rules level
                    recommendations.append({
                        "type": "abstraction_generation",
                        "priority": "high",
                        "target_topic": topic_id,
                        "target_level": 3,
                        "description": f"Generate rule-level abstractions for topic '{topic['label']}'"
                    })
            
            # Check connectivity
            if topic["connectivity"] < 0.3 and topic["node_count"] >= 5:
                recommendations.append({
                    "type": "relation_discovery",
                    "priority": "medium",
                    "target_topic": topic_id,
                    "description": f"Discover missing relationships in topic '{topic['label']}'"
                })
        
        # Structure-level recommendations
        if structure_analysis["isolated_component_count"] > 0:
            recommendations.append({
                "type": "isolated_component_connection",
                "priority": "high",
                "description": f"Connect {structure_analysis['isolated_component_count']} isolated nodes to the main graph"
            })
            
        if structure_analysis["cross_topic_connections"] < len(topic_analysis) - 1 and len(topic_analysis) > 1:
            recommendations.append({
                "type": "cross_topic_linking",
                "priority": "medium",
                "description": "Discover cross-topic connections to integrate knowledge areas"
            })
            
        if structure_analysis["abstraction_balance"] < 0.4 and system_state.node_count >= 10:
            # Global abstraction recommendation
            abs_dist = structure_analysis["abstraction_distribution"]
            if abs_dist.get(4, 0) == 0 and abs_dist.get(3, 0) > 0:
                recommendations.append({
                    "type": "global_abstraction",
                    "priority": "medium",
                    "target_level": 4,
                    "description": "Generate principle-level abstractions across topics"
                })
                
        # Quality-level recommendations
        if quality_analysis["verified_ratio"] < 0.3 and system_state.node_count >= 10:
            recommendations.append({
                "type": "content_verification",
                "priority": "medium",
                "description": "Verify accuracy of key knowledge nodes"
            })
            
        if quality_analysis["avg_summary_length"] < 50 and system_state.node_count >= 5:
            recommendations.append({
                "type": "summary_enhancement",
                "priority": "low",
                "description": "Enhance node summaries with more detailed information"
            })
            
        # Knowledge lifecycle recommendations - if there are many nodes, consider pruning
        if system_state.node_count > 30:
            # For now, use a simplistic approach to estimate low importance nodes
            low_importance_nodes = int(system_state.node_count * 0.2)  # Assume ~20% are low importance
            if low_importance_nodes > 5:
                recommendations.append({
                    "type": "knowledge_pruning",
                    "priority": "medium",
                    "description": f"Consider dormancy for {low_importance_nodes} low-importance nodes"
                })
        
        # Sort by priority
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_rank.get(r["priority"], 99))
        
        return recommendations
    
    async def _count_low_importance_nodes(self, user_id: str) -> int:
        """Count nodes with low importance scores.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of low importance nodes
        """
        threshold = settings.knowledge_lifecycle.node_dormancy_threshold
        
        count = await self.storage.count_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active",
                "importance_score": {"$lt": threshold}
            }
        )
        
        return count
