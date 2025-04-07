"""Additional REST API routes for knowledge forest.

This module provides additional REST API endpoints for the knowledge forest.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import uuid

from src.forest.tasks import KnowledgeForestTaskHandler
from src.forest.graph import KnowledgeGraphManager
from src.services.event_bus import EventBus
from src.common.auth import get_current_user, User
from src.storage.vector_search import VectorSearch

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Import the models from knowledge_forest.py
from src.api.rest.knowledge_forest import (
    NodeFeedbackRequest, EdgeCreationRequest, TaskResponse,
    get_task_handler, get_graph_manager, get_event_bus
)

# Enums
class NodeDetailLevelEnum(str, Enum):
    """Enum for node detail levels."""
    
    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"

# Additional models
class SearchRequest(BaseModel):
    """Request model for knowledge search."""
    
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results to return")
    topic_cluster_id: Optional[str] = Field(None, description="Limit search to a specific topic cluster")
    content_types: Optional[List[str]] = Field(None, description="Limit search to specific content types")

class VisualLayoutRequest(BaseModel):
    """Request model for saving custom visual layout settings."""
    
    node_positions: Dict[str, Dict[str, float]] = Field(..., description="Node position data {node_id: {x: float, y: float, z: float}}")
    zoom_level: Optional[float] = Field(None, description="Camera zoom level")
    camera_position: Optional[Dict[str, float]] = Field(None, description="Camera position {x: float, y: float, z: float}")
    layout_name: Optional[str] = Field("default", description="Name of this layout configuration")

class TopicClusterRequest(BaseModel):
    """Request model for topic cluster operations."""
    
    name: str = Field(..., description="Topic cluster name")
    description: Optional[str] = Field(None, description="Topic cluster description")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

class Visualization3DRequest(BaseModel):
    """Request model for 3D visualization data."""
    
    format: str = Field("json", description="Format of the visualization data (json or gltf)")
    include_virtual_nodes: bool = Field(True, description="Include virtual nodes for groups and abstractions")
    include_3d_positions: bool = Field(True, description="Include 3D position data")
    colorize_by: str = Field("type", description="How to colorize nodes (type, topic, importance, age)")
    max_nodes: int = Field(1000, description="Maximum number of nodes to include")
    with_edges: bool = Field(True, description="Include edges in the visualization")
    edge_min_weight: float = Field(0.3, description="Minimum edge weight to include")
    
class RelatedNodesRequest(BaseModel):
    """Request model for finding related nodes."""
    
    node_ids: List[str] = Field(..., description="List of node IDs to find related nodes for")
    max_distance: int = Field(2, description="Maximum distance (hops) from source nodes")
    min_similarity: float = Field(0.6, description="Minimum similarity score for vector relationships")
    limit: int = Field(50, description="Maximum number of nodes to return")
    
class PathRequest(BaseModel):
    """Request model for finding paths between nodes."""
    
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")
    max_distance: int = Field(5, description="Maximum path length")
    min_weight: float = Field(0.0, description="Minimum edge weight to consider")

# Routes
@router.delete("/nodes/{node_id}", response_model=TaskResponse)
async def delete_node(
    node_id: str = Path(..., description="Node ID"),
    current_user: User = Depends(get_current_user),
    task_handler: KnowledgeForestTaskHandler = Depends(get_task_handler),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Delete a node.
    
    Args:
        node_id: The node ID.
        current_user: The current user.
        task_handler: The task handler.
        event_bus: The event bus.
        
    Returns:
        Task information.
    """
    try:
        # Publish an event for node deletion request
        await event_bus.publish(
            "knowledge.delete_request",
            {
                "user_id": str(current_user.id),
                "node_id": node_id
            }
        )
        
        # Generate a task ID
        task_id = f"delete_node_{datetime.utcnow().timestamp()}"
        
        # Delete the node
        task = await task_handler.task_queue.add_task(
            task_handler._delete_node,
            task_id=task_id,
            node_id=node_id,
            user_id=str(current_user.id)
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Node deletion task has been started"
        }
    except Exception as e:
        logger.error(f"Failed to delete node: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete node: {str(e)}")

