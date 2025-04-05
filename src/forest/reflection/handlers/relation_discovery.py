"""Relation discovery task handler.

This module provides the handler for relation discovery tasks.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from forest.models import (
    ReflectionTask, RelationshipType
)
from forest.reflection.handlers.base import TaskHandler
from common.exceptions import ExecutionError
from common.decorators import handle_errors

logger = logging.getLogger(__name__)

class RelationDiscoveryHandler(TaskHandler):
    """Handler for relation discovery tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "relation_discovery"
    
    @handle_errors(error_type=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle relation discovery task."""
        result = {
            "success": False,
            "relations_created": 0,
            "relation_ids": []
        }
        
        # Get parameters
        topic_id = task.parameters.get("topic_id")
        
        # If we have related node IDs, use those
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If we have a topic ID, get nodes from that topic
        if topic_id and not node_ids:
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "topic_cluster_id": topic_id
                },
                projection={"_id": 1, "label": 1}
            )
            
            node_ids = [node["_id"] for node in nodes]
        
        # If we still don't have enough nodes, fail
        if len(node_ids) < 2:
            result["error"] = "Not enough nodes for relation discovery"
            return result
            
        # Discover relations
        discovered_relations = await self._discover_relations(user_id, node_ids)
        
        # Update result
        result["success"] = True
        result["relations_created"] = len(discovered_relations)
        result["relation_ids"] = discovered_relations
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
        
    async def _discover_relations(self,
                             user_id: str,
                             node_ids: List[str]) -> List[str]:
        """Discover relations between nodes."""
        # Get full node data
        nodes = {}
        for node_id in node_ids:
            node = await self.storage.get_document("nodes", node_id)
            if node and node.get("status") == "active":
                nodes[str(node_id)] = node
                
        # Skip if we have too few nodes
        if len(nodes) < 2:
            return []
            
        # Check which pairs already have relationships
        existing_relations = set()
        for source_id in nodes:
            for target_id in nodes:
                if source_id != target_id:
                    # Check if an edge exists in either direction
                    count = await self.storage.count_documents(
                        "edges",
                        {
                            "user_id": user_id,
                            "$or": [
                                {"source_node_id": source_id, "target_node_id": target_id},
                                {"source_node_id": target_id, "target_node_id": source_id}
                            ]
                        }
                    )
                    
                    if count > 0:
                        existing_relations.add(frozenset([source_id, target_id]))
        
        # For remaining pairs, discover relationships
        created_edge_ids = []
        node_id_list = list(nodes.keys())
        
        # Limit number of pairs to analyze to avoid excessive computation
        max_pairs = 10
        pair_count = 0
        
        for i in range(len(node_id_list)):
            for j in range(i+1, len(node_id_list)):
                source_id = node_id_list[i]
                target_id = node_id_list[j]
                
                # Skip if already related
                if frozenset([source_id, target_id]) in existing_relations:
                    continue
                    
                # Discover relationship
                edge_id = await self._analyze_and_create_relationship(
                    user_id,
                    nodes[source_id],
                    nodes[target_id]
                )
                
                if edge_id:
                    created_edge_ids.append(edge_id)
                    
                # Increment pair count
                pair_count += 1
                if pair_count >= max_pairs:
                    break
                    
            if pair_count >= max_pairs:
                break
                
        return created_edge_ids
    
    async def _analyze_and_create_relationship(self,
                                         user_id: str,
                                         source_node: Dict[str, Any],
                                         target_node: Dict[str, Any]) -> Optional[str]:
        """Analyze and create a relationship between two nodes."""
        try:
            # Get node information
            source_label = source_node.get("label", "Unknown")
            source_summary = source_node.get("summary", "")
            
            target_label = target_node.get("label", "Unknown")
            target_summary = target_node.get("summary", "")
            
            # Prepare the prompt
            prompt = f"""I'll provide you with two concepts. Please analyze their relationship.

            Concept 1: {source_label}
            {source_summary}

            Concept 2: {target_label}
            {target_summary}

            What is the most appropriate relationship between these concepts?
            Choose from: relates_to, extends, part_of, causes, explains, contradicts, instance_of, precedes

            Format your response as:
            Relationship: [relationship type]
            Direction: [1->2 or 2->1]
            Explanation: [brief explanation]
            Strength: [a number between 0.0 and 1.0]
            """
            
            # Get the response
            response = await self.text_model.generate_text(prompt, max_tokens=300)
            
            # Parse the response
            relationship_type = RelationshipType.RELATES_TO
            direction = "1->2"
            explanation = ""
            strength = 0.5
            
            try:
                lines = response.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("Relationship:"):
                        rel_text = line.replace("Relationship:", "").strip().lower()
                        # Map to valid RelationshipType
                        for rel_type in RelationshipType:
                            if rel_type.value in rel_text:
                                relationship_type = rel_type
                                break
                    elif line.startswith("Direction:"):
                        direction = line.replace("Direction:", "").strip()
                    elif line.startswith("Explanation:"):
                        explanation = line.replace("Explanation:", "").strip()
                    elif line.startswith("Strength:"):
                        strength_text = line.replace("Strength:", "").strip()
                        try:
                            strength_value = float(strength_text)
                            strength = min(1.0, max(0.0, strength_value))
                        except ValueError:
                            pass
            except Exception as e:
                logger.error(f"Failed to parse relationship response: {str(e)}")
                
            # Create the edge based on direction
            if direction == "2->1":
                # Swap source and target
                source_id = target_node["_id"]
                target_id = source_node["_id"]
            else:
                source_id = source_node["_id"]
                target_id = target_node["_id"]
                
            # Create the edge
            edge = {
                "user_id": user_id,
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": relationship_type,
                "strength": strength,
                "context_summary": explanation,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "source": "reflection",
                "certainty_score": 0.6
            }
            
            # Save to database
            edge_id = await self.storage.save_document("edges", edge)
            
            return edge_id
            
        except Exception as e:
            logger.error(f"Failed to create relationship: {str(e)}")
            return None
