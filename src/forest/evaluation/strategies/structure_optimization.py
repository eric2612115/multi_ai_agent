"""Structure optimization strategy for AI Knowledge Forest.

This module provides a strategy for optimizing knowledge graph structure
to improve connectivity, topic organization, and overall knowledge coherence.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from src.forest.evaluation.strategies.base import BaseOptimizationStrategy
from src.common.decorators import track_energy, handle_errors
from src.common.exceptions import OptimizationError
from src.common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StructureOptimizationStrategy(BaseOptimizationStrategy):
    """Strategy for optimizing knowledge graph structure."""
    
    @track_energy(10.0)
    @handle_errors(OptimizationError)
    async def evaluate(self, user_id: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate current graph structure and identify optimization opportunities.
        
        Args:
            user_id: User ID
            current_metrics: Current system metrics
            
        Returns:
            Evaluation results with structure optimization recommendations
        """
        results = {
            "recommendations": [],
            "expected_improvements": {},
            "risk_level": "medium",
            "priority": 0
        }
        
        # Get graph structure metrics
        graph_metrics = await self._get_graph_metrics(user_id)
        
        # Look for optimization opportunities
        recommendations = []
        
        # Check for isolated nodes
        if graph_metrics.get("isolated_nodes_count", 0) > 5:
            recommendations.append({
                "type": "connect_isolated_nodes",
                "details": {
                    "node_count": graph_metrics.get("isolated_nodes_count", 0),
                    "max_connections": min(10, graph_metrics.get("isolated_nodes_count", 0))
                },
                "expected_improvement": "Increase graph connectivity by connecting isolated nodes",
                "reason": f"Found {graph_metrics.get('isolated_nodes_count', 0)} isolated nodes"
            })
        
        # Check for sparse topics
        sparse_topics = graph_metrics.get("sparse_topics", [])
        if sparse_topics:
            recommendations.append({
                "type": "densify_sparse_topics",
                "details": {
                    "topic_count": len(sparse_topics),
                    "topic_ids": [topic["topic_id"] for topic in sparse_topics[:5]],
                    "max_new_connections": 20
                },
                "expected_improvement": "Improve topic coherence by adding connections between related nodes",
                "reason": f"Found {len(sparse_topics)} topics with low internal connectivity"
            })
        
        # Check for disconnected topic clusters
        if graph_metrics.get("disconnected_topics_count", 0) > 1:
            recommendations.append({
                "type": "connect_topic_clusters",
                "details": {
                    "topic_count": graph_metrics.get("disconnected_topics_count", 0),
                    "max_cross_connections": 5
                },
                "expected_improvement": "Improve cross-domain knowledge by connecting related topics",
                "reason": f"Found {graph_metrics.get('disconnected_topics_count', 0)} disconnected topic clusters"
            })
        
        # Check for nodes that could be merged
        potential_merges = graph_metrics.get("potential_merges", [])
        if potential_merges:
            recommendations.append({
                "type": "merge_similar_nodes",
                "details": {
                    "merge_count": len(potential_merges),
                    "candidate_pairs": potential_merges[:5]
                },
                "expected_improvement": "Reduce redundancy by merging similar nodes",
                "reason": f"Found {len(potential_merges)} node pairs that could potentially be merged"
            })
        
        results["recommendations"] = recommendations
        results["priority"] = len(recommendations)
        
        if recommendations:
            expected_improvements = {
                "graph_density": "+15-20%" if any(r["type"] == "connect_isolated_nodes" for r in recommendations) else "0%",
                "avg_node_degree": "+10-15%" if any(r["type"] in ["connect_isolated_nodes", "densify_sparse_topics"] for r in recommendations) else "0%",
                "topic_coherence": "+20-25%" if any(r["type"] == "densify_sparse_topics" for r in recommendations) else "0%",
                "cross_domain_connections": "+30-40%" if any(r["type"] == "connect_topic_clusters" for r in recommendations) else "0%",
                "graph_clarity": "+10-15%" if any(r["type"] == "merge_similar_nodes" for r in recommendations) else "0%"
            }
            results["expected_improvements"] = expected_improvements
        
        return results
    
    @track_energy(15.0)
    @handle_errors(OptimizationError)
    async def optimize(self, user_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply structure optimization.
        
        Args:
            user_id: User ID
            parameters: Structure optimization parameters
            
        Returns:
            Optimization results
        """
        result = {
            "actions_taken": [],
            "success": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get current metrics for before/after comparison
        current_metrics = await self._get_graph_metrics(user_id)
        
        optimization_type = parameters.get("type")
        if not optimization_type:
            raise OptimizationError("No optimization type specified")
        
        # Apply the specified optimization
        if optimization_type == "connect_isolated_nodes":
            actions = await self._connect_isolated_nodes(user_id, parameters.get("details", {}))
            result["actions_taken"].extend(actions)
            
        elif optimization_type == "densify_sparse_topics":
            actions = await self._densify_sparse_topics(user_id, parameters.get("details", {}))
            result["actions_taken"].extend(actions)
            
        elif optimization_type == "connect_topic_clusters":
            actions = await self._connect_topic_clusters(user_id, parameters.get("details", {}))
            result["actions_taken"].extend(actions)
            
        elif optimization_type == "merge_similar_nodes":
            actions = await self._merge_similar_nodes(user_id, parameters.get("details", {}))
            result["actions_taken"].extend(actions)
            
        else:
            raise OptimizationError(f"Unknown optimization type: {optimization_type}")
        
        # Record the optimization
        if result["actions_taken"]:
            optimization_id = await self.record_optimization(
                user_id,
                self.name,
                parameters,
                current_metrics,
                result
            )
            
            result["optimization_id"] = optimization_id
            result["success"] = True
        
        return result
    
    async def revert(self, user_id: str, optimization_id: str) -> bool:
        """Revert structure optimization.
        
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
        
        # Get actions from the result
        actions = optimization.get("result", {}).get("actions_taken", [])
        
        if not actions:
            logger.warning(f"No actions to revert for optimization {optimization_id}")
            return False
        
        # Revert each action
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "add_edge":
                # Remove the added edge
                edge_id = action.get("edge_id")
                if edge_id:
                    await self.storage.update_document(
                        "edges",
                        edge_id,
                        {"is_active": False, "updated_at": datetime.utcnow()}
                    )
                    
            elif action_type == "merge_nodes":
                # We can't easily revert merges, but we could mark the merged node as inactive
                # and restore the original nodes (if we kept them)
                merged_node_id = action.get("merged_node_id")
                original_node_ids = action.get("original_node_ids", [])
                
                if merged_node_id:
                    # Mark merged node as dormant
                    await self.storage.update_document(
                        "nodes",
                        merged_node_id,
                        {"status": "dormant", "updated_at": datetime.utcnow()}
                    )
                
                # For a complete reversion, we would need to have stored the original nodes' data
                # and restore them, but that's complex and beyond the scope of this implementation
        
        # Update optimization record
        await self.storage.update_document(
            "optimizations",
            optimization_id,
            {"status": "reverted"}
        )
        
        return True
    
    async def _get_graph_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get detailed graph structure metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Graph structure metrics
        """
        # Get nodes and edges
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        # Basic counts
        node_count = len(nodes)
        edge_count = len(edges)
        
        # Topic analysis
        topic_nodes = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                if topic_id not in topic_nodes:
                    topic_nodes[topic_id] = []
                topic_nodes[topic_id].append(node)
        
        topic_count = len(topic_nodes)
        
        # Calculate node degrees
        node_degrees = {}
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            if source_id not in node_degrees:
                node_degrees[source_id] = 0
            if target_id not in node_degrees:
                node_degrees[target_id] = 0
                
            node_degrees[source_id] += 1
            node_degrees[target_id] += 1
        
        # Find isolated nodes
        isolated_nodes = []
        for node in nodes:
            node_id = node.get("_id")
            if node_id not in node_degrees:
                isolated_nodes.append(node)
        
        # Calculate topic connectivity
        topic_connectivity = {}
        sparse_topics = []
        
        for topic_id, topic_node_list in topic_nodes.items():
            topic_node_ids = [node.get("_id") for node in topic_node_list]
            internal_edges = 0
            
            for edge in edges:
                source_id = edge.get("source_node_id")
                target_id = edge.get("target_node_id")
                
                if source_id in topic_node_ids and target_id in topic_node_ids:
                    internal_edges += 1
            
            # Calculate internal density
            max_possible = len(topic_node_list) * (len(topic_node_list) - 1) if len(topic_node_list) > 1 else 1
            internal_density = internal_edges / max_possible if max_possible > 0 else 0
            
            topic_connectivity[topic_id] = {
                "node_count": len(topic_node_list),
                "internal_edges": internal_edges,
                "internal_density": internal_density
            }
            
            # Check if topic is sparse (low internal density)
            if internal_density < 0.2 and len(topic_node_list) >= 5:
                sparse_topics.append({
                    "topic_id": topic_id,
                    "node_count": len(topic_node_list),
                    "internal_density": internal_density
                })
        
        # Check for disconnected topic clusters
        topic_connections = {}
        for topic_id in topic_nodes.keys():
            topic_connections[topic_id] = set()
        
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            # Find topics for source and target
            source_topic = None
            target_topic = None
            
            for node in nodes:
                if node.get("_id") == source_id:
                    source_topic = node.get("topic_cluster_id")
                if node.get("_id") == target_id:
                    target_topic = node.get("topic_cluster_id")
                
                if source_topic and target_topic:
                    break
            
            # If both nodes have topics and they're different, record connection
            if source_topic and target_topic and source_topic != target_topic:
                topic_connections[source_topic].add(target_topic)
                topic_connections[target_topic].add(source_topic)
        
        # Count disconnected topic clusters
        visited_topics = set()
        disconnected_clusters = 0
        
        for topic_id in topic_nodes.keys():
            if topic_id not in visited_topics:
                # BFS to find connected topics
                queue = [topic_id]
                while queue:
                    current = queue.pop(0)
                    if current not in visited_topics:
                        visited_topics.add(current)
                        for connected in topic_connections.get(current, []):
                            if connected not in visited_topics:
                                queue.append(connected)
                
                disconnected_clusters += 1
        
        # Find potential node merges
        potential_merges = []
        
        # Build node embeddings map
        node_embeddings = {}
        for node in nodes:
            embedding = node.get("embedding")
            if embedding:
                node_embeddings[node.get("_id")] = embedding
        
        # Check for very similar nodes
        if node_embeddings:
            from numpy import dot, linalg
            
            for i, (node_id1, embedding1) in enumerate(node_embeddings.items()):
                for node_id2, embedding2 in list(node_embeddings.items())[i+1:]:
                    # Check if same topic
                    node1 = next((n for n in nodes if n.get("_id") == node_id1), None)
                    node2 = next((n for n in nodes if n.get("_id") == node_id2), None)
                    
                    if not node1 or not node2:
                        continue
                        
                    # Only consider nodes in the same topic
                    if node1.get("topic_cluster_id") != node2.get("topic_cluster_id"):
                        continue
                    
                    # Calculate cosine similarity
                    try:
                        similarity = dot(embedding1, embedding2) / (linalg.norm(embedding1) * linalg.norm(embedding2))
                        
                        # If very similar (>0.92), consider merging
                        if similarity > 0.92:
                            potential_merges.append({
                                "node_id1": node_id1,
                                "node_id2": node_id2,
                                "similarity": float(similarity),
                                "node1_label": node1.get("label"),
                                "node2_label": node2.get("label")
                            })
                    except Exception:
                        pass
        
        # Compile results
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "topic_count": topic_count,
            "isolated_nodes_count": len(isolated_nodes),
            "isolated_nodes": [node.get("_id") for node in isolated_nodes[:10]],  # Limit to 10 examples
            "avg_node_degree": sum(node_degrees.values()) / len(node_degrees) if node_degrees else 0,
            "degree_distribution": self._calculate_degree_distribution(node_degrees),
            "topic_connectivity": topic_connectivity,
            "sparse_topics": sparse_topics,
            "disconnected_topics_count": disconnected_clusters,
            "potential_merges": potential_merges
        }
    
    def _calculate_degree_distribution(self, node_degrees: Dict[str, int]) -> Dict[str, int]:
        """Calculate degree distribution.
        
        Args:
            node_degrees: Map of node IDs to degree values
            
        Returns:
            Degree distribution
        """
        distribution = {}
        for degree in node_degrees.values():
            if degree not in distribution:
                distribution[degree] = 0
            distribution[degree] += 1
        
        return distribution
    
    async def _connect_isolated_nodes(self, user_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Connect isolated nodes to the graph.
        
        Args:
            user_id: User ID
            params: Connection parameters
            
        Returns:
            Actions taken
        """
        max_connections = params.get("max_connections", 10)
        actions_taken = []
        
        # Get isolated nodes
        nodes = await self.storage.find_documents(
            "nodes", 
            {"user_id": user_id, "status": "active"}
        )
        
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        # Find isolated nodes
        node_degrees = {}
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            if source_id not in node_degrees:
                node_degrees[source_id] = 0
            if target_id not in node_degrees:
                node_degrees[target_id] = 0
                
            node_degrees[source_id] += 1
            node_degrees[target_id] += 1
        
        isolated_nodes = []
        for node in nodes:
            node_id = node.get("_id")
            if node_id not in node_degrees:
                isolated_nodes.append(node)
        
        if not isolated_nodes:
            return actions_taken
        
        # Find potential connections for each isolated node
        connections_made = 0
        
        for isolated_node in isolated_nodes:
            if connections_made >= max_connections:
                break
                
            potential_connections = await self._find_potential_connections(isolated_node, nodes)
            
            # Create edges for top connections
            for connection in potential_connections[:2]:  # Connect to up to 2 nodes
                if connections_made >= max_connections:
                    break
                    
                target_node = connection["node"]
                similarity = connection["similarity"]
                
                # Create new edge
                new_edge = {
                    "user_id": user_id,
                    "source_node_id": isolated_node["_id"],
                    "target_node_id": target_node["_id"],
                    "relationship_type": "relates_to",
                    "strength": similarity,
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "structure_optimization",
                    "certainty_score": 0.7,
                    "context_summary": "Connected during structure optimization"
                }
                
                edge_id = await self.storage.save_document("edges", new_edge)
                
                actions_taken.append({
                    "type": "add_edge",
                    "edge_id": edge_id,
                    "source_node_id": isolated_node["_id"],
                    "target_node_id": target_node["_id"],
                    "source_label": isolated_node.get("label", ""),
                    "target_label": target_node.get("label", ""),
                    "similarity": similarity
                })
                
                connections_made += 1
        
        return actions_taken
    
    async def _densify_sparse_topics(self, user_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Increase connectivity within sparse topics.
        
        Args:
            user_id: User ID
            params: Connection parameters
            
        Returns:
            Actions taken
        """
        topic_ids = params.get("topic_ids", [])
        max_new_connections = params.get("max_new_connections", 20)
        actions_taken = []
        
        if not topic_ids:
            return actions_taken
        
        # Get nodes in specified topics
        topic_nodes = {}
        for topic_id in topic_ids:
            nodes = await self.storage.find_documents(
                "nodes",
                {"user_id": user_id, "status": "active", "topic_cluster_id": topic_id}
            )
            topic_nodes[topic_id] = nodes
        
        # Get existing edges
        existing_edges = set()
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            existing_edges.add(f"{source_id}:{target_id}")
            existing_edges.add(f"{target_id}:{source_id}")  # Treat edges as undirected
        
        # Find and create new connections
        connections_made = 0
        
        for topic_id, nodes in topic_nodes.items():
            # Skip topics with too few nodes
            if len(nodes) < 3:
                continue
                
            # Find potential connections within the topic
            for i, node1 in enumerate(nodes):
                for node2 in nodes[i+1:]:
                    # Skip if connection already exists
                    edge_key = f"{node1['_id']}:{node2['_id']}"
                    if edge_key in existing_edges:
                        continue
                    
                    # Calculate similarity
                    similarity = await self._calculate_node_similarity(node1, node2)
                    
                    # Only connect if reasonably similar
                    if similarity > 0.6:
                        # Create new edge
                        new_edge = {
                            "user_id": user_id,
                            "source_node_id": node1["_id"],
                            "target_node_id": node2["_id"],
                            "relationship_type": "relates_to",
                            "strength": similarity,
                            "created_at": datetime.utcnow(),
                            "is_active": True,
                            "source": "structure_optimization",
                            "certainty_score": 0.7,
                            "context_summary": "Connected during topic densification"
                        }
                        
                        edge_id = await self.storage.save_document("edges", new_edge)
                        
                        actions_taken.append({
                            "type": "add_edge",
                            "edge_id": edge_id,
                            "source_node_id": node1["_id"],
                            "target_node_id": node2["_id"],
                            "topic_id": topic_id,
                            "source_label": node1.get("label", ""),
                            "target_label": node2.get("label", ""),
                            "similarity": similarity
                        })
                        
                        connections_made += 1
                        
                        # Update existing edges set
                        existing_edges.add(edge_key)
                        existing_edges.add(f"{node2['_id']}:{node1['_id']}")
                        
                        if connections_made >= max_new_connections:
                            return actions_taken
        
        return actions_taken
    
    async def _connect_topic_clusters(self, user_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Connect disconnected topic clusters.
        
        Args:
            user_id: User ID
            params: Connection parameters
            
        Returns:
            Actions taken
        """
        max_cross_connections = params.get("max_cross_connections", 5)
        actions_taken = []
        
        # Get topic nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Group nodes by topic
        topic_nodes = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                if topic_id not in topic_nodes:
                    topic_nodes[topic_id] = []
                topic_nodes[topic_id].append(node)
        
        # Get existing edges
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        # Create topic connection graph
        topic_connections = {}
        for topic_id in topic_nodes.keys():
            topic_connections[topic_id] = set()
        
        existing_edges = set()
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            existing_edges.add(f"{source_id}:{target_id}")
            
            # Find topics for source and target
            source_topic = None
            target_topic = None
            
            for node in nodes:
                if node.get("_id") == source_id:
                    source_topic = node.get("topic_cluster_id")
                if node.get("_id") == target_id:
                    target_topic = node.get("topic_cluster_id")
                
                if source_topic and target_topic:
                    break
            
            # If both nodes have topics and they're different, record connection
            if source_topic and target_topic and source_topic != target_topic:
                topic_connections[source_topic].add(target_topic)
                topic_connections[target_topic].add(source_topic)
        
        # Find disconnected clusters
        visited_topics = set()
        topic_clusters = []
        
        for topic_id in topic_nodes.keys():
            if topic_id not in visited_topics:
                # New cluster
                cluster = set()
                
                # BFS to find connected topics
                queue = [topic_id]
                while queue:
                    current = queue.pop(0)
                    if current not in visited_topics:
                        visited_topics.add(current)
                        cluster.add(current)
                        for connected in topic_connections.get(current, []):
                            if connected not in visited_topics:
                                queue.append(connected)
                
                topic_clusters.append(cluster)
        
        # Create connections between clusters
        if len(topic_clusters) < 2:
            return actions_taken
        
        connections_made = 0
        
        for i, cluster1 in enumerate(topic_clusters):
            for cluster2 in topic_clusters[i+1:]:
                # Find most similar nodes between these clusters
                best_connections = await self._find_cross_cluster_connections(
                    user_id, cluster1, cluster2, topic_nodes, existing_edges)
                
                # Connect the best matches
                for connection in best_connections[:2]:  # Up to 2 connections per cluster pair
                    if connections_made >= max_cross_connections:
                        return actions_taken
                    
                    node1 = connection["node1"]
                    node2 = connection["node2"]
                    similarity = connection["similarity"]
                    
                    # Create new edge
                    new_edge = {
                        "user_id": user_id,
                        "source_node_id": node1["_id"],
                        "target_node_id": node2["_id"],
                        "relationship_type": "cross_links",
                        "strength": similarity,
                        "created_at": datetime.utcnow(),
                        "is_active": True,
                        "source": "structure_optimization",
                        "certainty_score": 0.7,
                        "context_summary": "Cross-cluster connection created during optimization"
                    }
                    
                    edge_id = await self.storage.save_document("edges", new_edge)
                    
                    actions_taken.append({
                        "type": "add_edge",
                        "edge_id": edge_id,
                        "source_node_id": node1["_id"],
                        "target_node_id": node2["_id"],
                        "source_topic": node1.get("topic_cluster_id"),
                        "target_topic": node2.get("topic_cluster_id"),
                        "source_label": node1.get("label", ""),
                        "target_label": node2.get("label", ""),
                        "similarity": similarity
                    })
                    
                    connections_made += 1
        
        return actions_taken
    
    async def _merge_similar_nodes(self, user_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Merge very similar nodes to reduce redundancy.
        
        Args:
            user_id: User ID
            params: Merge parameters
            
        Returns:
            Actions taken
        """
        candidate_pairs = params.get("candidate_pairs", [])
        actions_taken = []
        
        if not candidate_pairs:
            return actions_taken
        
        # Process each candidate pair
        for pair in candidate_pairs:
            node_id1 = pair.get("node_id1")
            node_id2 = pair.get("node_id2")
            
            if not node_id1 or not node_id2:
                continue
            
            # Get the nodes
            node1 = await self.storage.get_document("nodes", node_id1)
            node2 = await self.storage.get_document("nodes", node_id2)
            
            if not node1 or not node2:
                continue
            
            # Create merged node
            merged_node = {
                "user_id": user_id,
                "label": self._merge_text(node1.get("label", ""), node2.get("label", "")),
                "type": node1.get("type", "concept"),
                "summary": self._merge_text(node1.get("summary", ""), node2.get("summary", "")),
                "content": self._merge_text(node1.get("content", ""), node2.get("content", "")),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "conversation_ids": list(set(node1.get("conversation_ids", []) + node2.get("conversation_ids", []))),
                "message_ids": list(set(node1.get("message_ids", []) + node2.get("message_ids", []))),
                "status": "active",
                "last_status_change": datetime.utcnow(),
                "abstraction_level": node1.get("abstraction_level", 2),  # Use first node's level
                "certainty_score": max(node1.get("certainty_score", 0.7), node2.get("certainty_score", 0.7)),
                "verification_status": "unverified",
                "importance_score": max(node1.get("importance_score", 0.5), node2.get("importance_score", 0.5)),
                "topic_cluster_id": node1.get("topic_cluster_id"),  # Use first node's topic
                "embedding": node1.get("embedding"),  # Use first node's embedding
                "metadata": {
                    "source": "structure_optimization",
                    "merged_from": [node_id1, node_id2],
                    "domain": node1.get("metadata", {}).get("domain"),
                    "tags": list(set((node1.get("metadata", {}).get("tags", []) or []) + 
                                   (node2.get("metadata", {}).get("tags", []) or []))),
                    "last_accessed": datetime.utcnow(),
                    "access_count": 0,
                    "config": node1.get("metadata", {}).get("config", {})
                }
            }
            
            # Save merged node
            merged_node_id = await self.storage.save_document("nodes", merged_node)
            
            # Get all edges connected to original nodes
            edges = await self.storage.find_documents(
                "edges",
                {
                    "user_id": user_id, 
                    "is_active": True,
                    "$or": [
                        {"source_node_id": {"$in": [node_id1, node_id2]}},
                        {"target_node_id": {"$in": [node_id1, node_id2]}}
                    ]
                }
            )
            
            # Keep track of connected nodes to avoid duplicates
            connected_nodes = set()
            
            # Create new edges from merged node to all previously connected nodes
            for edge in edges:
                source_id = edge.get("source_node_id")
                target_id = edge.get("target_node_id")
                
                # Determine the other node ID (not node1 or node2)
                other_node_id = None
                if source_id in [node_id1, node_id2]:
                    other_node_id = target_id
                    is_outgoing = True
                elif target_id in [node_id1, node_id2]:
                    other_node_id = source_id
                    is_outgoing = False
                
                # Skip if this is an edge between the two nodes we're merging
                if other_node_id in [node_id1, node_id2]:
                    continue
                
                # Skip if we already created an edge to this node
                if other_node_id in connected_nodes:
                    continue
                
                connected_nodes.add(other_node_id)
                
                # Create new edge
                new_edge = {
                    "user_id": user_id,
                    "source_node_id": merged_node_id if is_outgoing else other_node_id,
                    "target_node_id": other_node_id if is_outgoing else merged_node_id,
                    "relationship_type": edge.get("relationship_type", "relates_to"),
                    "strength": edge.get("strength", 0.7),
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "structure_optimization",
                    "certainty_score": edge.get("certainty_score", 0.7),
                    "context_summary": edge.get("context_summary", "Created during node merge")
                }
                
                await self.storage.save_document("edges", new_edge)
            
            # Mark original nodes as merged
            await self.storage.update_document(
                "nodes",
                node_id1,
                {"status": "merged", "merged_into": merged_node_id, "updated_at": datetime.utcnow()}
            )
            
            await self.storage.update_document(
                "nodes",
                node_id2,
                {"status": "merged", "merged_into": merged_node_id, "updated_at": datetime.utcnow()}
            )
            
            # Mark original edges as inactive
            for edge in edges:
                await self.storage.update_document(
                    "edges",
                    edge["_id"],
                    {"is_active": False, "updated_at": datetime.utcnow()}
                )
            
            # Record action
            actions_taken.append({
                "type": "merge_nodes",
                "merged_node_id": merged_node_id,
                "original_node_ids": [node_id1, node_id2],
                "original_labels": [node1.get("label", ""), node2.get("label", "")],
                "merged_label": merged_node.get("label", ""),
                "connections_transferred": len(connected_nodes)
            })
        
        return actions_taken
    
    async def _find_potential_connections(self, node: Dict[str, Any], all_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find potential connections for a node.
        
        Args:
            node: The node to find connections for
            all_nodes: All available nodes
            
        Returns:
            List of potential connections with similarity scores
        """
        potential_connections = []
        
        # Use node embedding if available
        node_embedding = node.get("embedding")
        if node_embedding:
            from numpy import dot, linalg
            
            for other_node in all_nodes:
                # Skip self
                if other_node["_id"] == node["_id"]:
                    continue
                
                other_embedding = other_node.get("embedding")
                if other_embedding:
                    try:
                        # Calculate cosine similarity
                        similarity = dot(node_embedding, other_embedding) / (linalg.norm(node_embedding) * linalg.norm(other_embedding))
                        
                        if similarity > 0.5:  # Minimum threshold
                            potential_connections.append({
                                "node": other_node,
                                "similarity": float(similarity)
                            })
                    except Exception:
                        pass
        else:
            # Fallback to text similarity
            for other_node in all_nodes:
                # Skip self
                if other_node["_id"] == node["_id"]:
                    continue
                
                similarity = await self._calculate_node_similarity(node, other_node)
                
                if similarity > 0.5:  # Minimum threshold
                    potential_connections.append({
                        "node": other_node,
                        "similarity": similarity
                    })
        
        # Sort by similarity (highest first)
        potential_connections.sort(key=lambda x: x["similarity"], reverse=True)
        
        return potential_connections
    
    async def _find_cross_cluster_connections(self, 
                                            user_id: str,
                                            cluster1: set, 
                                            cluster2: set,
                                            topic_nodes: Dict[str, List[Dict[str, Any]]],
                                            existing_edges: set) -> List[Dict[str, Any]]:
        """Find potential connections between two clusters.
        
        Args:
            user_id: User ID
            cluster1: First topic cluster
            cluster2: Second topic cluster
            topic_nodes: Map of topic IDs to node lists
            existing_edges: Set of existing edge keys
            
        Returns:
            List of potential connections with similarity scores
        """
        potential_connections = []
        
        # Get embeddings for all nodes
        cluster1_nodes = []
        for topic_id in cluster1:
            cluster1_nodes.extend(topic_nodes.get(topic_id, []))
            
        cluster2_nodes = []
        for topic_id in cluster2:
            cluster2_nodes.extend(topic_nodes.get(topic_id, []))
        
        # Calculate similarities between nodes in different clusters
        for node1 in cluster1_nodes:
            for node2 in cluster2_nodes:
                # Skip if connection already exists
                edge_key = f"{node1['_id']}:{node2['_id']}"
                if edge_key in existing_edges:
                    continue
                
                # Calculate similarity
                similarity = await self._calculate_node_similarity(node1, node2)
                
                if similarity > 0.55:  # Higher threshold for cross-cluster connections
                    potential_connections.append({
                        "node1": node1,
                        "node2": node2,
                        "similarity": similarity
                    })
        
        # Sort by similarity (highest first)
        potential_connections.sort(key=lambda x: x["similarity"], reverse=True)
        
        return potential_connections
    
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
                return float(max(0.0, min(1.0, similarity)))
            except Exception:
                pass
        
        # Fallback to basic text similarity
        text1 = f"{node1.get('label', '')} {node1.get('summary', '')}"
        text2 = f"{node2.get('label', '')} {node2.get('summary', '')}"
        
        # Simple overlap coefficient
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        min_size = min(len(words1), len(words2))
        
        if min_size == 0:
            return 0.0
            
        return intersection / min_size
    
    def _merge_text(self, text1: str, text2: str) -> str:
        """Merge two text strings intelligently.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Merged text
        """
        if not text1:
            return text2
        if not text2:
            return text1
            
        # Simple rules for different types of text
        
        # For short labels, join with slash if different
        if len(text1) < 50 and len(text2) < 50:
            if text1.lower() == text2.lower():
                return text1
            else:
                return f"{text1} / {text2}"
        
        # For summaries and content, pick the longer one and add unique info
        if len(text1) >= len(text2):
            primary = text1
            secondary = text2
        else:
            primary = text2
            secondary = text1
            
        # Check if secondary is mostly contained in primary
        words1 = set(primary.lower().split())
        words2 = set(secondary.lower().split())
        
        overlap = len(words1.intersection(words2)) / len(words2) if words2 else 0
        
        if overlap > 0.8:
            # Secondary mostly contained in primary, just return primary
            return primary
        else:
            # Combine with appropriate separator based on text length
            if len(primary) + len(secondary) < 1000:
                return f"{primary}\n\nAdditional information: {secondary}"
            else:
                # For very long content, just use primary to avoid excessive length
                return primary