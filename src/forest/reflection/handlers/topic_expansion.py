"""Topic expansion task handler.

This module provides the handler for topic expansion tasks.
"""
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from forest.models import (
    ReflectionTask, NodeStatus, AbstractionLevel, RelationshipType
)
from forest.reflection.handlers.base import TaskHandler
from common.exceptions import ExecutionError
from common.decorators import handle_errors

logger = logging.getLogger(__name__)

class TopicExpansionHandler(TaskHandler):
    """Handler for topic expansion tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "topic_expansion"
    
    @handle_errors(error_type=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle topic expansion task.
        
        Args:
            user_id: The user ID
            task: The task
            
        Returns:
            Task result
        """
        result = {
            "success": False,
            "nodes_created": 0,
            "node_ids": [],
            "edge_ids": []
        }
        
        # Get parameters
        description = task.parameters.get("description", "")
        topic_id = task.parameters.get("topic_id")
        
        # If we don't have a topic ID, this might be a completely new topic
        if not topic_id:
            # Create a new topic based on the gap description
            if not description:
                result["error"] = "No topic ID or description provided"
                return result
                
            # Extract a topic name from the description
            topic_name = await self._extract_topic_name(description)
            
            # Create a new topic root node
            root_node_id = await self._create_new_topic(user_id, topic_name, description)
            
            if not root_node_id:
                result["error"] = "Failed to create new topic"
                return result
                
            result["nodes_created"] = 1
            result["node_ids"].append(root_node_id)
            
            # Set as topic for further expansion
            topic_id = await self._get_node_topic_id(user_id, root_node_id)
        
        # Generate expansion nodes for the topic
        expansion_results = await self._expand_topic(user_id, topic_id, description)
        
        # Update result
        result["success"] = True
        result["nodes_created"] += expansion_results.get("nodes_created", 0)
        result["node_ids"].extend(expansion_results.get("node_ids", []))
        result["edge_ids"].extend(expansion_results.get("edge_ids", []))
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _extract_topic_name(self, description: str) -> str:
        """Extract a topic name from a description."""
        # Prompt for extracting topic name
        prompt = f"""From the following description, extract a concise topic name (2-5 words):

        Description: {description}

        Topic name: """
        
        # Get response
        response = await self.text_model.generate_text(prompt, max_tokens=50)
        
        # Clean up
        topic_name = response.strip()
        
        # If too long, truncate
        if len(topic_name.split()) > 5:
            words = topic_name.split()[:5]
            topic_name = " ".join(words)
            
        return topic_name
    
    async def _create_new_topic(self, user_id: str, topic_name: str, description: str) -> Optional[str]:
        """Create a new topic root node."""
        try:
            # Create root node
            root_node = {
                "user_id": user_id,
                "label": topic_name,
                "type": "topic",
                "summary": description,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": AbstractionLevel.CONCEPT,
                "importance_score": 0.7,  # Moderately high initial importance
                "certainty_score": 0.6,  # Moderate certainty
                "metadata": {
                    "source": "reflection",
                    "tags": ["topic_root"],
                    "config": {
                        "auto_prune": False  # Don't auto-prune topic roots
                    }
                }
            }
            
            # Save to database
            root_id = await self.storage.save_document("nodes", root_node)
            
            # Now set its own topic_cluster_id to itself
            await self.storage.update_document(
                "nodes",
                root_id,
                {"topic_cluster_id": root_id}
            )
            
            return root_id
            
        except Exception as e:
            logger.error(f"Failed to create topic: {str(e)}")
            return None
    
    async def _get_node_topic_id(self, user_id: str, node_id: str) -> Optional[str]:
        """Get the topic ID for a node."""
        node = await self.storage.get_document("nodes", node_id)
        if not node:
            return None
            
        return node.get("topic_cluster_id")
    
    async def _get_topic_name(self, user_id: str, topic_id: str) -> Optional[str]:
        """Get the name of a topic."""
        # Get the topic root node
        node = await self.storage.get_document("nodes", topic_id)
        if not node:
            return None
            
        return node.get("label", f"Topic {topic_id[:8]}")
    
    async def _expand_topic(self, user_id: str, topic_id: str, context: str) -> Dict[str, Any]:
        """Expand a topic with new nodes."""
        result = {
            "nodes_created": 0,
            "node_ids": [],
            "edge_ids": []
        }
        
        try:
            # Get the topic name
            topic_name = await self._get_topic_name(user_id, topic_id)
            
            if not topic_name:
                return result
                
            # Generate concepts for this topic
            concepts = await self._generate_topic_concepts(topic_name, context)
            
            if not concepts:
                return result
                
            # Create nodes for concepts
            for concept in concepts:
                # Create the node
                node = {
                    "user_id": user_id,
                    "label": concept["name"],
                    "type": "concept",
                    "summary": concept["description"],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "status": NodeStatus.ACTIVE,
                    "topic_cluster_id": topic_id,
                    "abstraction_level": AbstractionLevel.CONCEPT,
                    "importance_score": 0.5,  # Medium importance
                    "certainty_score": 0.6,  # Moderate certainty
                    "metadata": {
                        "source": "reflection",
                        "tags": ["expansion"]
                    }
                }
                
                # Save to database
                node_id = await self.storage.save_document("nodes", node)
                
                # Create edge to topic root
                edge = {
                    "user_id": user_id,
                    "source_node_id": node_id,
                    "target_node_id": topic_id,
                    "relationship_type": RelationshipType.PART_OF,
                    "strength": 0.9,
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "reflection",
                    "certainty_score": 0.8
                }
                
                edge_id = await self.storage.save_document("edges", edge)
                
                # Update results
                result["nodes_created"] += 1
                result["node_ids"].append(node_id)
                result["edge_ids"].append(edge_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to expand topic: {str(e)}")
            return result
    
    async def _generate_topic_concepts(self, topic_name: str, context: str) -> List[Dict[str, str]]:
        """Generate concepts for a topic."""
        # Prompt for generating concepts
        prompt = f"""Generate 3-5 important concepts that would help expand knowledge about the following topic:

        Topic: {topic_name}
        Context: {context}

        For each concept, provide a name and brief description. Ensure the concepts cover different aspects of the topic.

        Format your response as follows (strict JSON format):
        ```json
        [
          {{
            "name": "First Concept Name",
            "description": "Description of first concept"
          }},
          {{
            "name": "Second Concept Name",
            "description": "Description of second concept"
          }}
          // additional concepts...
        ]
        ```
        """
        
        # Get response
        response = await self.text_model.generate_text(prompt, max_tokens=1000)
        
        # Parse JSON
        concepts = []
        try:
            # Extract JSON part
            json_text = response
            if "```json" in response:
                parts = response.split("```json")
                if len(parts) > 1:
                    json_part = parts[1].split("```")[0]
                    json_text = json_part
            
            concepts = json.loads(json_text)
        except Exception as e:
            logger.error(f"Failed to parse concept JSON: {str(e)}")
            
            # Fallback: Create a single concept from the response
            if response:
                concepts = [
                    {
                        "name": topic_name,
                        "description": response[:200]  # Limit length
                    }
                ]
        
        # Ensure we don't exceed a reasonable number
        return concepts[:5]  # Max 5 concepts
