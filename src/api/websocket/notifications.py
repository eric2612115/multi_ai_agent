"""WebSocket notifications for knowledge forest.

This module provides WebSocket endpoints for real-time notifications
from the knowledge forest.
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from datetime import datetime

from src.services.event_bus import EventBus
from src.common.auth import get_current_user, User, get_user_from_token

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ws/knowledge", tags=["knowledge-ws"])

# Store active WebSocket connections
class ConnectionManager:
    """Manager for WebSocket connections."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a WebSocket connection and store it.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
        """
        try:
            # Accept the connection with proper headers
            await websocket.accept()
            
            async with self.lock:
                if user_id not in self.active_connections:
                    self.active_connections[user_id] = []
                
                self.active_connections[user_id].append(websocket)
                
                # Initialize subscriptions
                if user_id not in self.user_subscriptions:
                    self.user_subscriptions[user_id] = {"all"}  # Subscribe to all by default
                
                logger.info(f"WebSocket connection established for user {user_id}")
                
                # Send a welcome message
                try:
                    await websocket.send_text("\n")
                    welcome_msg = {
                        "event_type": "connection_established",
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": "WebSocket connection established",
                        "status": "connected"
                    }
                    await websocket.send_text(json.dumps(welcome_msg))
                except Exception as e:
                    logger.error(f"Error sending welcome message: {str(e)}")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            raise
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
        """
        async with self.lock:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                
                # Remove the user if no more connections
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    
                    # Remove subscriptions
                    if user_id in self.user_subscriptions:
                        del self.user_subscriptions[user_id]
            
            logger.info(f"WebSocket connection closed for user {user_id}")
    
    async def subscribe(self, user_id: str, event_type: str):
        """Subscribe a user to an event type.
        
        Args:
            user_id: The user ID.
            event_type: The event type to subscribe to.
        """
        async with self.lock:
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            
            self.user_subscriptions[user_id].add(event_type)
            logger.info(f"User {user_id} subscribed to event type {event_type}")
    
    async def unsubscribe(self, user_id: str, event_type: str):
        """Unsubscribe a user from an event type.
        
        Args:
            user_id: The user ID.
            event_type: The event type to unsubscribe from.
        """
        async with self.lock:
            if user_id in self.user_subscriptions:
                if event_type in self.user_subscriptions[user_id]:
                    self.user_subscriptions[user_id].remove(event_type)
                    logger.info(f"User {user_id} unsubscribed from event type {event_type}")
    
    async def is_subscribed(self, user_id: str, event_type: str) -> bool:
        """Check if a user is subscribed to an event type.
        
        Args:
            user_id: The user ID.
            event_type: The event type.
            
        Returns:
            True if subscribed, False otherwise.
        """
        if user_id not in self.user_subscriptions:
            return False
            
        return event_type in self.user_subscriptions[user_id] or "all" in self.user_subscriptions[user_id]
    
    async def broadcast(self, event_type: str, data: Dict[str, Any], user_id: Optional[str] = None):
        """Broadcast a message to subscribed users.
        
        Args:
            event_type: The event type.
            data: The data to broadcast.
            user_id: Optional user ID to target a specific user.
        """
        message = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        json_message = json.dumps(message)
        
        if user_id:
            # Send to a specific user if they're subscribed
            if user_id in self.active_connections and await self.is_subscribed(user_id, event_type):
                for connection in self.active_connections[user_id]:
                    try:
                        await connection.send_text(json_message)
                    except Exception as e:
                        logger.error(f"Error sending message to user {user_id}: {str(e)}")
        else:
            # Broadcast to all subscribed users
            for uid, connections in self.active_connections.items():
                if await self.is_subscribed(uid, event_type):
                    for connection in connections:
                        try:
                            await connection.send_text(json_message)
                        except Exception as e:
                            logger.error(f"Error broadcasting message to user {uid}: {str(e)}")

# Create a singleton instance
manager = ConnectionManager()

# Event handler for broadcasting events
async def handle_knowledge_event(event_data: Dict[str, Any]):
    """Handle knowledge events from the event bus.
    
    Args:
        event_data: The event data.
    """
    # Extract the event type from the event bus event name
    # This assumes the event bus publishes with names like "knowledge.extraction_complete"
    event_type = "knowledge_event"  # Default event type
    
    # Extract user ID if present
    user_id = event_data.get("user_id")
    
    # Broadcast the event to subscribed users
    await manager.broadcast(event_type, event_data, user_id)

async def handle_visualization_event(event_data: Dict[str, Any]):
    """Handle 3D visualization events from the event bus.
    
    Args:
        event_data: The event data.
    """
    # Extract the event type from the event bus event name
    # This assumes the event bus publishes with names like "visualization.layout_changed"
    event_name = event_data.get("event_name", "")
    if "layout" in event_name:
        event_type = "layout_update"
    elif "focus" in event_name:
        event_type = "camera_focus"
    elif "nodes" in event_name:
        event_type = "visualization_update"
    else:
        event_type = "visualization_event"  # Default
    
    # Extract user ID if present
    user_id = event_data.get("user_id")
    
    # Broadcast the event to subscribed users
    await manager.broadcast(event_type, event_data, user_id)

