"""REST API routes for knowledge forest.

This module provides REST API endpoints for the knowledge forest.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, Body
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from forest.tasks import KnowledgeForestTaskHandler
from forest.graph import KnowledgeGraphManager
from forest.extraction_service import KnowledgeExtractionService
from services.event_bus import EventBus
from common.auth import get_current_user, User

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Models for request and response
class NodeCreationRequest(BaseModel):
    """Request model for node creation."""
    
    label: str = Field(..., description="Node label")
    content: str = Field(..., description="Content to extract knowledge from")
    type: Optional[str] = Field(None, description="Node type (auto-detected if not provided)")
    parent_node_id: Optional[str] = Field(None, description="Parent node ID if this is a child node")
    relationship_type: Optional[str] = Field(None, description="Relationship type to parent")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")
    message_id: Optional[str] = Field(None, description="Associated message ID")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

class NodeUpdateRequest(BaseModel):
    """Request model for node update."""
    
    label: Optional[str] = Field(None, description="Updated node label")
    summary: Optional[str] = Field(None, description="Updated node summary")
    content: Optional[str] = Field(None, description="New content to extract knowledge from")
    visual_attributes: Optional[Dict[str, Any]] = Field(None, description="Visual attributes")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class EdgeCreationRequest(BaseModel):
    """Request model for edge creation."""
    
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Relationship type")
    strength: Optional[float] = Field(0.5, description="Relationship strength (0-1)")
    context_summary: Optional[str] = Field(None, description="Context summary")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

class NodeFeedbackRequest(BaseModel):
    """Request model for node feedback."""
    
    feedback_type: str = Field(..., description="Feedback type (correct, incorrect, merge, split, delete)")
    feedback_data: Optional[Dict[str, Any]] = Field({}, description="Additional feedback data")
    comment: Optional[str] = Field(None, description="User comment")

class KnowledgeExtractionRequest(BaseModel):
    """Request model for knowledge extraction."""
    
    content: str = Field(..., description="Content to extract knowledge from")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")
    message_id: Optional[str] = Field(None, description="Associated message ID")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

class TaskResponse(BaseModel):
    """Response model for asynchronous tasks."""
    
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")

# Dependencies
def get_task_handler():
    """Get the task handler."""
    return KnowledgeForestTaskHandler()

def get_graph_manager():
    """Get the graph manager."""
    return KnowledgeGraphManager()

def get_event_bus():
    """Get the event bus."""
    return EventBus()

# Routes
@router.post("/extract", response_model=TaskResponse)
async def extract_knowledge(
    request: KnowledgeExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    task_handler: KnowledgeForestTaskHandler = Depends(get_task_handler)
):
    """Extract knowledge from content.
    
    Args:
        request: The extraction request.
        background_tasks: Background tasks.
        current_user: The current user.
        task_handler: The task handler.
        
    Returns:
        Task information.
    """
    try:
        # Prepare message data
        message_data = {
            "content": request.content,
            "user_id": str(current_user.id),
            "conversation_id": request.conversation_id,
            "message_id": request.message_id,
            "metadata": request.metadata
        }
        
        # Process the message
        task_id = await task_handler.process_message(message_data)
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Knowledge extraction task has been started"
        }
    except Exception as e:
        logger.error(f"Failed to extract knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to extract knowledge: {str(e)}")

@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_task_status(
    task_id: str = Path(..., description="Task ID"),
    current_user: User = Depends(get_current_user),
    task_handler: KnowledgeForestTaskHandler = Depends(get_task_handler)
):
    """Get the status of a task.
    
    Args:
        task_id: The task ID.
        current_user: The current user.
        task_handler: The task handler.
        
    Returns:
        Task status information.
    """
    try:
        # Get the task status
        status = await task_handler.get_task_status(task_id)
        
        if status["status"] == "not_found":
            raise HTTPException(status_code=404, detail="Task not found")
            
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@router.get("/graph", response_model=Dict[str, Any])
async def get_knowledge_graph(
    user_id: str = Query(..., description="User ID"),
    topic_cluster_id: Optional[str] = Query(None, description="Topic cluster ID"),
    max_depth: int = Query(3, description="Maximum depth of nodes to include"),
    include_cross_links: bool = Query(True, description="Include cross-links between topics"),
    graph_manager: KnowledgeGraphManager = Depends(get_graph_manager)
):
    """Get a knowledge graph for visualization.
    
    Args:
        topic_cluster_id: Optional topic cluster ID.
        max_depth: Maximum depth of nodes to include.
        include_cross_links: Include cross-links between topics.
        current_user: The current user.
        graph_manager: The graph manager.
        
    Returns:
        The knowledge graph.
    """
    try:
        # Check if user has data, if not, initialize
        from common.initialization import initialize_new_user
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

@router.post("/nodes", response_model=TaskResponse)
async def create_node(
    request: NodeCreationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    task_handler: KnowledgeForestTaskHandler = Depends(get_task_handler),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Create a new node.
    
    Args:
        request: The node creation request.
        background_tasks: Background tasks.
        current_user: The current user.
        task_handler: The task handler.
        event_bus: The event bus.
        
    Returns:
        Task information.
    """
    try:
        # Generate IDs if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        message_id = request.message_id or str(uuid.uuid4())
        
        # Prepare message data
        message_data = {
            "content": request.content,
            "user_id": str(current_user.id),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "metadata": {
                **request.metadata,
                "label": request.label,
                "type": request.type,
                "parent_node_id": request.parent_node_id,
                "relationship_type": request.relationship_type
            }
        }
        
        # Publish an event for node creation request
        await event_bus.publish(
            "knowledge.create_node_request",
            {
                "user_id": str(current_user.id),
                "request": request.dict()
            }
        )
        
        # Process the message
        task_id = await task_handler.process_message(message_data)
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Node creation task has been started"
        }
    except Exception as e:
        logger.error(f"Failed to create node: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create node: {str(e)}")

@router.put("/nodes/{node_id}", response_model=TaskResponse)
async def update_node(
    node_id: str = Path(..., description="Node ID"),
    request: NodeUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user),
    task_handler: KnowledgeForestTaskHandler = Depends(get_task_handler),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Update a node.
    
    Args:
        node_id: The node ID.
        request: The node update request.
        current_user: The current user.
        task_handler: The task handler.
        event_bus: The event bus.
        
    Returns:
        Task information.
    """
    try:
        # Prepare update data
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        # Publish an event for node update request
        await event_bus.publish(
            "knowledge.update_request",
            {
                "user_id": str(current_user.id),
                "node_id": node_id,
                "update_data": update_data
            }
        )
        
        # Generate a task ID
        task_id = f"update_node_{datetime.utcnow().timestamp()}"
        
        # Update the node
        task = await task_handler.task_queue.add_task(
            task_handler._update_node,
            task_id=task_id,
            node_id=node_id,
            update_data=update_data,
            user_id=str(current_user.id)
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Node update task has been started"
        }
    except Exception as e:
        logger.error(f"Failed to update node: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update node: {str(e)}")