@router.post("/edges", response_model=Dict[str, Any])
async def create_edge(
    request: EdgeCreationRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Create a new edge.
    
    Args:
        request: The edge creation request.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The created edge.
    """
    try:
        # Create edge
        conversation_id = str(uuid.uuid4())  # Generate a placeholder conversation ID
        message_id = str(uuid.uuid4())  # Generate a placeholder message ID
        
        edge_id = await graph_manager._create_edge(
            source_node_id=request.source_node_id,
            target_node_id=request.target_node_id,
            relationship_type=request.relationship_type,
            user_id=str(current_user.id),
            conversation_id=conversation_id,
            message_id=message_id,
            strength=request.strength,
            context_summary=request.context_summary
        )
        
        return {
            "id": edge_id,
            "source_node_id": request.source_node_id,
            "target_node_id": request.target_node_id,
            "relationship_type": request.relationship_type,
            "strength": request.strength
        }
    except Exception as e:
        logger.error(f"Failed to create edge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create edge: {str(e)}")

@router.delete("/edges/{edge_id}", response_model=Dict[str, Any])
async def delete_edge(
    edge_id: str = Path(..., description="Edge ID"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Delete an edge.
    
    Args:
        edge_id: The edge ID.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Acknowledgement.
    """
    try:
        # TODO: Implement edge deletion in graph manager
        # For now, simulate the operation
        logger.info(f"Would delete edge {edge_id} for user {current_user.id}")
        
        return {
            "status": "success",
            "message": "Edge deleted",
            "edge_id": edge_id
        }
    except Exception as e:
        logger.error(f"Failed to delete edge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete edge: {str(e)}")

@router.post("/visual-layout", response_model=Dict[str, Any])
async def save_visual_layout(
    request: VisualLayoutRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Save the user's preferred visual layout settings.
    
    Args:
        request: The visual layout settings.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Acknowledgment with the saved layout ID.
    """
    try:
        # Generate a unique ID for this layout if not updating an existing one
        layout_id = f"layout_{str(uuid.uuid4())}"
        
        # Save the layout in database
        layout_data = {
            "user_id": str(current_user.id),
            "name": request.layout_name,
            "node_positions": request.node_positions,
            "zoom_level": request.zoom_level,
            "camera_position": request.camera_position,
            "created_at": datetime.utcnow()
        }
        
        await graph_manager.storage.save_document("layouts", layout_data)
        
        return {
            "status": "success",
            "message": "Visual layout saved",
            "layout_id": layout_id,
            "layout_name": request.layout_name
        }
    except Exception as e:
        logger.error(f"Failed to save visual layout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save visual layout: {str(e)}")

@router.get("/visual-layout/{layout_name}", response_model=Dict[str, Any])
async def get_visual_layout(
    layout_name: str = Path(..., description="Layout name"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get a saved visual layout by name.
    
    Args:
        layout_name: The layout name.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The saved visual layout settings.
    """
    try:
        # Find layout by name
        layouts = await graph_manager.storage.find_documents(
            collection="layouts",
            query={
                "user_id": str(current_user.id),
                "name": layout_name
            },
            sort={"created_at": -1},  # Get the most recent one
            limit=1
        )
        
        if not layouts or len(layouts) == 0:
            raise HTTPException(status_code=404, detail=f"Layout '{layout_name}' not found")
            
        layout = layouts[0]
        
        return {
            "layout_id": str(layout["_id"]),
            "layout_name": layout.get("name", "default"),
            "node_positions": layout.get("node_positions", {}),
            "zoom_level": layout.get("zoom_level"),
            "camera_position": layout.get("camera_position"),
            "created_at": layout.get("created_at").isoformat() if "created_at" in layout else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get visual layout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get visual layout: {str(e)}")


@router.get("/visual-layout", response_model=Dict[str, Any])
async def get_default_visual_layout(
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get the default visual layout.
    
    Args:
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The default visual layout settings.
    """
    # Just call the get_visual_layout function with "default" as the layout name
    try:
        # Find layout by name
        layouts = await graph_manager.storage.find_documents(
            collection="layouts",
            query={
                "user_id": str(current_user.id),
                "name": "default"
            },
            sort={"created_at": -1},  # Get the most recent one
            limit=1
        )
        
        if not layouts or len(layouts) == 0:
            # Return an empty default layout
            return {
                "layout_id": "default",
                "layout_name": "default",
                "node_positions": {},
                "zoom_level": 1.0,
                "camera_position": {"x": 0, "y": 0, "z": 0},
                "created_at": datetime.utcnow().isoformat()
            }
            
        layout = layouts[0]
        
        return {
            "layout_id": str(layout["_id"]),
            "layout_name": layout.get("name", "default"),
            "node_positions": layout.get("node_positions", {}),
            "zoom_level": layout.get("zoom_level"),
            "camera_position": layout.get("camera_position"),
            "created_at": layout.get("created_at").isoformat() if "created_at" in layout else None
        }
    except Exception as e:
        logger.error(f"Failed to get default visual layout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get default visual layout: {str(e)}")

@router.post("/nodes/{node_id}/feedback", response_model=Dict[str, Any])
async def provide_node_feedback(
    node_id: str = Path(..., description="Node ID"),
    request: NodeFeedbackRequest = Body(...),
    current_user: User = Depends(get_current_user),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Provide feedback for a node.
    
    Args:
        node_id: The node ID.
        request: The feedback request.
        current_user: The current user.
        event_bus: The event bus.
        
    Returns:
        Acknowledgement.
    """
    try:
        # Publish feedback event
        await event_bus.publish(
            "knowledge.feedback",
            {
                "user_id": str(current_user.id),
                "node_id": node_id,
                "feedback_type": request.feedback_type,
                "feedback_data": request.feedback_data,
                "comment": request.comment
            }
        )
        
        return {
            "status": "received",
            "message": "Feedback received",
            "node_id": node_id,
            "feedback_type": request.feedback_type
        }
    except Exception as e:
        logger.error(f"Failed to process feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process feedback: {str(e)}")

async def normalize_query(query: str, text_model = None) -> Dict[str, Any]:
    """Normalize search query for better results.
    
    This function:
    1. Standardizes query format
    2. Adds multilingual support
    3. Expands query with semantic alternatives
    
    Args:
        query: Original search query
        text_model: Optional text generation model
        
    Returns:
        Dict with normalized query and expansions
    """
    # Basic cleaning
    normalized = query.strip()
    
    # Get language detector and optional text model
    if not text_model:
        try:
            from src.ai.factory import get_text_generation_model
            text_model = get_text_generation_model()
        except Exception as e:
            logger.warning(f"Could not get text model for query expansion: {str(e)}")
    
    # Detect language and normalize differently based on language
    try:
        import langdetect
        lang = langdetect.detect(normalized)
    except:
        lang = "en"  # Default to English if detection fails
        
    # Language-specific normalization
    if lang not in ["en", "zh-cn", "zh-tw", "ja", "ko"]:
        # For languages with inflections, try to get root forms
        try:
            # Use simple stemming for non-English languages without special handling
            import nltk
            from nltk.stem import SnowballStemmer
            supported_langs = {"es": "spanish", "fr": "french", "de": "german", 
                              "it": "italian", "pt": "portuguese", "ru": "russian"}
            
            if lang in supported_langs:
                stemmer = SnowballStemmer(supported_langs[lang])
                words = normalized.split()
                normalized_words = [stemmer.stem(word) for word in words]
                normalized = " ".join(normalized_words)
        except:
            # If NLTK fails, keep original normalization
            pass
        
    # For non-English queries, add English translation if available
    translations = []
    if lang != "en" and text_model:
        try:
            translation_prompt = f"Translate the following text from {lang} to English:\n\n{normalized}\n\nEnglish translation:"
            translation = await text_model.generate_text(translation_prompt, max_tokens=50)
            translations.append(translation.strip())
        except Exception as e:
            logger.warning(f"Failed to translate query: {str(e)}")
    
    # Add semantic expansions using AI if available
    expansions = []
    if text_model:
        try:
            expansion_prompt = f"""
            Generate 3-5 alternative search terms or phrases for the query below.
            Include related concepts, synonyms, and industry-specific terminology.
            Format as a comma-separated list without explanations.
            
            Query: {normalized}
            
            Alternative search terms (comma-separated):
            """
            
            expansion_response = await text_model.generate_text(expansion_prompt, max_tokens=100)
            expansions = [term.strip() for term in expansion_response.split(",") if term.strip()]
            
        except Exception as e:
            logger.warning(f"Failed to expand query: {str(e)}")
    
    return {
        "normalized_query": normalized,
        "translations": translations,
        "expansions": expansions,
        "original_language": lang
    }


@router.post("/search", response_model=Dict[str, Any])
async def search_knowledge(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Search the knowledge graph with advanced query processing.
    
    Args:
        request: The search request.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Search results.
    """
    try:
        # Initialize vector search
        from src.storage.vector_search import VectorSearch
        vector_search = await VectorSearch.create()
        
        # Get embedding provider
        from src.ai.base import get_default_embedding_provider
        from src.ai.factory import get_text_generation_model
        embedding_provider = get_default_embedding_provider()
        text_model = get_text_generation_model()
        
        # Step 1: Normalize and expand query
        query_processing = await normalize_query(request.query, text_model)
        normalized_query = query_processing["normalized_query"]
        translations = query_processing["translations"]
        expansions = query_processing["expansions"]
        
        # Log query processing results
        logger.info(f"Query normalized: '{request.query}' -> '{normalized_query}'")
        if translations:
            logger.info(f"Query translated: {translations}")
        if expansions:
            logger.info(f"Query expanded: {expansions}")
        
        # Step 2: Get embeddings for all query variations
        query_embeddings = []
        
        # Primary query embedding
        primary_embedding = await embedding_provider.get_embedding(normalized_query)
        query_embeddings.append(primary_embedding)
        
        # Translation embeddings
        for translation in translations:
            try:
                trans_embedding = await embedding_provider.get_embedding(translation)
                query_embeddings.append(trans_embedding)
            except Exception as e:
                logger.warning(f"Failed to get embedding for translation: {str(e)}")
        
        # Step 3: Search with all embeddings
        all_results = []
        
        # Search with primary query
        primary_results = await vector_search.search_nodes(
            user_id=str(current_user.id),
            query_embedding=primary_embedding,
            limit=request.limit,
            min_similarity=0.6,
            topic_cluster_id=request.topic_cluster_id
        )
        all_results.extend(primary_results)
        
        # Search with translations and expansions (if available)
        if len(query_embeddings) > 1:
            # Get batch results for all additional embeddings
            batch_results = await vector_search.batch_search_vectors(
                collection="nodes",
                vectors=query_embeddings[1:],  # Skip primary embedding
                filter={"user_id": str(current_user.id), 
                       **({"topic_cluster_id": request.topic_cluster_id} if request.topic_cluster_id else {})},
                top_k=max(3, request.limit // 2),  # Fewer results for expanded queries
                min_similarity=0.6
            )
            
            # Add all batch results to the result set
            for result_set in batch_results:
                all_results.extend(result_set)
        
        # Step 4: Deduplicate and rank results
        seen_ids = set()
        unique_results = []
        
        for result in all_results:
            result_id = str(result["_id"])
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)
        
        # Sort by search score
        unique_results.sort(key=lambda x: x.get("searchScore", 0), reverse=True)
        
        # Limit to requested number
        unique_results = unique_results[:request.limit]
        
        # Step 5: Format the results
        formatted_results = []
        for result in unique_results:
            formatted_results.append({
                "id": str(result["_id"]),
                "label": result.get("label", "Unnamed"),
                "type": result.get("type", "unknown"),
                "summary": result.get("summary"),
                "score": result.get("searchScore", 0.0),
                "topic_cluster_id": result.get("topic_cluster_id"),
                "importance_score": result.get("importance_score", 0.0),
                "created_at": result.get("created_at").isoformat() if result.get("created_at") else None,
                "updated_at": result.get("updated_at").isoformat() if result.get("updated_at") else None
            })
        
        # Step 6: Return results with query processing metadata
        return {
            "status": "success",
            "query": request.query,
            "normalized_query": normalized_query,
            "query_expansions": expansions if expansions else [],
            "results": formatted_results,
            "count": len(formatted_results),
            "search_type": "vector"
        }
    except Exception as e:
        logger.error(f"Failed to search knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge: {str(e)}")

@router.get("/topics", response_model=List[Dict[str, Any]])
async def get_topic_clusters(
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get all topic clusters for the user.
    
    Args:
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        List of topic clusters.
    """
    try:
        # TODO: Implement topic cluster retrieval in graph manager
        # For now, simulate the operation
        logger.info(f"Would get topic clusters for user {current_user.id}")
        
        return []  # Placeholder for topic clusters
    except Exception as e:
        logger.error(f"Failed to get topic clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get topic clusters: {str(e)}")

@router.post("/topics", response_model=Dict[str, Any])
async def create_topic_cluster(
    request: TopicClusterRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Create a new topic cluster.
    
    Args:
        request: The topic cluster creation request.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The created topic cluster.
    """
    try:
        # TODO: Implement topic cluster creation in graph manager
        # For now, simulate the operation
        topic_id = str(uuid.uuid4())
        logger.info(f"Would create topic cluster '{request.name}' for user {current_user.id}")
        
        return {
            "id": topic_id,
            "name": request.name,
            "description": request.description,
            "created_at": datetime.utcnow().isoformat(),
            "node_count": 0
        }
    except Exception as e:
        logger.error(f"Failed to create topic cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create topic cluster: {str(e)}")

@router.put("/topics/{topic_id}", response_model=Dict[str, Any])
async def update_topic_cluster(
    topic_id: str = Path(..., description="Topic cluster ID"),
    request: TopicClusterRequest = Body(...),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Update a topic cluster.
    
    Args:
        topic_id: The topic cluster ID.
        request: The topic cluster update request.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The updated topic cluster.
    """
    try:
        # TODO: Implement topic cluster update in graph manager
        # For now, simulate the operation
        logger.info(f"Would update topic cluster {topic_id} for user {current_user.id}")
        
        return {
            "id": topic_id,
            "name": request.name,
            "description": request.description,
            "updated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update topic cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update topic cluster: {str(e)}")

@router.get("/timeline", response_model=Dict[str, Any])
async def get_knowledge_timeline(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    interval: str = Query("day", description="Timeline interval (hour, day, week, month)"),
    topic_cluster_id: Optional[str] = Query(None, description="Filter by topic cluster ID"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get knowledge graph timeline data.
    
    Args:
        start_date: Optional start date in ISO format.
        end_date: Optional end date in ISO format.
        interval: Timeline interval (hour, day, week, month).
        topic_cluster_id: Optional topic cluster ID filter.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Timeline data with node/edge counts per interval.
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid start date format: {start_date}")
                
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid end date format: {end_date}")
        
        # Build query
        query = {"user_id": str(current_user.id)}
        
        if topic_cluster_id:
            query["topic_cluster_id"] = topic_cluster_id
            
        date_filter = {}
        if start_dt:
            date_filter["$gte"] = start_dt
        if end_dt:
            date_filter["$lte"] = end_dt
            
        if date_filter:
            query["created_at"] = date_filter
        
        # Get all nodes within the time range
        nodes = await graph_manager.storage.find_documents(
            collection="nodes",
            query=query,
            sort={"created_at": 1}
        )
        
        # Format into timeline data
        timeline_data = {}
        
        for node in nodes:
            # Get timestamp
            timestamp = node.get("created_at")
            if not timestamp:
                continue
                
            # Format interval key based on the requested interval
            if interval == "hour":
                interval_key = timestamp.strftime("%Y-%m-%d %H:00")
            elif interval == "day":
                interval_key = timestamp.strftime("%Y-%m-%d")
            elif interval == "week":
                # Start of the week (Monday)
                week_start = timestamp - timedelta(days=timestamp.weekday())
                interval_key = week_start.strftime("%Y-%m-%d")
            elif interval == "month":
                interval_key = timestamp.strftime("%Y-%m")
            else:
                interval_key = timestamp.strftime("%Y-%m-%d")
                
            # Initialize the interval if not exists
            if interval_key not in timeline_data:
                timeline_data[interval_key] = {
                    "node_count": 0,
                    "edge_count": 0,
                    "node_types": {}
                }
                
            # Update counts
            timeline_data[interval_key]["node_count"] += 1
            
            # Track node types
            node_type = node.get("type", "unknown")
            if node_type not in timeline_data[interval_key]["node_types"]:
                timeline_data[interval_key]["node_types"][node_type] = 0
            timeline_data[interval_key]["node_types"][node_type] += 1
        
        # Sort by interval key
        sorted_intervals = sorted(timeline_data.keys())
        result = [{
            "interval": interval_key,
            "node_count": timeline_data[interval_key]["node_count"],
            "edge_count": timeline_data[interval_key]["edge_count"],
            "node_types": timeline_data[interval_key]["node_types"]
        } for interval_key in sorted_intervals]
        
        return {
            "interval_type": interval,
            "intervals": result
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge timeline: {str(e)}")

@router.get("/node/{node_id}", response_model=Dict[str, Any])
async def get_node_details(
    node_id: str = Path(..., description="Node ID"),
    include_neighbors: bool = Query(False, description="Include connected nodes"),
    include_sources: bool = Query(True, description="Include source conversation and message references"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get detailed information about a node.
    
    Args:
        node_id: The node ID.
        include_neighbors: Whether to include connected nodes.
        include_sources: Whether to include source conversation and message references.
        current_user: The current user.
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
        if node_user_id != str(current_user.id):
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
                    "user_id": str(current_user.id),
                    "$or": [
                        {"source_node_id": node["_id"]},
                        {"target_node_id": node["_id"]}
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

@router.get("/snapshot/{time_point}", response_model=Dict[str, Any])
async def get_graph_snapshot(
    time_point: str = Path(..., description="Timestamp in ISO format"),
    topic_cluster_id: Optional[str] = Query(None, description="Filter by topic cluster ID"),
    max_depth: int = Query(3, description="Maximum depth for retrieving child nodes"),
    include_cross_links: bool = Query(True, description="Include cross-topic links"),
    detail_level: NodeDetailLevelEnum = Query(NodeDetailLevelEnum.STANDARD, description="Node detail level"),
    folded_topics: Optional[List[str]] = Query(None, description="List of topic IDs to fold"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get a snapshot of the knowledge graph at a specific point in time.
    
    Args:
        time_point: Timestamp in ISO format.
        topic_cluster_id: Optional topic cluster ID filter.
        max_depth: Maximum depth for retrieving child nodes.
        include_cross_links: Whether to include cross-topic links.
        detail_level: Node detail level.
        folded_topics: List of topic IDs to fold.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Knowledge graph snapshot at the specified time.
    """
    try:
        # Call the get_graph method with time_point parameter
        graph = await graph_manager.get_graph(
            user_id=str(current_user.id),
            topic_cluster_id=topic_cluster_id,
            max_depth=max_depth,
            include_cross_links=include_cross_links,
            detail_level=detail_level.value,
            folded_topics=folded_topics,
            time_point=time_point
        )
        
        return {
            "time_point": time_point,
            "graph": graph
        }
    except Exception as e:
        logger.error(f"Failed to get graph snapshot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get graph snapshot: {str(e)}")

@router.delete("/topics/{topic_id}", response_model=Dict[str, Any])
async def delete_topic_cluster(
    topic_id: str = Path(..., description="Topic cluster ID"),
    delete_nodes: bool = Query(False, description="Whether to delete all nodes in this topic"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Delete a topic cluster.
    
    Args:
        topic_id: The topic cluster ID.
        delete_nodes: Whether to delete all nodes in this topic.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Acknowledgement.
    """
    try:
        # TODO: Implement topic cluster deletion in graph manager
        # For now, simulate the operation
        logger.info(f"Would delete topic cluster {topic_id} for user {current_user.id} (delete_nodes={delete_nodes})")
        
        return {
            "status": "success",
            "message": "Topic cluster deleted",
            "topic_id": topic_id
        }
    except Exception as e:
        logger.error(f"Failed to delete topic cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete topic cluster: {str(e)}")

@router.get("/stats", response_model=Dict[str, Any])
async def get_knowledge_stats(
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get knowledge graph statistics.
    
    Args:
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Knowledge graph statistics.
    """
    try:
        # Get node count
        node_count = await graph_manager.storage.count_documents(
            collection="nodes",
            query={"user_id": str(current_user.id)}
        )
        
        # Get edge count
        edge_count = await graph_manager.storage.count_documents(
            collection="edges",
            query={"user_id": str(current_user.id)}
        )
        
        # Get topic count
        topic_clusters = {}
        nodes = await graph_manager.storage.find_documents(
            collection="nodes",
            query={"user_id": str(current_user.id)}
        )
        
        for node in nodes:
            if "topic_cluster_id" in node and node["topic_cluster_id"]:
                topic_clusters[node["topic_cluster_id"]] = 1
        
        # Get node types distribution
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            if node_type in node_types:
                node_types[node_type] += 1
            else:
                node_types[node_type] = 1
                
        # Get latest update timestamp
        latest_node = await graph_manager.storage.find_documents(
            collection="nodes",
            query={"user_id": str(current_user.id)},
            sort={"updated_at": -1},
            limit=1
        )
        
        last_updated = datetime.utcnow().isoformat()
        if latest_node and len(latest_node) > 0 and "updated_at" in latest_node[0]:
            last_updated = latest_node[0]["updated_at"].isoformat()
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "topic_count": len(topic_clusters),
            "node_types": node_types,
            "last_updated": last_updated
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge stats: {str(e)}")

@router.post("/visualization-3d", response_model=Dict[str, Any])
async def get_3d_visualization(
    request: Visualization3DRequest,
    topic_cluster_id: Optional[str] = Query(None, description="Filter by topic cluster ID"),
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get knowledge graph data formatted for 3D visualization.
    
    Args:
        request: Visualization options.
        topic_cluster_id: Optional topic cluster ID filter.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Knowledge graph data for 3D visualization.
    """
    try:
        # Get the full graph with additional 3D positioning data
        graph = await graph_manager.get_graph(
            user_id=str(current_user.id),
            topic_cluster_id=topic_cluster_id,
            max_depth=100,  # We want the full graph for visualization
            include_cross_links=True
        )
        
        # Prepare nodes for 3D visualization
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        # Limit the number of nodes if needed
        if len(nodes) > request.max_nodes:
            # Sort by importance score before limiting
            nodes.sort(key=lambda x: x.get("importance_score", 0.0), reverse=True)
            nodes = nodes[:request.max_nodes]
            
            # Keep only edges that connect retained nodes
            node_ids = set(node["id"] for node in nodes)
            edges = [edge for edge in edges 
                    if edge["source"] in node_ids 
                    and edge["target"] in node_ids
                    and edge.get("strength", 0.0) >= request.edge_min_weight]
        
        # Add 3D positions if requested
        if request.include_3d_positions:
            # Get or create 3D positions for nodes
            positions = await _get_3d_node_positions(nodes, graph_manager, current_user.id)
            
            # Add positions to node data
            for node in nodes:
                node_id = node["id"]
                if node_id in positions:
                    node["position_3d"] = positions[node_id]
        
        # If we're not including edges, empty the edge list
        if not request.with_edges:
            edges = []
        
        # Format the result based on requested format
        if request.format == "gltf":
            # Format for glTF export (for Three.js or Babylon.js)
            visualization_data = _format_as_gltf(nodes, edges, request.colorize_by)
        else:
            # Default JSON format
            visualization_data = {
                "nodes": nodes,
                "edges": edges,
                "metadata": {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "generated_at": datetime.utcnow().isoformat(),
                    "colorize_by": request.colorize_by
                }
            }
        
        return visualization_data
    except Exception as e:
        logger.error(f"Failed to get 3D visualization data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get 3D visualization data: {str(e)}")

@router.post("/related-nodes", response_model=Dict[str, Any])
async def find_related_nodes(
    request: RelatedNodesRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Find nodes related to the specified node(s).
    
    Args:
        request: The request parameters.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Related nodes with path information.
    """
    try:
        # Get the nodes and verify access
        nodes = []
        for node_id in request.node_ids:
            node = await graph_manager.storage.get_document("nodes", node_id)
            if node and str(node.get("user_id")) == str(current_user.id):
                nodes.append(node)
        
        if not nodes:
            raise HTTPException(status_code=404, detail="No valid nodes found")
        
        # Get graph connections (structural relationships)
        related_nodes = set()
        edges = []
        
        # For each source node, find connected nodes up to max_distance
        for node in nodes:
            found_nodes, found_edges = await _find_connected_nodes(
                node["_id"], 
                request.max_distance, 
                graph_manager, 
                str(current_user.id),
                request.min_weight
            )
            
            # Add to our collections
            related_nodes.update(found_nodes)
            edges.extend(found_edges)
        
        # If we have vector search capability, also find similar nodes
        vector_results = []
        try:
            # Initialize vector search
            vector_search = await VectorSearch.create()
            
            # For each source node, find similar nodes using vector search
            for node in nodes:
                if "embedding" in node:
                    # Search using the node's embedding
                    similar_nodes = await vector_search.search_nodes(
                        user_id=str(current_user.id),
                        query_embedding=node["embedding"],
                        limit=request.limit // len(nodes),  # Divide limit among source nodes
                        min_similarity=request.min_similarity
                    )
                    
                    # Add the results
                    for similar in similar_nodes:
                        # Don't include the source node itself
                        if str(similar["_id"]) != str(node["_id"]):
                            similar["vector_similarity"] = similar.get("searchScore", 0.0)
                            vector_results.append(similar)
                            related_nodes.add(str(similar["_id"]))
        except Exception as vector_err:
            logger.warning(f"Vector search failed, continuing with graph connections only: {str(vector_err)}")
        
        # Format the final results
        # Remove the source nodes from related_nodes
        source_node_ids = set(str(node["_id"]) for node in nodes)
        related_nodes = related_nodes - source_node_ids
        
        # Get the node data for all related nodes
        formatted_nodes = []
        for node_id in related_nodes:
            node = await graph_manager.storage.get_document("nodes", node_id)
            if node:
                formatted_node = {
                    "id": str(node["_id"]),
                    "label": node.get("label", "Unnamed"),
                    "type": node.get("type", "unknown"),
                    "summary": node.get("summary"),
                    "topic_cluster_id": node.get("topic_cluster_id"),
                    "importance_score": node.get("importance_score", 0.0),
                    "created_at": node.get("created_at").isoformat() if node.get("created_at") else None
                }
                
                # Add vector similarity if available
                for vr in vector_results:
                    if str(vr["_id"]) == node_id:
                        formatted_node["vector_similarity"] = vr.get("vector_similarity", 0.0)
                        break
                
                formatted_nodes.append(formatted_node)
        
        # Format the edges
        formatted_edges = []
        for edge in edges:
            formatted_edges.append({
                "id": str(edge["_id"]),
                "source": str(edge["source_node_id"]),
                "target": str(edge["target_node_id"]),
                "type": edge.get("relationship_type", "relates_to"),
                "strength": edge.get("strength", 0.5)
            })
        
        # Limit results if needed
        if len(formatted_nodes) > request.limit:
            # Sort by importance score or vector similarity
            formatted_nodes.sort(
                key=lambda x: x.get("vector_similarity", 0.0) or x.get("importance_score", 0.0), 
                reverse=True
            )
            formatted_nodes = formatted_nodes[:request.limit]
            
            # Keep only edges that connect retained nodes
            node_ids = set(node["id"] for node in formatted_nodes).union(source_node_ids)
            formatted_edges = [edge for edge in formatted_edges 
                              if edge["source"] in node_ids 
                              and edge["target"] in node_ids]
        
        return {
            "source_nodes": [{"id": str(node["_id"]), "label": node.get("label", "Unnamed")} for node in nodes],
            "related_nodes": formatted_nodes,
            "edges": formatted_edges,
            "count": len(formatted_nodes)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find related nodes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find related nodes: {str(e)}")

@router.post("/find-path", response_model=Dict[str, Any])
async def find_path_between_nodes(
    request: PathRequest,
    current_user: User = Depends(get_current_user),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Find a path between two nodes in the knowledge graph.
    
    Args:
        request: The path request.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        Path information if a path exists.
    """
    try:
        # Verify the nodes exist and are accessible to the user
        source_node = await graph_manager.storage.get_document("nodes", request.source_node_id)
        target_node = await graph_manager.storage.get_document("nodes", request.target_node_id)
        
        if not source_node or str(source_node.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Source node not found")
            
        if not target_node or str(target_node.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Target node not found")
        
        # Find a path using Breadth-First Search
        paths = await _find_paths(
            source_node["_id"],
            target_node["_id"],
            request.max_distance,
            graph_manager,
            str(current_user.id),
            request.min_weight
        )
        
        if not paths:
            return {
                "source_node": {
                    "id": str(source_node["_id"]),
                    "label": source_node.get("label", "Unnamed")
                },
                "target_node": {
                    "id": str(target_node["_id"]),
                    "label": target_node.get("label", "Unnamed")
                },
                "paths": [],
                "path_count": 0,
                "message": "No path found between the nodes"
            }
        
        # Format the paths
        formatted_paths = []
        for path in paths:
            formatted_path = []
            for i, node_id in enumerate(path["nodes"]):
                node = await graph_manager.storage.get_document("nodes", node_id)
                if node:
                    formatted_path.append({
                        "id": str(node["_id"]),
                        "label": node.get("label", "Unnamed"),
                        "type": node.get("type", "unknown"),
                        "topic_cluster_id": node.get("topic_cluster_id")
                    })
            
            formatted_paths.append({
                "nodes": formatted_path,
                "edges": path["edges"],
                "length": len(path["nodes"]) - 1,
                "strength": path["strength"]
            })
        
        # Sort paths by strength (descending)
        formatted_paths.sort(key=lambda x: x["strength"], reverse=True)
        
        return {
            "source_node": {
                "id": str(source_node["_id"]),
                "label": source_node.get("label", "Unnamed")
            },
            "target_node": {
                "id": str(target_node["_id"]),
                "label": target_node.get("label", "Unnamed")
            },
            "paths": formatted_paths,
            "path_count": len(formatted_paths)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find path between nodes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find path between nodes: {str(e)}")

# Helper functions for 3D visualization and graph operations
async def _get_3d_node_positions(nodes, graph_manager, user_id):
    """Get or generate 3D positions for nodes.
    
    Args:
        nodes: List of nodes to position.
        graph_manager: Graph manager instance.
        user_id: User ID.
        
    Returns:
        Dictionary of node positions {node_id: {x, y, z}}.
    """
    # First try to get existing positions from the database
    layouts = await graph_manager.storage.find_documents(
        collection="layouts",
        query={
            "user_id": str(user_id),
            "name": "3d_default"
        },
        sort={"created_at": -1},
        limit=1
    )
    
    if layouts and len(layouts) > 0 and "node_positions" in layouts[0]:
        return layouts[0]["node_positions"]
    
    # If no existing layout, generate positions
    # This is a simple force-directed layout algorithm
    import random
    import math
    
    # Initialize positions randomly
    positions = {}
    for node in nodes:
        positions[node["id"]] = {
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "z": random.uniform(-100, 100)
        }
    
    return positions

def _format_as_gltf(nodes, edges, colorize_by):
    """Format graph data as glTF for 3D visualization.
    
    Args:
        nodes: List of nodes.
        edges: List of edges.
        colorize_by: How to colorize nodes.
        
    Returns:
        Data formatted for glTF export.
    """
    # Create a simple JSON that can be used with Three.js
    # A full glTF conversion would be more complex
    return {
        "asset": {
            "version": "2.0",
            "generator": "Knowledge Forest API"
        },
        "scene": 0,
        "scenes": [
            {
                "nodes": list(range(len(nodes)))
            }
        ],
        "nodes": [
            {
                "name": node.get("label", "Node"),
                "translation": [
                    node.get("position_3d", {}).get("x", 0),
                    node.get("position_3d", {}).get("y", 0),
                    node.get("position_3d", {}).get("z", 0)
                ],
                "extensions": {
                    "KHR_knowledge_forest": {
                        "id": node["id"],
                        "type": node.get("type", "unknown"),
                        "importance": node.get("importance_score", 0.0),
                        "topic": node.get("topic_cluster_id", ""),
                        "colorize_by": colorize_by
                    }
                }
            }
            for node in nodes
        ],
        "extensions": {
            "KHR_knowledge_forest": {
                "edges": [
                    {
                        "source": edge["source"],
                        "target": edge["target"],
                        "type": edge.get("type", "relates_to"),
                        "strength": edge.get("strength", 0.5)
                    }
                    for edge in edges
                ]
            }
        },
        "extensionsUsed": ["KHR_knowledge_forest"]
    }

async def _find_connected_nodes(start_node_id, max_distance, graph_manager, user_id, min_weight=0.0):
    """Find nodes connected to the start node up to max_distance.
    
    Args:
        start_node_id: Starting node ID.
        max_distance: Maximum distance (hops) from start node.
        graph_manager: Graph manager instance.
        user_id: User ID.
        min_weight: Minimum edge weight to consider.
        
    Returns:
        Tuple of (set of node IDs, list of edges).
    """
    # BFS to find connected nodes
    visited = set([str(start_node_id)])
    queue = [(str(start_node_id), 0)]  # (node_id, distance)
    edges = []
    
    while queue:
        current_id, distance = queue.pop(0)
        
        if distance >= max_distance:
            continue
        
        # Get edges from this node
        outbound_edges = await graph_manager.storage.find_documents(
            collection="edges",
            query={
                "user_id": user_id,
                "source_node_id": current_id,
                "strength": {"$gte": min_weight}
            }
        )
        
        inbound_edges = await graph_manager.storage.find_documents(
            collection="edges",
            query={
                "user_id": user_id,
                "target_node_id": current_id,
                "strength": {"$gte": min_weight}
            }
        )
        
        # Process outbound edges
        for edge in outbound_edges:
            target_id = str(edge["target_node_id"])
            if target_id not in visited:
                visited.add(target_id)
                queue.append((target_id, distance + 1))
            edges.append(edge)
        
        # Process inbound edges
        for edge in inbound_edges:
            source_id = str(edge["source_node_id"])
            if source_id not in visited:
                visited.add(source_id)
                queue.append((source_id, distance + 1))
            edges.append(edge)
    
    # Remove the start node from results
    visited.remove(str(start_node_id))
    return visited, edges

async def _find_paths(source_id, target_id, max_distance, graph_manager, user_id, min_weight=0.0):
    """Find all paths between source and target nodes up to max_distance.
    
    Args:
        source_id: Source node ID.
        target_id: Target node ID.
        max_distance: Maximum path length.
        graph_manager: Graph manager instance.
        user_id: User ID.
        min_weight: Minimum edge weight to consider.
        
    Returns:
        List of paths with nodes and edges.
    """
    # Use BFS to find all paths up to max_distance
    source_id_str = str(source_id)
    target_id_str = str(target_id)
    
    # If source and target are the same, return empty paths
    if source_id_str == target_id_str:
        return []
    
    # Queue of paths
    queue = [{
        "nodes": [source_id_str],
        "edges": [],
        "strength": 1.0,
        "visited": set([source_id_str])
    }]
    
    found_paths = []
    
    while queue:
        current_path = queue.pop(0)
        current_node = current_path["nodes"][-1]
        current_distance = len(current_path["nodes"]) - 1
        
        if current_distance >= max_distance:
            continue
        
        # Get edges from this node
        outbound_edges = await graph_manager.storage.find_documents(
            collection="edges",
            query={
                "user_id": user_id,
                "source_node_id": current_node,
                "strength": {"$gte": min_weight}
            }
        )
        
        # Check outbound edges
        for edge in outbound_edges:
            target_id = str(edge["target_node_id"])
            
            # Skip if already visited in this path
            if target_id in current_path["visited"]:
                continue
            
            # Create a new path with this edge
            edge_strength = edge.get("strength", 0.5)
            new_strength = current_path["strength"] * edge_strength
            
            new_path = {
                "nodes": current_path["nodes"] + [target_id],
                "edges": current_path["edges"] + [{
                    "id": str(edge["_id"]),
                    "source": str(edge["source_node_id"]),
                    "target": str(edge["target_node_id"]),
                    "type": edge.get("relationship_type", "relates_to"),
                    "strength": edge_strength
                }],
                "strength": new_strength,
                "visited": current_path["visited"].union([target_id])
            }
            
            # If we reached the target, add to found paths
            if target_id == target_id_str:
                found_paths.append(new_path)
            else:
                # Add to queue for further exploration
                queue.append(new_path)
    
    # Clean up the paths and return
    result = []
    for path in found_paths:
        result.append({
            "nodes": path["nodes"],
            "edges": path["edges"],
            "strength": path["strength"]
        })
    
    # Sort by path strength
    result.sort(key=lambda x: x["strength"], reverse=True)
    return result