# Setup event bus subscription
async def setup_event_subscriptions():
    """Setup event bus subscriptions."""
    event_bus = EventBus()
    
    # Subscribe to knowledge events
    event_bus.subscribe("knowledge.extraction_complete", handle_knowledge_event)
    event_bus.subscribe("knowledge.placement_decided", handle_knowledge_event)
    event_bus.subscribe("knowledge.graph_updated", handle_knowledge_event)
    event_bus.subscribe("knowledge.cross_links_detected", handle_knowledge_event)
    event_bus.subscribe("knowledge.nodes_merged", handle_knowledge_event)
    event_bus.subscribe("knowledge.node_split", handle_knowledge_event)
    event_bus.subscribe("knowledge.node_deleted", handle_knowledge_event)
    event_bus.subscribe("knowledge.node_updated", handle_knowledge_event)
    
    # Subscribe to 3D visualization events
    event_bus.subscribe("visualization.layout_changed", handle_visualization_event)
    event_bus.subscribe("visualization.focus_node", handle_visualization_event)
    event_bus.subscribe("visualization.nodes_added", handle_visualization_event)
    event_bus.subscribe("visualization.nodes_updated", handle_visualization_event)
    event_bus.subscribe("visualization.nodes_removed", handle_visualization_event)
    
    logger.info("Subscribed to knowledge and visualization events")

