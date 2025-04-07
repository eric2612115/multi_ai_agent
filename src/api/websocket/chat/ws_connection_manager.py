"""WebSocket connection manager for chat service.

This module provides connection management functionality for chat WebSockets,
supporting high availability, error resilience, and distributed deployment.
"""
import logging
import asyncio
import json
import time
import os
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from fastapi import WebSocket, status
from datetime import datetime, timedelta
import uuid
import traceback

from src.ai.chat_agent import ChatAgent
from src.services.message_broker import MessageBroker
from src.api.websocket.chat.ws_session_store import WebSocketSessionStore
from src.api.websocket.chat.ws_reconnect_handler import ReconnectHandler
from src.api.websocket.chat.ws_security import SecurityManager

# Setup logging
logger = logging.getLogger(__name__)

# Configuration - will be loaded from environment variables or defaults
MAX_CONNECTIONS_PER_USER = int(os.environ.get("MAX_CONNECTIONS_PER_USER", "10"))
CONNECTION_IDLE_TIMEOUT = int(os.environ.get("CONNECTION_IDLE_TIMEOUT", "300"))  # 5 minutes
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))  # 30 seconds
GLOBAL_CONNECTION_LIMIT = int(os.environ.get("GLOBAL_CONNECTION_LIMIT", "1000"))
DISTRIBUTED_MODE = os.environ.get("USE_DISTRIBUTED_MODE", "false").lower() in ("true", "1", "yes")

