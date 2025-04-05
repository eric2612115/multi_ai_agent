"""Public REST API routes for knowledge forest.

This module provides public REST API endpoints for the knowledge forest without authentication.
"""
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path

from forest.graph import KnowledgeGraphManager
from common.initialization import initialize_new_user

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/public/knowledge", tags=["public-knowledge"])

# Dependencies
def get_graph_manager():
    """Get the graph manager."""
    return KnowledgeGraphManager()

# Routes
@router.get("/graph", response_model=Dict[str, Any])
async def get_knowledge_graph(
    user_id: str = Query(..., description="User ID"),
    topic_cluster_id: Optional[str] = Query(None, description="Topic cluster ID"),
    max_depth: int = Query(3, description="Maximum depth of nodes to include"),
    include_cross_links: bool = Query(True, description="Include cross-links between topics"),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get a knowledge graph for visualization (public endpoint).
    
    Args:
        user_id: User ID.
        topic_cluster_id: Optional topic cluster ID.
        max_depth: Maximum depth of nodes to include.
        include_cross_links: Include cross-links between topics.
        graph_manager: The graph manager.
        
    Returns:
        The knowledge graph.
    """
    try:
        # Check if user has data, if not, initialize
        await initialize_new_user(user_id)
        
        # Get the graph
        graph = await graph_manager.get_graph(
            user_id=user_id,
            topic_cluster_id=topic_cluster_id,
            max_depth=max_depth,
            include_cross_links=include_cross_links
        )
        
        return graph
    except Exception as e:
        logger.error(f"Failed to get knowledge graph: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge graph: {str(e)}")

@router.get("/node/{node_id}", response_model=Dict[str, Any])
async def get_node_details(
    node_id: str = Path(..., description="Node ID"),
    user_id: str = Query(..., description="User ID"),
    include_neighbors: bool = Query(False, description="Include connected nodes"),
    include_sources: bool = Query(True, description="Include source conversation and message references"),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get detailed information about a node (public endpoint).
    
    Args:
        node_id: The node ID.
        user_id: The user ID.
        include_neighbors: Whether to include connected nodes.
        include_sources: Whether to include source conversation and message references.
        graph_manager: The graph manager.
        
    Returns:
        Node details with optional neighbors and sources.
    """
    try:
        # Get the node
        node = await graph_manager.storage.get_document("nodes", node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
            
        # Check if the user owns this node
        node_user_id = str(node.get("user_id", ""))
        if node_user_id != str(user_id):
            raise HTTPException(status_code=403, detail="You don't have permission to access this node")
            
        # Format the node
        result = {
            "id": str(node["_id"]),
            "label": node.get("label", "Unnamed"),
            "type": node.get("type", "unknown"),
            "summary": node.get("summary"),
            "topic_cluster_id": node.get("topic_cluster_id"),
            "created_at": node.get("created_at").isoformat() if "created_at" in node else None,
            "updated_at": node.get("updated_at").isoformat() if "updated_at" in node else None,
            "visual_attributes": node.get("visual_attributes", {}),
            "importance_score": node.get("importance_score", 0.0)
        }
        
        # Include source references if requested
        if include_sources:
            result["conversation_ids"] = [str(id) for id in node.get("conversation_ids", [])]
            result["message_ids"] = [str(id) for id in node.get("message_ids", [])]
            
            # Get source messages if available
            if "message_ids" in node and node["message_ids"]:
                messages = []
                for msg_id in node["message_ids"]:
                    message = await graph_manager.storage.get_document("messages", str(msg_id))
                    if message:
                        messages.append({
                            "id": str(message["_id"]),
                            "speaker": message.get("speaker", "unknown"),
                            "text": message.get("text", ""),
                            "timestamp": message.get("timestamp").isoformat() if "timestamp" in message else None
                        })
                        
                result["source_messages"] = messages
        
        # Include neighbors if requested
        if include_neighbors:
            # Get edges connected to this node
            edges = await graph_manager.storage.find_documents(
                collection="edges",
                query={
                    "user_id": str(user_id),
                    "$or": [
                        {"source_node_id": str(node["_id"])},
                        {"target_node_id": str(node["_id"])}
                    ]
                }
            )
            
            # Format edges and get connected nodes
            formatted_edges = []
            neighbor_ids = set()
            
            for edge in edges:
                source_id = str(edge["source_node_id"])
                target_id = str(edge["target_node_id"])
                
                # Add to formatted edges
                formatted_edges.append({
                    "id": str(edge["_id"]),
                    "source": source_id,
                    "target": target_id,
                    "type": edge.get("relationship_type", "relates_to"),
                    "strength": edge.get("strength", 0.5),
                    "context_summary": edge.get("context_summary")
                })
                
                # Add neighbor ID
                if source_id != str(node["_id"]):
                    neighbor_ids.add(source_id)
                if target_id != str(node["_id"]):
                    neighbor_ids.add(target_id)
            
            # Get neighbor nodes
            neighbors = []
            for neighbor_id in neighbor_ids:
                neighbor = await graph_manager.storage.get_document("nodes", neighbor_id)
                if neighbor:
                    neighbors.append({
                        "id": str(neighbor["_id"]),
                        "label": neighbor.get("label", "Unnamed"),
                        "type": neighbor.get("type", "unknown"),
                        "summary": neighbor.get("summary"),
                        "topic_cluster_id": neighbor.get("topic_cluster_id"),
                        "visual_attributes": neighbor.get("visual_attributes", {})
                    })
            
            result["edges"] = formatted_edges
            result["neighbors"] = neighbors
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get node details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get node details: {str(e)}")

@router.get("/search", response_model=Dict[str, Any])
async def search_knowledge(
    query: str = Query(..., description="Search query"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, description="Maximum number of results to return"),
    topic_cluster_id: Optional[str] = Query(None, description="Limit search to a specific topic cluster"),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Search the knowledge graph (public endpoint).
    
    Args:
        query: The search query.
        user_id: The user ID.
        limit: Maximum number of results to return.
        topic_cluster_id: Optional topic cluster ID filter.
        graph_manager: The graph manager.
        
    Returns:
        Search results.
    """
    try:
        # Check if vector search is enabled
        vector_search_enabled = hasattr(graph_manager, "vector_search") and graph_manager.vector_search
        
        if vector_search_enabled:
            # Perform vector search
            results = await graph_manager.search_nodes(
                user_id=user_id,
                query=query,
                limit=limit,
                topic_cluster_id=topic_cluster_id
            )
        else:
            # Fallback to simple text search
            nodes = await graph_manager.storage.find_documents(
                collection="nodes",
                query={
                    "user_id": user_id,
                    "$or": [
                        {"label": {"$regex": query, "$options": "i"}},
                        {"summary": {"$regex": query, "$options": "i"}}
                    ],
                    **({"topic_cluster_id": topic_cluster_id} if topic_cluster_id else {})
                },
                limit=limit
            )
            
            # Format search results
            results = []
            for node in nodes:
                results.append({
                    "id": str(node["_id"]),
                    "label": node.get("label", "Unnamed"),
                    "type": node.get("type", "unknown"),
                    "summary": node.get("summary"),
                    "score": 1.0,  # No actual score in simple search
                    "topic_cluster_id": node.get("topic_cluster_id")
                })
        
        return {
            "query": query,
            "results": results,
            "count": len(results),
            "search_type": "vector" if vector_search_enabled else "text"
        }
    except Exception as e:
        logger.error(f"Failed to search knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge: {str(e)}")
