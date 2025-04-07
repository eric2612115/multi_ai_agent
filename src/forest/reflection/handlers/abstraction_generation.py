"""Abstraction generation task handler.

This module provides the handler for abstraction generation tasks.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from src.forest.models import (
    ReflectionTask, NodeStatus, AbstractionLevel, RelationshipType, AbstractionCluster
)
from src.forest.reflection.handlers.base import TaskHandler
from src.common.exceptions import ExecutionError
from src.common.decorators import handle_errors
from src.common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class AbstractionGenerationHandler(TaskHandler):
    """Handler for abstraction generation tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "abstraction_generation"
    
    @handle_errors(error_class=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle abstraction generation task."""
        result = {
            "success": False,
            "abstractions_created": 0,
            "abstraction_ids": []
        }
        
        # Use abstraction generator if available
        if hasattr(self.executor, 'abstraction_generator') and self.executor.abstraction_generator:
            try:
                generator = self.executor.abstraction_generator
                
                # Get parameters
                topic_id = task.parameters.get("topic_id")
                target_level = task.parameters.get("target_level", 4)  # Default to principle level
                node_ids = task.parameters.get("node_ids", task.target_node_ids)
                
                # Generate abstractions
                abstraction_results = await generator.generate_abstractions(
                    user_id=user_id,
                    node_ids=node_ids,
                    topic_id=topic_id,
                    target_level=target_level
                )
                
                # Update result
                result["success"] = True
                result["abstractions_created"] = len(abstraction_results.get("created_abstractions", []))
                result["abstraction_ids"] = abstraction_results.get("created_abstractions", [])
                result["details"] = abstraction_results
                
                # Track energy
                self.energy_consumed = task.energy_cost
                
                return result
            except Exception as e:
                logger.error(f"Error using abstraction generator: {str(e)}")
                # Fall back to internal implementation
        
        # If abstraction generator not available or failed, use internal implementation
        # Get parameters
        topic_id = task.parameters.get("topic_id")
        target_level = task.parameters.get("target_level", 4)  # Default to principle level
        
        # If we have related node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If we have a topic ID, get nodes from that topic
        if topic_id and not node_ids:
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "topic_cluster_id": topic_id,
                    "abstraction_level": {"$lt": target_level}  # Only lower level nodes
                },
                projection={"_id": 1, "label": 1, "summary": 1, "abstraction_level": 1}
            )
            
            node_ids = [node["_id"] for node in nodes]
        
        # If we still don't have nodes, fail
        if not node_ids:
            result["error"] = "No nodes found for abstraction"
            return result
            
        # Find node clusters for abstraction
        clusters = await self._find_abstraction_clusters(
            user_id,
            node_ids,
            target_level
        )
        
        # If no clusters found, report result
        if not clusters:
            result["message"] = "No suitable clusters found for abstraction"
            return result
            
        # Create abstractions for each cluster
        for cluster in clusters:
            abstraction_id = await self._create_abstraction_from_cluster(user_id, cluster)
            
            if abstraction_id:
                result["abstraction_ids"].append(abstraction_id)
        
        # Update result
        result["success"] = True
        result["abstractions_created"] = len(result["abstraction_ids"])
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _find_abstraction_clusters(self, 
                                   user_id: str,
                                   node_ids: List[str],
                                   target_level: int) -> List[AbstractionCluster]:
        """Find clusters of nodes that can be abstracted."""
        # Get full node data
        nodes = []
        for node_id in node_ids:
            node = await self.storage.get_document("nodes", node_id)
            if node and node.get("status") == "active":
                nodes.append(node)
        
        # Skip if we have too few nodes
        if len(nodes) < settings.abstraction.min_cluster_size:
            return []
            
        # Group nodes by abstraction level
        nodes_by_level = {}
        for node in nodes:
            level = node.get("abstraction_level", 2)  # Default to CONCEPT
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node)
        
        # Generate abstraction from each level
        clusters = []
        
        # Start with one level below target
        source_level = target_level - 1
        if source_level in nodes_by_level and len(nodes_by_level[source_level]) >= settings.abstraction.min_cluster_size:
            level_clusters = await self._cluster_nodes_for_abstraction(
                user_id,
                nodes_by_level[source_level],
                target_level
            )
            clusters.extend(level_clusters)
            
        # If no clusters from optimal level, try two levels below
        if not clusters and source_level - 1 > 0:
            source_level = target_level - 2
            if source_level in nodes_by_level and len(nodes_by_level[source_level]) >= settings.abstraction.min_cluster_size:
                level_clusters = await self._cluster_nodes_for_abstraction(
                    user_id,
                    nodes_by_level[source_level],
                    target_level
                )
                clusters.extend(level_clusters)
                
        return clusters
    
    async def _cluster_nodes_for_abstraction(self,
                                       user_id: str,
                                       nodes: List[Dict[str, Any]],
                                       target_level: int) -> List[AbstractionCluster]:
        """Cluster nodes for abstraction."""
        # This is a simplified implementation - in a real system, this would use
        # vector similarity clustering or another sophisticated approach
        
        # For now, we'll just check if nodes are in the same topic
        topic_groups = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id", "unknown")
            if topic_id not in topic_groups:
                topic_groups[topic_id] = []
            topic_groups[topic_id].append(node)
            
        # Create clusters for topics with enough nodes
        clusters = []
        for topic_id, topic_nodes in topic_groups.items():
            if len(topic_nodes) >= settings.abstraction.min_cluster_size:
                # Create an abstraction cluster
                node_ids = [node["_id"] for node in topic_nodes]
                node_labels = [node.get("label", "Unknown") for node in topic_nodes]
                node_summaries = [node.get("summary", "") for node in topic_nodes if node.get("summary")]
                
                # Generate an abstraction using AI
                suggested_label, suggested_summary = await self._generate_abstraction_content(
                    node_labels,
                    node_summaries,
                    target_level
                )
                
                # Create the cluster
                clusters.append(
                    AbstractionCluster(
                        source_node_ids=node_ids,
                        centroid_vector=[],  # Placeholder - would be actual vector in real system
                        coherence_score=0.8,  # Placeholder
                        common_topic_id=topic_id if topic_id != "unknown" else None,
                        suggested_label=suggested_label,
                        suggested_summary=suggested_summary,
                        abstraction_level=target_level
                    )
                )
                
        return clusters
    
    async def _generate_abstraction_content(self,
                                      node_labels: List[str],
                                      node_summaries: List[str],
                                      target_level: int) -> Tuple[str, str]:
        """Generate label and summary for an abstraction."""
        # Prepare the input
        level_names = {
            3: "rule or relationship",
            4: "principle or theory",
            5: "paradigm or framework"
        }
        level_name = level_names.get(target_level, "higher-level concept")
        
        # Prepare the prompt
        prompt = f"""I'll provide you with several related concepts and their descriptions. 
        Please identify a {level_name} that these concepts exemplify or are part of.

        Concepts:
        {', '.join(node_labels)}

        Details:
        {'; '.join(node_summaries[:5])}

        Based on these concepts, please provide:
        1. A concise label for the {level_name} (3-5 words)
        2. A brief summary explaining this {level_name} (2-3 sentences)

        Format your response as:
        Label: [your label]
        Summary: [your summary]
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Parse the response
        label = "Abstract Concept"
        summary = "Generated abstraction from related concepts."
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                if line.startswith("Label:"):
                    label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    summary = line.replace("Summary:", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse abstraction response: {str(e)}")
            
        return label, summary
    
    async def _create_abstraction_from_cluster(self,
                                         user_id: str,
                                         cluster: AbstractionCluster) -> Optional[str]:
        """Create an abstraction node from a cluster."""
        try:
            # Create the node
            abstraction_node = {
                "user_id": user_id,
                "label": cluster.suggested_label,
                "type": "abstraction",
                "summary": cluster.suggested_summary,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": cluster.abstraction_level,
                "abstraction_source_ids": cluster.source_node_ids,
                "abstraction_method": "reflection",
                "topic_cluster_id": cluster.common_topic_id,
                "importance_score": 0.7,  # Start with moderately high importance
                "certainty_score": 0.6,  # Moderate certainty
                "metadata": {
                    "source": "reflection",
                    "tags": ["abstraction", f"level_{cluster.abstraction_level}"],
                    "config": {
                        "auto_prune": False,  # Don't auto-prune abstractions
                        "importance_decay_rate": 0.005  # Slower decay for abstractions
                    }
                }
            }
            
            # Save to database
            abstraction_id = await self.storage.save_document("nodes", abstraction_node)
            
            # Create edges connecting source nodes to this abstraction
            for source_id in cluster.source_node_ids:
                edge = {
                    "user_id": user_id,
                    "source_node_id": source_id,
                    "target_node_id": abstraction_id,
                    "relationship_type": RelationshipType.ABSTRACTED_BY,
                    "strength": 0.8,
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "reflection",
                    "certainty_score": 0.7
                }
                
                await self.storage.save_document("edges", edge)
                
            return abstraction_id
            
        except Exception as e:
            logger.error(f"Failed to create abstraction: {str(e)}")
            return None