# WebSocket endpoints
@router.websocket("/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for knowledge notifications.
    
    Args:
        websocket: The WebSocket connection.
    """
    # For tracking keepalive
    last_activity = datetime.utcnow()
    disconnect_task = None
    user_id = None
    
    # Get user_id and token from query parameters
    user_id = websocket.query_params.get("user_id")
    token = websocket.query_params.get("token")
    
    if not user_id:
        await websocket.close(code=1008, reason="Missing user_id parameter")
        return
        
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    
    # Use simple token check for demo - in production we'd validate properly
    if token != "demo_token":
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # Define the keepalive function
    async def keepalive_check():
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                if (datetime.utcnow() - last_activity).total_seconds() > 60:  # Disconnect after 60 seconds of inactivity
                    logger.warning(f"Disconnecting inactive WebSocket for user {user_id}")
                    try:
                        await websocket.close(code=1000, reason="Inactivity timeout")
                    except Exception as e:
                        logger.error(f"Error closing inactive WebSocket: {str(e)}")
                    return
        except asyncio.CancelledError:
            # Task was cancelled, ignore
            pass
        except Exception as e:
            logger.error(f"Error in keepalive check: {str(e)}")
    
    try:
        # Initialize user if needed
        from src.common.initialization import initialize_new_user
        await initialize_new_user(user_id)
        
        # Connect the WebSocket
        await manager.connect(websocket, user_id)
        
        # Start the keepalive check
        disconnect_task = asyncio.create_task(keepalive_check())
        
        # Keep track of last activity
        last_activity = datetime.utcnow()
        
        try:
            while True:
                # Wait for messages from the client with a timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                    last_activity = datetime.utcnow()  # Update last activity timestamp
                except asyncio.TimeoutError:
                    # Send a ping to keep the connection alive
                    try:
                        ping_msg = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                        await websocket.send_text(json.dumps(ping_msg))
                        last_activity = datetime.utcnow()  # Update last activity timestamp
                        continue
                    except Exception as e:
                        logger.error(f"Error sending ping: {str(e)}")
                        break
                
                try:
                    message = json.loads(data)
                    
                    # Handle subscription requests
                    if message.get("action") == "subscribe" and "event_type" in message:
                        await manager.subscribe(user_id, message["event_type"])
                        await websocket.send_text(json.dumps({
                            "status": "success",
                            "message": f"Subscribed to {message['event_type']}",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                    # Handle unsubscription requests
                    elif message.get("action") == "unsubscribe" and "event_type" in message:
                        await manager.unsubscribe(user_id, message["event_type"])
                        await websocket.send_text(json.dumps({
                            "status": "success",
                            "message": f"Unsubscribed from {message['event_type']}",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                    # Handle ping messages
                    elif message.get("action") == "ping":
                        await websocket.send_text(json.dumps({
                            "status": "success",
                            "message": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                    # Unknown action
                    else:
                        await websocket.send_text(json.dumps({
                            "status": "error",
                            "message": "Unknown action",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "status": "error",
                        "message": "Invalid JSON",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
        
        except WebSocketDisconnect as e:
            # Disconnect on client disconnect
            logger.info(f"WebSocket disconnected for user {user_id} with code {e.code}")
        except Exception as e:
            logger.error(f"Error in WebSocket communication: {str(e)}")
        finally:
            # Clean up
            if disconnect_task:
                disconnect_task.cancel()
            await manager.disconnect(websocket, user_id)
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception as close_err:
            logger.error(f"Error closing WebSocket after exception: {str(close_err)}")
        finally:
            if disconnect_task:
                disconnect_task.cancel()
            if user_id:
                await manager.disconnect(websocket, user_id)

# Startup event to setup event subscriptions
async def startup():
    """Setup event subscriptions on startup."""
    await setup_event_subscriptions()

# Make sure to call this during application startup
# app.add_event_handler("startup", startup)

# Convenience functions for sending specific notifications
async def broadcast_to_user(user_id: str, message: Dict[str, Any]):
    """Send a message to a specific user.
    
    Args:
        user_id: The user ID.
        message: The message to send.
    """
    event_type = message.get("type", "knowledge_event")
    await manager.broadcast(event_type, message, user_id)

async def broadcast_graph_update(user_id: str, update_info: Dict[str, Any]):
    """Broadcast a graph update notification.
    
    Args:
        user_id: The user ID.
        update_info: The update information.
    """
    update_message = {
        "type": "graph_update",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "nodes_created": update_info.get("nodes_created", []),
            "nodes_updated": update_info.get("nodes_updated", []),
            "edges_created": update_info.get("edges_created", [])
        }
    }
    await broadcast_to_user(user_id, update_message)

async def broadcast_processing_status(user_id: str, status: str, 
                                   details: Optional[Dict[str, Any]] = None,
                                   message_id: Optional[str] = None):
    """Broadcast a processing status notification.
    
    Args:
        user_id: The user ID.
        status: The processing status.
        details: Optional details.
        message_id: Optional message ID related to the processing.
    """
    status_message = {
        "type": "processing_status",
        "status": status,  # "extracting", "analyzing", "placing", "complete", "error"
        "timestamp": datetime.utcnow().isoformat(),
        "message_id": message_id,
        "details": details or {}
    }
    await broadcast_to_user(user_id, status_message)

async def broadcast_node_focus(user_id: str, node_id: str, detail_level: str = "full"):
    """Broadcast a node focus notification.
    
    Args:
        user_id: The user ID.
        node_id: The ID of the node to focus on.
        detail_level: The level of detail to include.
    """
    # This can be used to tell the frontend to focus on a specific node
    focus_message = {
        "type": "node_focus",
        "timestamp": datetime.utcnow().isoformat(),
        "node_id": node_id,
        "detail_level": detail_level
    }
    await broadcast_to_user(user_id, focus_message)

async def broadcast_search_result(user_id: str, query: str, results: List[Dict[str, Any]]):
    """Broadcast search results.
    
    Args:
        user_id: The user ID.
        query: The search query.
        results: The search results.
    """
    search_message = {
        "type": "search_result",
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "results": results
    }
    await broadcast_to_user(user_id, search_message)

async def broadcast_ai_thinking(user_id: str, message_id: str, thinking_update: str, 
                              progress: Optional[float] = None):
    """Broadcast AI thinking updates for streaming UI feedback.
    
    Args:
        user_id: The user ID.
        message_id: The message ID.
        thinking_update: The thinking update text.
        progress: Optional progress value (0.0 to 1.0).
    """
    thinking_message = {
        "type": "ai_thinking",
        "timestamp": datetime.utcnow().isoformat(),
        "message_id": message_id,
        "thinking_update": thinking_update,
        "progress": progress
    }
    await broadcast_to_user(user_id, thinking_message)

async def broadcast_visualization_update(user_id: str, nodes: List[Dict[str, Any]], 
                                       edges: List[Dict[str, Any]], update_type: str = "add"):
    """Broadcast visualization updates for 3D graph.
    
    Args:
        user_id: The user ID.
        nodes: List of nodes to update.
        edges: List of edges to update.
        update_type: Type of update (add, update, remove).
    """
    viz_message = {
        "type": "visualization_update",
        "timestamp": datetime.utcnow().isoformat(),
        "update_type": update_type,
        "nodes": nodes,
        "edges": edges
    }
    await broadcast_to_user(user_id, viz_message)

async def broadcast_camera_focus(user_id: str, position: Dict[str, float], 
                               target: Dict[str, float], 
                               animation_duration: float = 1.0):
    """Broadcast camera focus position for 3D visualization.
    
    Args:
        user_id: The user ID.
        position: Camera position {x, y, z}.
        target: Look-at target position {x, y, z}.
        animation_duration: Duration of camera movement animation in seconds.
    """
    camera_message = {
        "type": "camera_focus",
        "timestamp": datetime.utcnow().isoformat(),
        "position": position,
        "target": target,
        "animation_duration": animation_duration
    }
    await broadcast_to_user(user_id, camera_message)

async def broadcast_layout_update(user_id: str, layout_name: str, 
                                node_positions: Dict[str, Dict[str, float]]):
    """Broadcast graph layout update for 3D visualization.
    
    Args:
        user_id: The user ID.
        layout_name: Name of the layout.
        node_positions: Dictionary mapping node IDs to positions {x, y, z}.
    """
    layout_message = {
        "type": "layout_update",
        "timestamp": datetime.utcnow().isoformat(),
        "layout_name": layout_name,
        "node_positions": node_positions
    }
    await broadcast_to_user(user_id, layout_message)
