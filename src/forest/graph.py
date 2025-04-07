"""Knowledge graph manager.

This module provides functionality for managing the knowledge graph,
including creating, updating, and querying nodes and edges.
"""
import logging
import uuid
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from bson import ObjectId

from src.storage.mongodb import MongoDBProvider
from src.forest.models import Node, Edge, KnowledgeExtractionResult, PlacementDecision, GraphUpdateResult
from src.forest.placement import KnowledgePlacementService
from src.common.config import get_settings
from src.common.exceptions import GraphError

settings = get_settings()
logger = logging.getLogger(__name__)

class KnowledgeGraphManager:
    """Knowledge graph manager for operating on the knowledge graph."""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None,
                placement_service: Optional[KnowledgePlacementService] = None):
        """Initialize the knowledge graph manager.
        
        Args:
            storage_provider: Optional storage provider.
            placement_service: Optional placement service.
        """
        self.storage = storage_provider
        self.placement_service = placement_service
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize placement service if not provided
        if self.placement_service is None:
            self.placement_service = KnowledgePlacementService(storage_provider=self.storage)
    
    async def update_graph(self, extraction_result: KnowledgeExtractionResult, 
                         placement_decision: PlacementDecision,
                         user_id: str, conversation_id: str, message_id: str) -> GraphUpdateResult:
        """Update the knowledge graph with new information.
        
        Args:
            extraction_result: The extraction result.
            placement_decision: The placement decision.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            
        Returns:
            The update result.
            
        Raises:
            GraphError: If graph update fails.
        """
        try:
            # Ensure storage is connected
            connected = await self.storage.is_connected()
            if not connected:
                await self.storage.connect()
                
            # Initialize result tracking
            nodes_created = []
            nodes_updated = []
            edges_created = []
            folded_topics = [] # Initialize folded_topics to an empty list
            
            # Get the action type from placement decision
            action_type = placement_decision.action_type
            
            # Handle based on action type
            if action_type == "create_new":
                # Create a new root node
                node_id = await self._create_root_node(
                    extraction_result=extraction_result,
                    topic_cluster_id=placement_decision.target_topic_cluster_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id
                )
                nodes_created.append(node_id)
                
            elif action_type == "create_child":
                # Create a child node
                parent_node_id = placement_decision.parent_node_info.get("_id")
                relationship_type = placement_decision.relationship_to_parent
                
                node_id = await self._create_child_node(
                    extraction_result=extraction_result,
                    parent_node_id=parent_node_id,
                    relationship_type=relationship_type,
                    topic_cluster_id=placement_decision.target_topic_cluster_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id
                )
                nodes_created.append(node_id)
                
                # Create edge between parent and child
                edge_id = await self._create_edge(
                    source_node_id=parent_node_id,
                    target_node_id=node_id,
                    relationship_type=relationship_type,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id
                )
                edges_created.append(edge_id)
                
            elif action_type == "update_existing":
                # Update existing node
                node_id = placement_decision.parent_node_info.get("_id")
                await self._update_node(
                    node_id=node_id,
                    extraction_result=extraction_result,
                    conversation_id=conversation_id,
                    message_id=message_id
                )
                nodes_updated.append(node_id)
            
            # Process extracted relationships
            relation_results = await self._process_relationships(
                extraction_result=extraction_result,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )
            
            # Add relationship results to the overall results
            nodes_created.extend(relation_results.get("nodes_created", []))
            edges_created.extend(relation_results.get("edges_created", []))
            
            # Create and return the result
            result = GraphUpdateResult(
                nodes_created=nodes_created,
                nodes_updated=nodes_updated,
                edges_created=edges_created
            )
            
            # Add folded topic summary nodes if any
            if folded_topics:
                await self._add_folded_topic_nodes(result, user_id, folded_topics)
            
            return result
            
        except Exception as e:
            logger.error(f"Graph update failed: {str(e)}")
            raise GraphError(f"Failed to update graph: {str(e)}")
    
    async def _create_root_node(self, extraction_result: KnowledgeExtractionResult,
                             topic_cluster_id: str, user_id: str,
                             conversation_id: str, message_id: str) -> str:
        """Create a new root node.
        
        Args:
            extraction_result: The extraction result.
            topic_cluster_id: The topic cluster ID.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            
        Returns:
            The node ID.
        """
        # Extract a primary entity or use summary as label
        label = extraction_result.summary
        if extraction_result.entities and len(extraction_result.entities) > 0:
            # Find the most important entity (prefer concepts over keywords)
            concepts = [e for e in extraction_result.entities if e.get("type") == "concept"]
            if concepts:
                label = concepts[0].get("text", label)
            else:
                # Use the first entity as a fallback
                label = extraction_result.entities[0].get("text", label)
        
        # Truncate label if too long
        if len(label) > 100:
            label = label[:97] + "..."
            
        # Create the node
        node = Node(
            user_id=user_id,
            label=label,
            type="topic",  # Root nodes are topics
            summary=extraction_result.summary,
            embedding=extraction_result.embedding,
            conversation_ids=[conversation_id],
            message_ids=[message_id],
            topic_cluster_id=topic_cluster_id,
            visual_attributes={
                "color": "#4682B4",  # Steel blue
                "size": 1.5
            },
            importance_score=1.0  # Root nodes have high importance
        )
        
        # Save the node
        node_dict = node.dict(by_alias=True, exclude_none=True)
        node_id = await self.storage.save_document("nodes", node_dict)
        
        return node_id
    
    async def _create_child_node(self, extraction_result: KnowledgeExtractionResult,
                              parent_node_id: str, relationship_type: str,
                              topic_cluster_id: str, user_id: str,
                              conversation_id: str, message_id: str) -> str:
        """Create a child node.
        
        Args:
            extraction_result: The extraction result.
            parent_node_id: The parent node ID.
            relationship_type: The relationship type.
            topic_cluster_id: The topic cluster ID.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            
        Returns:
            The node ID.
        """
        # Extract a primary entity or use summary as label
        label = extraction_result.summary
        node_type = "concept"  # Default type for child nodes
        
        if extraction_result.entities and len(extraction_result.entities) > 0:
            # Find the most important entity based on type
            for type_priority in ["concept", "entity", "keyword", "question"]:
                entities = [e for e in extraction_result.entities if e.get("type") == type_priority]
                if entities:
                    label = entities[0].get("text", label)
                    node_type = type_priority
                    break
        
        # Truncate label if too long
        if len(label) > 100:
            label = label[:97] + "..."
            
        # Create the node
        node = Node(
            user_id=user_id,
            label=label,
            type=node_type,
            summary=extraction_result.summary,
            embedding=extraction_result.embedding,
            conversation_ids=[conversation_id],
            message_ids=[message_id],
            parent_node_id=parent_node_id,
            topic_cluster_id=topic_cluster_id,
            visual_attributes={
                "color": self._get_color_for_node_type(node_type),
                "size": 1.0
            }
        )
        
        # Save the node
        node_dict = node.dict(by_alias=True, exclude_none=True)
        node_id = await self.storage.save_document("nodes", node_dict)
        
        return node_id
    
    async def _update_node(self, node_id: str, extraction_result: KnowledgeExtractionResult,
                         conversation_id: str, message_id: str) -> None:
        """Update an existing node.
        
        Args:
            node_id: The node ID.
            extraction_result: The extraction result.
            conversation_id: The conversation ID.
            message_id: The message ID.
        """
        # Get the existing node
        node = await self.storage.get_document("nodes", node_id)
        if not node:
            raise GraphError(f"Node not found: {node_id}")
            
        # Create updated data
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        # Handle array fields manually to avoid ObjectId issues
        # Handle conversation_ids update
        if "conversation_ids" not in node:
            update_data["conversation_ids"] = [conversation_id]
        elif conversation_id not in node["conversation_ids"]:
            update_data["conversation_ids"] = node["conversation_ids"] + [conversation_id]
            
        # Handle message_ids update
        if "message_ids" not in node:
            update_data["message_ids"] = [message_id]
        elif message_id not in node["message_ids"]:
            update_data["message_ids"] = node["message_ids"] + [message_id]
        
        # Merge summaries if both exist
        if node.get("summary") and extraction_result.summary:
            # Simply concatenate for now, could use AI to merge them in the future
            combined_summary = f"{node.get('summary')} {extraction_result.summary}"
            # Truncate if too long
            if len(combined_summary) > 500:
                combined_summary = combined_summary[:497] + "..."
            update_data["summary"] = combined_summary
        elif extraction_result.summary:
            update_data["summary"] = extraction_result.summary
            
        # Don't update the embedding for now
        # This could lead to "embedding drift" over time
        # A separate process could periodically recalculate embeddings
        
        # Update the node
        await self.storage.update_document("nodes", node_id, update_data)
    
    async def _create_edge(self, source_node_id: str, target_node_id: str,
                         relationship_type: str, user_id: str,
                         conversation_id: str, message_id: str,
                         strength: float = 0.8, context_summary: Optional[str] = None) -> str:
        """Create an edge between two nodes.
        
        Args:
            source_node_id: The source node ID.
            target_node_id: The target node ID.
            relationship_type: The relationship type.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            strength: The relationship strength.
            context_summary: Optional context summary.
            
        Returns:
            The edge ID.
        """
        # Create the edge
        edge = Edge(
            user_id=user_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            strength=strength,
            context_summary=context_summary,
            conversation_ids=[conversation_id],
            message_ids=[message_id]
        )
        
        # Save the edge
        edge_dict = edge.dict(by_alias=True, exclude_none=True)
        edge_id = await self.storage.save_document("edges", edge_dict)
        
        return edge_id
    
    async def _process_relationships(self, extraction_result: KnowledgeExtractionResult,
                                  user_id: str, conversation_id: str, message_id: str) -> Dict[str, List[str]]:
        """Process extracted relationships.
        
        Args:
            extraction_result: The extraction result.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            
        Returns:
            Dictionary with 'nodes_created' and 'edges_created' lists.
        """
        # Initialize result
        result = {
            "nodes_created": [],
            "edges_created": []
        }
        
        # Skip if no relationships
        if not extraction_result.relationships or len(extraction_result.relationships) == 0:
            return result
            
        # Process each relationship
        for relationship in extraction_result.relationships:
            source_text = relationship.get("source")
            target_text = relationship.get("target")
            rel_type = relationship.get("type", "relates_to")
            strength = relationship.get("strength", 0.7)
            context = relationship.get("context")
            
            if not source_text or not target_text:
                continue
                
            # Find or create source node
            source_node_id = await self._find_or_create_entity_node(
                entity_text=source_text,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )
            
            if source_node_id:
                # Only add to result if it's a new node
                if source_node_id not in result["nodes_created"]:
                    result["nodes_created"].append(source_node_id)
            else:
                continue
                
            # Find or create target node
            target_node_id = await self._find_or_create_entity_node(
                entity_text=target_text,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )
            
            if target_node_id:
                # Only add to result if it's a new node
                if target_node_id not in result["nodes_created"]:
                    result["nodes_created"].append(target_node_id)
            else:
                continue
                
            # Create edge between source and target
            edge_id = await self._create_edge(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relationship_type=rel_type,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                strength=strength,
                context_summary=context
            )
            
            result["edges_created"].append(edge_id)
            
        return result
    
    async def _find_or_create_entity_node(self, entity_text: str, user_id: str,
                                       conversation_id: str, message_id: str) -> Optional[str]:
        """Find or create a node for an entity.
        
        Args:
            entity_text: The entity text.
            user_id: The user ID.
            conversation_id: The conversation ID.
            message_id: The message ID.
            
        Returns:
            The node ID, or None if failed.
        """
        try:
            # Try to find existing node by label
            existing_nodes = await self.storage.find_documents(
                collection="nodes",
                query={
                    "user_id": user_id,
                    "label": entity_text
                },
                limit=1
            )
            
            if existing_nodes and len(existing_nodes) > 0:
                # Update the existing node to add the conversation and message IDs
                node_id = str(existing_nodes[0]["_id"])
                
                # First get the document to check existing arrays
                node_doc = await self.storage.get_document("nodes", node_id)
                
                # Update carefully to avoid ObjectId issues
                update_data = {
                    "updated_at": datetime.utcnow()
                }
                
                # Handle conversation_ids update
                if "conversation_ids" not in node_doc:
                    update_data["conversation_ids"] = [conversation_id]
                elif conversation_id not in node_doc["conversation_ids"]:
                    update_data["conversation_ids"] = node_doc["conversation_ids"] + [conversation_id]
                
                # Handle message_ids update
                if "message_ids" not in node_doc:
                    update_data["message_ids"] = [message_id]
                elif message_id not in node_doc["message_ids"]:
                    update_data["message_ids"] = node_doc["message_ids"] + [message_id]
                
                await self.storage.update_document(
                    collection="nodes",
                    document_id=node_id,
                    update_data=update_data
                )
                
                return node_id
                
            # Create a new node
            node = Node(
                user_id=user_id,
                label=entity_text,
                type=self._guess_entity_type(entity_text),
                summary=f"Entity: {entity_text}",
                conversation_ids=[conversation_id],
                message_ids=[message_id],
                topic_cluster_id=str(uuid.uuid4()),  # Generate a new topic ID
                visual_attributes={
                    "color": "#6B8E23",  # Olive green
                    "size": 0.8
                }
            )
            
            # Save the node
            node_dict = node.dict(by_alias=True, exclude_none=True)
            node_id = await self.storage.save_document("nodes", node_dict)
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to find or create entity node: {str(e)}")
            return None
    
    def _guess_entity_type(self, entity_text: str) -> str:
        """Guess the entity type based on the text.
        
        Args:
            entity_text: The entity text.
            
        Returns:
            The guessed entity type.
        """
        # This is a very simple heuristic and could be improved
        if "?" in entity_text:
            return "question"
        elif entity_text[0].isupper():
            return "entity"
        elif len(entity_text.split()) > 3:
            return "concept"
        else:
            return "keyword"
    
    def _get_color_for_node_type(self, node_type: str) -> str:
        """Get a color for a node type.
        
        Args:
            node_type: The node type.
            
        Returns:
            The color.
        """
        colors = {
            "topic": "#4682B4",  # Steel blue
            "concept": "#6A5ACD",  # Slate blue
            "entity": "#2E8B57",  # Sea green
            "keyword": "#CD853F",  # Peru
            "question": "#8B008B"   # Dark magenta
        }
        
        return colors.get(node_type, "#708090")  # Default: Slate gray
    
    async def get_graph(self, user_id: str, topic_cluster_id: Optional[str] = None,
                      max_depth: int = 3, include_cross_links: bool = True,
                      detail_level: str = "full", folded_topics: Optional[List[str]] = None,
                      time_point: Optional[str] = None) -> Dict[str, Any]:
        """Get a knowledge graph for visualization.
        
        Args:
            user_id: The user ID.
            topic_cluster_id: Optional topic cluster ID. If provided, only nodes in this topic will be included.
            max_depth: Maximum depth of nodes to include.
            include_cross_links: Whether to include cross-links between topics.
            
        Returns:
            A dictionary containing nodes and edges.
            
        Raises:
            GraphError: If graph retrieval fails.
        """
        try:
            # Ensure storage is connected
            connected = await self.storage.is_connected()
            if not connected:
                await self.storage.connect()
                
            # Initialize result
            result = {
                "nodes": [],
                "edges": []
            }
            
            # Base query for nodes
            node_query = {"user_id": user_id}
            
            # Add topic filter if provided
            if topic_cluster_id:
                node_query["topic_cluster_id"] = topic_cluster_id
                
            # Apply time filter if specified
            if time_point:
                try:
                    time_point_dt = datetime.fromisoformat(time_point)
                    node_query["created_at"] = {"$lte": time_point_dt}
                except (ValueError, TypeError):
                    logger.warning(f"Invalid time_point format: {time_point}, ignoring time filter")
            
            # Get root nodes (nodes without a parent)
            if topic_cluster_id:
                # If topic is specified, get all nodes in the topic
                root_nodes = await self.storage.find_documents(
                    collection="nodes",
                    query=node_query
                )
            else:
                # Otherwise, get just the root nodes (no parent)
                root_nodes = await self.storage.find_documents(
                    collection="nodes",
                    query={
                        **node_query,
                        "parent_node_id": {"$exists": False}
                    }
                )
                
            # Check if the topic should be folded
            folded_topics = folded_topics or []
            
            # Add root nodes to result
            for node in root_nodes:
                node_topic = node.get("topic_cluster_id")
                # If this node's topic is in folded_topics, skip individual nodes
                # (they will be represented by a summary node later)
                if node_topic in folded_topics:
                    continue
                result["nodes"].append(self._format_node_for_output(node, detail_level))
                
            # Get child nodes up to max_depth
            if max_depth > 0:
                # Get all node IDs we have so far
                node_ids = [node["_id"] for node in root_nodes]
                
                # For each depth level
                for depth in range(max_depth):
                    # Skip if no nodes at this level
                    if not node_ids:
                        break
                        
                    # Get children of the current level nodes
                    child_nodes = await self.storage.find_documents(
                        collection="nodes",
                        query={
                            **node_query,
                            "parent_node_id": {"$in": node_ids}
                        }
                    )
                    
                    # Add child nodes to result
                    for node in child_nodes:
                        node_topic = node.get("topic_cluster_id")
                        # Skip nodes from folded topics
                        if node_topic in folded_topics:
                            continue
                        result["nodes"].append(self._format_node_for_output(node, detail_level))
                        
                    # Update node_ids for the next level
                    node_ids = [node["_id"] for node in child_nodes]
                    
            # Get all node IDs in the result
            node_ids = [node["id"] for node in result["nodes"]]
            
            # Get edges between these nodes
            edges = await self.storage.find_documents(
                collection="edges",
                query={
                    "user_id": user_id,
                    "$or": [
                        {"source_node_id": {"$in": node_ids}},
                        {"target_node_id": {"$in": node_ids}}
                    ]
                }
            )
            
            # Add edges to result
            for edge in edges:
                # Only add edges where both source and target are in the result
                source_id = str(edge["source_node_id"])
                target_id = str(edge["target_node_id"])
                
                if source_id in node_ids and target_id in node_ids:
                    result["edges"].append(self._format_edge_for_output(edge))
                    
            # Include cross-links if requested
            if include_cross_links and topic_cluster_id:
                # Get cross-links for this topic
                cross_links = await self.storage.find_documents(
                    collection="edges",
                    query={
                        "user_id": user_id,
                        "relationship_type": "cross_links",
                        "$or": [
                            {"source_node_id": {"$in": node_ids}},
                            {"target_node_id": {"$in": node_ids}}
                        ]
                    }
                )
                
                # For each cross-link
                for edge in cross_links:
                    source_id = str(edge["source_node_id"])
                    target_id = str(edge["target_node_id"])
                    
                    # If the source is in our nodes but the target isn't
                    if source_id in node_ids and target_id not in node_ids:
                        # Get the target node
                        target_node = await self.storage.get_document("nodes", target_id)
                        if target_node:
                            # Check if in folded topic
                            node_topic = target_node.get("topic_cluster_id")
                            if node_topic not in folded_topics:
                                # Add it to our result
                                result["nodes"].append(self._format_node_for_output(target_node, detail_level))
                            # Add the edge
                            result["edges"].append(self._format_edge_for_output(edge))
                            # Update node_ids
                            node_ids.append(target_id)
                            
                    # If the target is in our nodes but the source isn't
                    elif target_id in node_ids and source_id not in node_ids:
                        # Get the source node
                        source_node = await self.storage.get_document("nodes", source_id)
                        if source_node:
                            # Check if in folded topic
                            node_topic = source_node.get("topic_cluster_id")
                            if node_topic not in folded_topics:
                                # Add it to our result
                                result["nodes"].append(self._format_node_for_output(source_node, detail_level))
                            # Add the edge
                            result["edges"].append(self._format_edge_for_output(edge))
                            # Update node_ids
                            node_ids.append(source_id)
                    
            return result
            
        except Exception as e:
            logger.error(f"Graph retrieval failed: {str(e)}")
            raise GraphError(f"Failed to retrieve graph: {str(e)}")
    
    def _format_node_for_output(self, node: Dict[str, Any], detail_level: str = "full") -> Dict[str, Any]:
        """Format a node for output based on detail level.
        
        Args:
            node: The node document.
            detail_level: Level of detail to include ("minimal", "standard", "full").
            
        Returns:
            Formatted node.
        """
        # For minimal detail level (used for distant nodes or performance optimization)
        if detail_level == "minimal":
            formatted = {
                "id": str(node["_id"]),
                "label": node.get("label", "Unnamed"),
                "type": node.get("type", "unknown"),
                "topic_cluster_id": node.get("topic_cluster_id"),
            }
            
            # Add minimal visual attributes
            formatted["visual_attributes"] = {
                "color": self._get_color_for_node_type(node.get("type", "unknown")),
                "size": 0.7  # Smaller size for minimal detail
            }
            
            return formatted
            
        # For standard detail level (default for most views)
        elif detail_level == "standard":
            formatted = {
                "id": str(node["_id"]),
                "label": node.get("label", "Unnamed"),
                "type": node.get("type", "unknown"),
                "topic_cluster_id": node.get("topic_cluster_id"),
                "created_at": node.get("created_at").isoformat() if "created_at" in node else None,
                "updated_at": node.get("updated_at").isoformat() if "updated_at" in node else None,
            }
            
            # Add parent if present
            if "parent_node_id" in node:
                formatted["parent_node_id"] = str(node["parent_node_id"])
                
            # Add visual attributes if present
            if "visual_attributes" in node:
                formatted["visual_attributes"] = node["visual_attributes"]
            else:
                # Default visual attributes
                formatted["visual_attributes"] = {
                    "color": self._get_color_for_node_type(node.get("type", "unknown")),
                    "size": 1.0
                }
                
            # Add importance score if present
            if "importance_score" in node:
                formatted["importance_score"] = node["importance_score"]
                
            return formatted
            
        # For full detail level (used for focused/selected nodes)
        else:  # "full"
            formatted = {
                "id": str(node["_id"]),
                "label": node.get("label", "Unnamed"),
                "type": node.get("type", "unknown"),
                "topic_cluster_id": node.get("topic_cluster_id"),
                "summary": node.get("summary"),
                "created_at": node.get("created_at").isoformat() if "created_at" in node else None,
                "updated_at": node.get("updated_at").isoformat() if "updated_at" in node else None,
                "conversation_ids": [str(id) for id in node.get("conversation_ids", [])],
                "message_ids": [str(id) for id in node.get("message_ids", [])],
            }
            
            # Add parent if present
            if "parent_node_id" in node:
                formatted["parent_node_id"] = str(node["parent_node_id"])
                
            # Add visual attributes if present
            if "visual_attributes" in node:
                formatted["visual_attributes"] = node["visual_attributes"]
            else:
                # Default visual attributes
                formatted["visual_attributes"] = {
                    "color": self._get_color_for_node_type(node.get("type", "unknown")),
                    "size": 1.0
                }
                
            # Add importance score if present
            if "importance_score" in node:
                formatted["importance_score"] = node["importance_score"]
                
            return formatted
    
    async def _add_folded_topic_nodes(self, result: Dict[str, Any], user_id: str, folded_topics: List[str]) -> None:
        """Add summary nodes for folded topics.
        
        Args:
            result: The graph result to modify.
            user_id: The user ID.
            folded_topics: List of topic IDs to fold.
        """
        for topic_id in folded_topics:
            # Query to get nodes in this topic
            topic_nodes = await self.storage.find_documents(
                collection="nodes",
                query={
                    "user_id": user_id,
                    "topic_cluster_id": topic_id
                }
            )
            
            if not topic_nodes:
                continue
                
            # Create a representative node for the topic
            # Find a root node to use as the base for the summary
            root_node = None
            for node in topic_nodes:
                if "parent_node_id" not in node:
                    root_node = node
                    break
                    
            # If no root node found, just use the first node
            if not root_node and topic_nodes:
                root_node = topic_nodes[0]
                
            if not root_node:
                continue
                
            # Count nodes in this topic
            node_count = len(topic_nodes)
            
            # Create a summary node
            summary_node = {
                "id": f"topic_{topic_id}",  # Special ID for folded topic
                "label": f"{root_node.get('label', 'Topic')} ({node_count} nodes)",
                "type": "folded_topic",
                "topic_cluster_id": topic_id,
                "is_folded_topic": True,  # Flag to indicate this is a folded topic
                "node_count": node_count,
                "visual_attributes": {
                    "color": root_node.get("visual_attributes", {}).get("color", "#4682B4"),
                    "size": 2.0,  # Larger size to represent multiple nodes
                    "icon": "folder"  # Suggest using a folder icon
                }
            }
            
            # Add the summary node to the result
            result["nodes"].append(summary_node)
            
            # Find all edges connecting to nodes outside this topic
            # These will connect to our summary node instead
            external_edges = await self.storage.find_documents(
                collection="edges",
                query={
                    "user_id": user_id,
                    "$or": [
                        {
                            "source_node_id": {"$in": [node["_id"] for node in topic_nodes]},
                            "target_node_id": {"$nin": [node["_id"] for node in topic_nodes]}
                        },
                        {
                            "target_node_id": {"$in": [node["_id"] for node in topic_nodes]},
                            "source_node_id": {"$nin": [node["_id"] for node in topic_nodes]}
                        }
                    ]
                }
            )
            
            # Create modified edges to/from the summary node
            for edge in external_edges:
                source_id = str(edge["source_node_id"])
                target_id = str(edge["target_node_id"])
                
                # Check if source or target is in the folded topic
                source_in_topic = any(str(node["_id"]) == source_id for node in topic_nodes)
                target_in_topic = any(str(node["_id"]) == target_id for node in topic_nodes)
                
                # Create a new edge connecting to the summary node
                new_edge = {
                    "id": f"summary_edge_{edge['_id']}",
                    "type": edge.get("relationship_type", "relates_to"),
                    "strength": edge.get("strength", 0.5)
                }
                
                if source_in_topic:
                    new_edge["source"] = f"topic_{topic_id}"
                    new_edge["target"] = target_id
                else:
                    new_edge["source"] = source_id
                    new_edge["target"] = f"topic_{topic_id}"
                    
                # Add the edge to the result
                result["edges"].append(new_edge)
    
    def _format_edge_for_output(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        """Format an edge for output.
        
        Args:
            edge: The edge document.
            
        Returns:
            Formatted edge.
        """
        return {
            "id": str(edge["_id"]),
            "source": str(edge["source_node_id"]),
            "target": str(edge["target_node_id"]),
            "type": edge.get("relationship_type", "relates_to"),
            "strength": edge.get("strength", 0.5)
        }