class ChatConnectionManager:
    """Manager for chat WebSocket connections.
    
    Provides comprehensive connection management with support for:
    - Connection tracking and cleanup
    - Rate limiting and security
    - Reconnection handling
    - Heartbeat monitoring
    - Error recovery
    - Distributed deployment via Redis message broker
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        # Core connection tracking
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_last_activity: Dict[WebSocket, datetime] = {}
        self.total_connections = 0
        
        # Tasks
        self.cleanup_task = None
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        # Agent management
        self.user_agents: Dict[str, ChatAgent] = {}
        
        # Session and security
        self.session_store = WebSocketSessionStore()
        self.security_manager = SecurityManager()
        self.reconnect_handler = ReconnectHandler()
        
        # Thread safety
        self.lock = asyncio.Lock()
        
        # Distributed support
        self.distributed_mode = DISTRIBUTED_MODE
        self.message_broker: Optional[MessageBroker] = None
        self.instance_id = f"ws_manager_{uuid.uuid4()}"
    
    async def initialize(self):
        """Initialize the connection manager and its components."""
        # Initialize session store
        await self.session_store.initialize()
        
        # Initialize security manager
        await self.security_manager.initialize()
        
        # Initialize reconnect handler
        await self.reconnect_handler.initialize()
        
        # Initialize message broker for distributed mode
        if self.distributed_mode:
            try:
                self.message_broker = MessageBroker()
                await self.message_broker.start()
                
                # Register handlers for distributed events
                await self._register_distributed_handlers()
                
                # Announce instance presence
                await self._announce_instance()
                
                logger.info(f"WebSocket manager initialized in distributed mode with instance ID: {self.instance_id}")
            except Exception as e:
                logger.error(f"Failed to initialize distributed mode: {str(e)}")
                self.distributed_mode = False
                logger.warning("Falling back to standalone mode")
        
        # Start the cleanup task
        self.start_cleanup_task()
        
        logger.info("WebSocket connection manager initialized")
    
    async def _register_distributed_handlers(self):
        """Register handlers for distributed events."""
        if not self.message_broker:
            return
            
        # Register for connection events
        await self.message_broker.subscribe("ws_connections", self._handle_connection_event)
        
        # Register for session events
        await self.message_broker.subscribe("ws_sessions", self._handle_session_event)
        
        # Register for message broadcast events
        await self.message_broker.subscribe("ws_broadcasts", self._handle_broadcast_event)
    
    async def _announce_instance(self):
        """Announce this instance's presence to the cluster."""
        if not self.message_broker:
            return
            
        # Publish instance online message
        await self.message_broker.publish("ws_instances", {
            "action": "instance_online",
            "instance_id": self.instance_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Start heartbeat task
        self.message_broker.start_heartbeat_task()
    
    async def _handle_connection_event(self, event: Dict[str, Any]):
        """Handle connection events from other instances."""
        if not event:
            return
            
        action = event.get("action")
        user_id = event.get("user_id")
        
        if not action or not user_id:
            return
            
        # Connection events handling
        if action == "user_connected":
            await self.reconnect_handler.handle_remote_connection(user_id, event)
        elif action == "user_disconnected":
            await self.reconnect_handler.handle_remote_disconnection(user_id, event)
    
    async def _handle_session_event(self, event: Dict[str, Any]):
        """Handle session events from other instances."""
        if not event:
            return
            
        action = event.get("action")
        
        # Session events handling
        if action == "session_update":
            await self.session_store.handle_remote_update(event)
        elif action == "session_invalidate":
            await self.session_store.handle_remote_invalidation(event)
    
    async def _handle_broadcast_event(self, event: Dict[str, Any]):
        """Handle broadcast events from other instances."""
        if not event:
            return
            
        action = event.get("action")
        
        # Broadcast events handling
        if action == "broadcast_message":
            message = event.get("message")
            exclude_user_id = event.get("exclude_user_id")
            
            if message:
                # Only handle for locally connected users
                local_users = set(self.active_connections.keys())
                for user_id in local_users:
                    if exclude_user_id and user_id == exclude_user_id:
                        continue
                    await self.send_message(user_id, message)
    
    async def connect(self, websocket: WebSocket, user_id: str, client_ip: Optional[str] = None) -> bool:
        """Accept a WebSocket connection and store it.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
            client_ip: Client IP address for security checks.
            
        Returns:
            True if connection accepted, False otherwise.
        """
        # Check global connection limit
        if self.total_connections >= GLOBAL_CONNECTION_LIMIT:
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER, reason="Server connection limit reached")
            logger.warning(f"Connection from {user_id} rejected: global limit reached")
            return False
        
        # Security checks
        if not await self.security_manager.allow_connection(user_id, client_ip, websocket):
            # Security manager has already closed the websocket with appropriate reason
            logger.warning(f"Connection from {user_id} rejected by security manager")
            return False
        
        # Check for reconnection in distributed mode
        if self.distributed_mode and self.message_broker:
            redirect_info = await self.reconnect_handler.check_redirect(user_id, self.instance_id)
            if redirect_info and redirect_info.get("should_redirect"):
                # Generate reconnect token
                reconnect_token = str(uuid.uuid4())
                await self.reconnect_handler.issue_reconnect_token(user_id, reconnect_token)
                
                # Inform client to redirect
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=f"REDIRECT:{reconnect_token}"
                )
                logger.info(f"User {user_id} redirected to another instance with token")
                return False
        
        try:
            # Accept the connection
            await websocket.accept()
            
            # Check per-user connection limit
            async with self.lock:
                max_conn = 20 if client_ip == "127.0.0.1" else MAX_CONNECTIONS_PER_USER
                
                if user_id in self.active_connections and len(self.active_connections[user_id]) >= max_conn:
                    await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER, 
                                        reason=f"Maximum of {max_conn} connections per user")
                    logger.warning(f"Connection from {user_id} rejected: per-user limit reached")
                    return False
                
                # Add connection
                if user_id not in self.active_connections:
                    self.active_connections[user_id] = []
                
                self.active_connections[user_id].append(websocket)
                self.total_connections += 1
                self.connection_last_activity[websocket] = datetime.now()
                
                # Create or update session
                can_recover = await self.reconnect_handler.can_recover_session(user_id)
                
                session_data = {
                    "last_activity": datetime.now(),
                    "client_ip": client_ip,
                    "can_recover": can_recover
                }
                
                await self.session_store.create_or_update_session(user_id, session_data)
                
                # Start heartbeat task
                conn_id = f"{user_id}_{id(websocket)}"
                heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket, user_id, conn_id))
                self.heartbeat_tasks[conn_id] = heartbeat_task
                
                # Announce connection in distributed mode
                if self.distributed_mode and self.message_broker:
                    await self.message_broker.publish("ws_connections", {
                        "action": "user_connected",
                        "user_id": user_id,
                        "instance_id": self.instance_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                logger.info(f"WebSocket connection established for user {user_id} (Total: {self.total_connections})")
                return True
                
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            logger.debug(traceback.format_exc())
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
            except:
                pass
            return False
    
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
                    self.total_connections -= 1
                    
                    # Clean up connection activity tracking
                    if websocket in self.connection_last_activity:
                        del self.connection_last_activity[websocket]
                
                # If this was the last connection for this user
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    
                    # Save session state for potential reconnection
                    await self.reconnect_handler.save_disconnect_state(user_id)
                    
                    # Update security tracking
                    await self.security_manager.track_disconnection(user_id)
                    
                    # If in distributed mode, announce disconnection
                    if self.distributed_mode and self.message_broker:
                        await self.message_broker.publish("ws_connections", {
                            "action": "user_disconnected",
                            "user_id": user_id,
                            "instance_id": self.instance_id,
                            "timestamp": datetime.utcnow().isoformat()
                        })
            
            logger.info(f"WebSocket connection closed for user {user_id} (Total: {self.total_connections})")
    
    async def send_message(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific user.
        
        Args:
            user_id: The user ID.
            message: The message to send.
            
        Returns:
            True if message was sent successfully, False otherwise.
        """
        if user_id not in self.active_connections:
            logger.warning(f"Attempted to send message to disconnected user: {user_id}")
            return False
            
        success = False
        failed_connections = []
        
        # Try each connection until one succeeds
        for websocket in self.active_connections[user_id]:
            try:
                # Send to client
                await websocket.send_json(message)
                
                # Update activity timestamp
                self.connection_last_activity[websocket] = datetime.now()
                await self.session_store.update_activity(user_id)
                
                success = True
                break  # Message sent successfully, no need to try other connections
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {e}")
                failed_connections.append(websocket)
        
        # Clean up failed connections
        if failed_connections:
            async with self.lock:
                for ws in failed_connections:
                    if user_id in self.active_connections and ws in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(ws)
                        self.total_connections -= 1
                        if ws in self.connection_last_activity:
                            del self.connection_last_activity[ws]
                
                # Remove user if no more connections
                if user_id in self.active_connections and not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        return success
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None):
        """Broadcast a message to all connected users.
        
        Args:
            message: The message to send.
            exclude_user_id: Optional user ID to exclude from the broadcast.
        """
        # In distributed mode, publish to message broker
        if self.distributed_mode and self.message_broker:
            await self.message_broker.publish("ws_broadcasts", {
                "action": "broadcast_message",
                "message": message,
                "exclude_user_id": exclude_user_id,
                "instance_id": self.instance_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            return
        
        # In standalone mode, or for local-only broadcast
        for user_id, connections in self.active_connections.items():
            if exclude_user_id and user_id == exclude_user_id:
                continue
                
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                    # Update activity timestamp
                    self.connection_last_activity[websocket] = datetime.now()
                except Exception as e:
                    logger.error(f"Error broadcasting message to {user_id}: {e}")
                    # Connection will be cleaned up in the next cleanup cycle
    
    def update_activity(self, websocket: WebSocket, user_id: str):
        """Update the last activity timestamp for a connection.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
        """
        self.connection_last_activity[websocket] = datetime.now()
        asyncio.create_task(self.session_store.update_activity(user_id))
    
    def set_agent_busy(self, user_id: str, busy: bool):
        """Set whether a user's agent is busy.
        
        Args:
            user_id: The user ID.
            busy: Whether the agent is busy.
        """
        asyncio.create_task(self.session_store.update_session(user_id, {"agent_busy": busy}))
        logger.info(f"Agent for {user_id} set to {'busy' if busy else 'available'}")
    
    async def is_agent_busy(self, user_id: str) -> bool:
        """Check if a user's agent is busy.
        
        Args:
            user_id: The user ID.
            
        Returns:
            True if busy, False otherwise.
        """
        session = await self.session_store.get_session(user_id)
        return session.get("agent_busy", False) if session else False
    
    def get_agent_for_user(self, user_id: str) -> Optional[ChatAgent]:
        """Get the chat agent for a user.
        
        Args:
            user_id: The user ID.
            
        Returns:
            The chat agent, or None if not found.
        """
        return self.user_agents.get(user_id)
    
    def set_agent_for_user(self, user_id: str, agent: ChatAgent):
        """Set the chat agent for a user.
        
        Args:
            user_id: The user ID.
            agent: The chat agent.
        """
        self.user_agents[user_id] = agent
        logger.info(f"Chat agent set for user {user_id}")
    
    async def _send_heartbeat(self, websocket: WebSocket, user_id: str, conn_id: str):
        """Send periodic heartbeats to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
                # Check if connection still active
                if user_id not in self.active_connections or websocket not in self.active_connections[user_id]:
                    logger.debug(f"Connection for {user_id} no longer active, stopping heartbeat")
                    break
                
                try:
                    # Send a ping message as heartbeat
                    heartbeat_msg = {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_json(heartbeat_msg)
                    logger.debug(f"Heartbeat sent to {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to send heartbeat to {user_id}: {str(e)}")
                    # Connection probably dead, clean it up
                    await self.disconnect(websocket, user_id)
                    break
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task for {user_id} cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat task for {user_id}: {str(e)}")
    
    def start_cleanup_task(self):
        """Start the periodic cleanup task."""
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("Started WebSocket connection cleanup task")
    
    async def _periodic_cleanup(self):
        """Periodically clean up inactive connections."""
        try:
            while True:
                await asyncio.sleep(60)  # Run cleanup every minute
                await self._cleanup_inactive_connections()
                await self._cleanup_dead_heartbeat_tasks()
                logger.debug(f"WebSocket cleanup completed. Active connections: {self.total_connections}")
        except asyncio.CancelledError:
            logger.info("WebSocket connection cleanup task cancelled")
        except Exception as e:
            logger.error(f"Error in WebSocket connection cleanup task: {str(e)}")
            logger.debug(traceback.format_exc())
    
    async def _cleanup_inactive_connections(self):
        """Clean up inactive connections."""
        now = datetime.now()
        connections_to_close = []
        
        async with self.lock:
            for user_id, connections in list(self.active_connections.items()):
                for ws in list(connections):
                    if ws in self.connection_last_activity:
                        last_activity = self.connection_last_activity[ws]
                        if (now - last_activity).total_seconds() > CONNECTION_IDLE_TIMEOUT:
                            connections_to_close.append((ws, user_id))
        
        # Close connections outside the lock to avoid deadlocks
        for ws, user_id in connections_to_close:
            try:
                logger.info(f"Closing inactive WebSocket connection for user {user_id}")
                await ws.close(code=status.WS_1000_NORMAL_CLOSURE, reason="Inactivity timeout")
            except Exception as e:
                logger.error(f"Error closing inactive WebSocket: {str(e)}")
            finally:
                # Ensure connection is properly removed
                await self.disconnect(ws, user_id)
    
    async def _cleanup_dead_heartbeat_tasks(self):
        """Clean up completed or failed heartbeat tasks."""
        async with self.lock:
            for conn_id, task in list(self.heartbeat_tasks.items()):
                if task.done():
                    try:
                        # Check if there was an exception
                        task.result()
                    except Exception as e:
                        logger.warning(f"Heartbeat task for {conn_id} failed: {str(e)}")
                    finally:
                        del self.heartbeat_tasks[conn_id]
    
    async def stop(self):
        """Stop the connection manager and clean up resources."""
        logger.info("Stopping WebSocket connection manager")
        
        # Cancel cleanup task
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all heartbeat tasks
        for conn_id, task in list(self.heartbeat_tasks.items()):
            if not task.done():
                task.cancel()
        
        # Announce instance offline in distributed mode
        if self.distributed_mode and self.message_broker:
            try:
                await self.message_broker.publish("ws_instances", {
                    "action": "instance_offline",
                    "instance_id": self.instance_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Stop message broker
                await self.message_broker.stop()
            except Exception as e:
                logger.error(f"Error during distributed shutdown: {str(e)}")
        
        # Close all connections
        close_tasks = []
        for user_id, connections in list(self.active_connections.items()):
            for websocket in connections:
                try:
                    close_tasks.append(asyncio.create_task(
                        websocket.close(code=status.WS_1001_GOING_AWAY, reason="Server shutdown")
                    ))
                except Exception as e:
                    logger.error(f"Error closing WebSocket for {user_id}: {e}")
        
        # Wait for all connections to close
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Clear all tracking data
        self.active_connections.clear()
        self.connection_last_activity.clear()
        self.heartbeat_tasks.clear()
        self.total_connections = 0
        
        # Cleanup supporting components
        await self.session_store.cleanup()
        await self.security_manager.cleanup()
        await self.reconnect_handler.cleanup()
        
        logger.info("WebSocket connection manager stopped")

# Create a singleton instance
chat_manager = ChatConnectionManager()
