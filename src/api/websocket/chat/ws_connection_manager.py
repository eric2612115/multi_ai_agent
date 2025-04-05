"""WebSocket connection manager for chat service.

This module provides connection management functionality for chat WebSockets.
"""
import logging
import asyncio
import json
import time
import os
from typing import Dict, List, Optional, Any, Union, Set
from fastapi import WebSocket, status
from datetime import datetime, timedelta
import uuid
import traceback

from ai.chat_agent import ChatAgent

# Setup logging
logger = logging.getLogger(__name__)

# Configuration - will be loaded from environment variables or defaults
MAX_CONNECTIONS_PER_USER = int(os.environ.get("MAX_CONNECTIONS_PER_USER", "10"))  # Increased from 5 to 10
CONNECTION_IDLE_TIMEOUT = int(os.environ.get("CONNECTION_IDLE_TIMEOUT", "300"))  # 5 minutes
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))  # 30 seconds
GLOBAL_CONNECTION_LIMIT = int(os.environ.get("GLOBAL_CONNECTION_LIMIT", "1000"))

class ChatConnectionManager:
    """Manager for chat WebSocket connections."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_agents: Dict[str, ChatAgent] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self.total_connections = 0
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self.cleanup_task = None
        self.connection_last_activity: Dict[WebSocket, datetime] = {}
        self.blacklisted_ips: Set[str] = set()  # 初始化為空集合，移除預設的黑名單
        self.ip_connection_count: Dict[str, int] = {}
        self.rate_limit_counters: Dict[str, List[datetime]] = {}
    
    # 訂閱事件處理
    async def handle_subscription_message(self, data: Dict[str, Any], websocket: WebSocket, user_id: str) -> bool:
        """處理訂閱事件的消息。
        
        Args:
            data: 消息數據。
            websocket: WebSocket連接。
            user_id: 用戶ID。
            
        Returns:
            處理成功返回True，否則返回False。
        """
        action = data.get("action")
        event_type = data.get("event_type")
        
        if action == "subscribe" and event_type:
            logger.info(f"User {user_id} subscribed to event: {event_type}")
            # 處理訂閱邏輯
            # 這裡如果需要，可以保存用戶的訂閱信息
            
            # 通知客戶端訂閱成功
            await websocket.send_json({
                "message_type": "subscription_success",
                "event_type": event_type,
                "text": f"Successfully subscribed to {event_type} events",
                "id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "sender": "system"
            })
            return True
        
        return False
    
    def check_rate_limit(self, user_id: str, max_requests: int = 30, time_window: int = 60) -> bool:
        """Check if a user has exceeded rate limits.
        
        Args:
            user_id: The user ID.
            max_requests: Maximum number of requests allowed in the time window.
            time_window: Time window in seconds.
            
        Returns:
            True if rate limit exceeded, False otherwise.
        """
        now = datetime.now()
        if user_id not in self.rate_limit_counters:
            self.rate_limit_counters[user_id] = []
        
        # Clean up old timestamps
        self.rate_limit_counters[user_id] = [
            ts for ts in self.rate_limit_counters[user_id] 
            if (now - ts).total_seconds() < time_window
        ]
        
        # Check if limit exceeded
        if len(self.rate_limit_counters[user_id]) >= max_requests:
            return True
        
        # Add current timestamp
        self.rate_limit_counters[user_id].append(now)
        return False
    
    async def connect(self, websocket: WebSocket, user_id: str, client_ip: str = None) -> bool:
        """Accept a WebSocket connection and store it.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
            client_ip: Client IP address for rate limiting.
            
        Returns:
            True if connection accepted, False otherwise.
        """
        # Check global connection limit
        if self.total_connections >= GLOBAL_CONNECTION_LIMIT:
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER, reason="Server connection limit reached")
            logger.warning(f"Connection from {user_id} rejected: global connection limit reached")
            return False
        
        # 開發環境特別處理：允許127.0.0.1 (localhost)連接，不論黑名單
        logger.info(f"Client IP: {client_ip}")
        if client_ip == "127.0.0.1":
            logger.info(f"Allowing localhost connection for development: {user_id}")
        # 非localhost，正常檢查黑名單
        elif client_ip and client_ip in self.blacklisted_ips:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="IP address is blacklisted")
            logger.warning(f"Connection from {user_id} (IP: {client_ip}) rejected: blacklisted IP")
            return False
        
        # Rate limiting by IP if provided (降低IP的連接數限制以允許更多開發環境連接)
        if client_ip and client_ip != "127.0.0.1":  # 排除localhost
            # Update IP connection count
            self.ip_connection_count[client_ip] = self.ip_connection_count.get(client_ip, 0) + 1
            
            # Check for suspicious activity (too many connections from same IP)
            if self.ip_connection_count[client_ip] > 50:  # 提高閾值，從20增加到50
                self.blacklisted_ips.add(client_ip)
                logger.warning(f"IP {client_ip} blacklisted for suspicious activity")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Too many connections from this IP")
                return False
        
        # Check rate limit (對於開發環境不進行速率限制)
        if client_ip != "127.0.0.1" and self.check_rate_limit(user_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")
            logger.warning(f"Connection from {user_id} rejected: rate limit exceeded")
            return False
        
        try:
            # Accept the connection
            await websocket.accept()
            
            async with self.lock:
                # Check per-user connection limit (for localhost, allow up to 20 connections)
                max_conn = 20 if client_ip == "127.0.0.1" else MAX_CONNECTIONS_PER_USER
                
                if user_id in self.active_connections and len(self.active_connections[user_id]) >= max_conn:
                    await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER, 
                                        reason=f"Maximum of {max_conn} connections per user")
                    logger.warning(f"Connection from {user_id} rejected: per-user connection limit reached")
                    return False
                
                # Add connection
                if user_id not in self.active_connections:
                    self.active_connections[user_id] = []
                
                self.active_connections[user_id].append(websocket)
                self.total_connections += 1
                self.connection_last_activity[websocket] = datetime.now()
                
                # Initialize user session
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = {
                        "last_message_time": datetime.now(),
                        "reconnect_count": 0,
                        "agent_busy": False,
                        "created_at": datetime.now(),
                        "client_ip": client_ip
                    }
                else:
                    self.user_sessions[user_id]["reconnect_count"] += 1
                    self.user_sessions[user_id]["last_message_time"] = datetime.now()
                
                logger.info(f"Chat WebSocket connection established for user {user_id} (Total: {self.total_connections})")
                
                # Start heartbeat
                conn_id = f"{user_id}_{id(websocket)}"
                heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket, user_id, conn_id))
                self.heartbeat_tasks[conn_id] = heartbeat_task
                
                return True
                
        except Exception as e:
            logger.error(f"Error accepting chat WebSocket connection: {str(e)}")
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
                
                # Remove the user if no more connections
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    
                    # Update session data
                    if user_id in self.user_sessions:
                        self.user_sessions[user_id]["last_disconnect_time"] = datetime.now()
                        self.user_sessions[user_id]["agent_busy"] = False
                        
                        # Clean up client IP tracking if this was the last connection
                        client_ip = self.user_sessions[user_id].get("client_ip")
                        if client_ip and client_ip in self.ip_connection_count:
                            self.ip_connection_count[client_ip] = max(0, self.ip_connection_count[client_ip] - 1)
            
            logger.info(f"Chat WebSocket connection closed for user {user_id} (Total: {self.total_connections})")
    
    async def send_message(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific user.
        
        Args:
            user_id: The user ID.
            message: The message to send.
            
        Returns:
            True if message was sent successfully, False otherwise.
        """
        if user_id not in self.active_connections or not self.active_connections[user_id]:
            logger.warning(f"Attempted to send message to disconnected client: {user_id}")
            return False
            
        success = False
        failed_connections = []
        
        # Try each connection until one succeeds
        for websocket in self.active_connections[user_id]:
            try:
                # Send to client
                await websocket.send_json(message)
                logger.debug(f"Message sent to {user_id}: {message.get('id', 'unknown')}")
                
                # Update activity timestamp
                self.connection_last_activity[websocket] = datetime.now()
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["last_message_time"] = datetime.now()
                
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
                    
                    # Update session data
                    if user_id in self.user_sessions:
                        self.user_sessions[user_id]["last_disconnect_time"] = datetime.now()
                        self.user_sessions[user_id]["agent_busy"] = False
        
        return success
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_user_id: str = None):
        """Broadcast a message to all connected users.
        
        Args:
            message: The message to send.
            exclude_user_id: Optional user ID to exclude from the broadcast.
        """
        failed_connections = []
        
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
                    failed_connections.append((user_id, websocket))
        
        # Clean up failed connections
        if failed_connections:
            async with self.lock:
                for user_id, websocket in failed_connections:
                    if user_id in self.active_connections and websocket in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(websocket)
                        self.total_connections -= 1
                        if websocket in self.connection_last_activity:
                            del self.connection_last_activity[websocket]
                    
                    # Remove user if no more connections
                    if user_id in self.active_connections and not self.active_connections[user_id]:
                        del self.active_connections[user_id]
    
    def update_activity(self, websocket: WebSocket, user_id: str):
        """Update the last activity timestamp for a connection.
        
        Args:
            websocket: The WebSocket connection.
            user_id: The user ID.
        """
        self.connection_last_activity[websocket] = datetime.now()
        if user_id in self.user_sessions:
            self.user_sessions[user_id]["last_message_time"] = datetime.now()
    
    def set_agent_busy(self, user_id: str, busy: bool):
        """Set whether a user's agent is busy.
        
        Args:
            user_id: The user ID.
            busy: Whether the agent is busy.
        """
        if user_id in self.user_sessions:
            self.user_sessions[user_id]["agent_busy"] = busy
            logger.info(f"Agent for {user_id} set to {'busy' if busy else 'available'}")
    
    def is_agent_busy(self, user_id: str) -> bool:
        """Check if a user's agent is busy.
        
        Args:
            user_id: The user ID.
            
        Returns:
            True if busy, False otherwise.
        """
        return self.user_sessions.get(user_id, {}).get("agent_busy", False)
    
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
    
    def _is_socket_open(self, websocket: WebSocket) -> bool:
        """檢查WebSocket連接是否仍然開放。
        
        Args:
            websocket: WebSocket連接。
            
        Returns:
            如果連接仍然開放則為True，否則為False。
        """
        try:
            # 嘗試獲取客戶端狀態，若連接關閉則會有問題
            client = websocket.client
            return client is not None
        except Exception:
            return False

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
        self.user_sessions.clear()
        self.connection_last_activity.clear()
        self.heartbeat_tasks.clear()
        self.total_connections = 0
        
        logger.info("WebSocket connection manager stopped")
    
    async def _send_heartbeat(self, websocket: WebSocket, user_id: str, conn_id: str):
        """Send periodic heartbeats to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
                # Check if user session still exists
                if user_id not in self.user_sessions:
                    logger.debug(f"User session for {user_id} no longer exists, stopping heartbeat")
                    break
                
                # Check if connection still active
                if user_id not in self.active_connections or websocket not in self.active_connections[user_id]:
                    logger.debug(f"Connection for {user_id} no longer active, stopping heartbeat")
                    break
                
                try:
                    # First, verify the connection is still open before attempting to send
                    if not self._is_socket_open(websocket):
                        logger.debug(f"WebSocket connection for {user_id} appears to be closed, stopping heartbeat")
                        await self.disconnect(websocket, user_id)
                        break
                        
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
                logger.debug(f"WebSocket connection cleanup completed. Active connections: {self.total_connections}")
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
                # Remove from active connections if still present
                async with self.lock:
                    if ws in self.connection_last_activity:
                        del self.connection_last_activity[ws]
                    if user_id in self.active_connections and ws in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(ws)
                        self.total_connections -= 1
                        if not self.active_connections[user_id]:
                            del self.active_connections[user_id]
    
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

# Create a singleton instance
chat_manager = ChatConnectionManager()
