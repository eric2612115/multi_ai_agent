"""WebSocket reconnection handler.

This module provides functionality for handling WebSocket reconnections,
maintaining session continuity across disconnections, and supporting
distributed deployments.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import uuid

from src.common.config import get_settings

# Setup logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()
RECONNECT_GRACE_PERIOD = int(getattr(settings, "RECONNECT_GRACE_PERIOD", 120))  # 2 minutes
RECONNECT_MAX_ATTEMPTS = int(getattr(settings, "RECONNECT_MAX_ATTEMPTS", 5))

class ReconnectHandler:
    """Handler for WebSocket reconnection logic.
    
    Provides:
    - Reconnection token management
    - Session state preservation
    - Cross-instance redirect support
    - Automatic session recovery
    """
    
    def __init__(self):
        """Initialize the reconnect handler."""
        self.reconnect_tokens: Dict[str, Tuple[str, datetime]] = {}  # token -> (user_id, expiry)
        self.pending_reconnections: Dict[str, Dict[str, Any]] = {}  # user_id -> reconnection data
        self.user_instance_map: Dict[str, str] = {}  # user_id -> instance_id
        self.token_lock = asyncio.Lock()
        self.redis_client = None
        self.distributed_mode = getattr(settings, "USE_DISTRIBUTED_MODE", False)
    
    async def initialize(self):
        """Initialize the reconnect handler."""
        if self.distributed_mode:
            try:
                import redis.asyncio as redis
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self.redis_client = redis.from_url(redis_url)
                await self.redis_client.ping()
                logger.info("Reconnect handler initialized with Redis backend")
            except ImportError:
                logger.warning("Redis package not available, using in-memory reconnect handler")
                self.distributed_mode = False
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                logger.warning("Falling back to in-memory reconnect handler")
                self.distributed_mode = False
        
        if not self.distributed_mode:
            logger.info("Reconnect handler initialized with in-memory backend")
    
    async def issue_reconnect_token(self, user_id: str, token: Optional[str] = None) -> str:
        """Issue a reconnect token for a user.
        
        Args:
            user_id: User ID.
            token: Optional specific token to use.
            
        Returns:
            The reconnect token.
        """
        if not token:
            token = str(uuid.uuid4())
            
        expiry = datetime.now() + timedelta(minutes=5)
        
        async with self.token_lock:
            self.reconnect_tokens[token] = (user_id, expiry)
        
        if self.distributed_mode and self.redis_client:
            # Store in Redis with 5 minute expiry
            token_key = f"ws_reconnect_token:{token}"
            token_data = {
                "user_id": user_id,
                "expiry": expiry.isoformat()
            }
            
            await self.redis_client.setex(
                token_key,
                300,  # 5 minutes in seconds
                json.dumps(token_data)
            )
            
            # Publish token issuance
            await self.redis_client.publish(
                "ws_tokens",
                json.dumps({
                    "action": "token_issued",
                    "user_id": user_id,
                    "token": token,
                    "expiry": expiry.isoformat()
                })
            )
        
        logger.info(f"Reconnect token issued for user {user_id}")
        return token
    
    async def validate_reconnect_token(self, token: str) -> Optional[str]:
        """Validate a reconnect token.
        
        Args:
            token: Reconnect token.
            
        Returns:
            User ID if valid, None otherwise.
        """
        if not token:
            return None
        
        # First check local cache
        async with self.token_lock:
            if token in self.reconnect_tokens:
                user_id, expiry = self.reconnect_tokens[token]
                
                # Check if token has expired
                if datetime.now() > expiry:
                    del self.reconnect_tokens[token]
                    return None
                
                return user_id
        
        # If not found locally and in distributed mode, check Redis
        if self.distributed_mode and self.redis_client:
            token_key = f"ws_reconnect_token:{token}"
            token_data = await self.redis_client.get(token_key)
            
            if token_data:
                try:
                    data = json.loads(token_data)
                    user_id = data.get("user_id")
                    expiry_str = data.get("expiry")
                    
                    if user_id and expiry_str:
                        expiry = datetime.fromisoformat(expiry_str)
                        
                        # Check if token has expired
                        if datetime.now() > expiry:
                            await self.redis_client.delete(token_key)
                            return None
                        
                        # Cache token locally
                        async with self.token_lock:
                            self.reconnect_tokens[token] = (user_id, expiry)
                        
                        return user_id
                except (json.JSONDecodeError, ValueError):
                    pass
        
        return None
    
    async def invalidate_reconnect_token(self, token: str) -> bool:
        """Invalidate a reconnect token.
        
        Args:
            token: Reconnect token.
            
        Returns:
            True if successful, False otherwise.
        """
        if not token:
            return False
        
        async with self.token_lock:
            if token in self.reconnect_tokens:
                del self.reconnect_tokens[token]
        
        if self.distributed_mode and self.redis_client:
            token_key = f"ws_reconnect_token:{token}"
            await self.redis_client.delete(token_key)
            
            # Publish token invalidation
            await self.redis_client.publish(
                "ws_tokens",
                json.dumps({
                    "action": "token_invalidated",
                    "token": token
                })
            )
        
        return True
    
    async def save_disconnect_state(self, user_id: str, state: Optional[Dict[str, Any]] = None) -> bool:
        """Save disconnection state for potential reconnection.
        
        Args:
            user_id: User ID.
            state: Optional state data to save.
            
        Returns:
            True if successful, False otherwise.
        """
        if not user_id:
            return False
        
        # Create basic reconnection data
        reconnect_data = {
            "disconnect_time": datetime.now(),
            "reconnect_attempts": 0
        }
        
        # Add custom state if provided
        if state:
            reconnect_data.update(state)
        
        # Store locally
        self.pending_reconnections[user_id] = reconnect_data
        
        # Store in Redis if in distributed mode
        if self.distributed_mode and self.redis_client:
            reconnect_key = f"ws_reconnect:{user_id}"
            
            # Convert datetime objects to strings
            data_to_store = reconnect_data.copy()
            for key, value in data_to_store.items():
                if isinstance(value, datetime):
                    data_to_store[key] = value.isoformat()
            
            # Store with grace period expiry
            await self.redis_client.setex(
                reconnect_key,
                RECONNECT_GRACE_PERIOD + 60,  # Grace period + 1 minute buffer
                json.dumps(data_to_store)
            )
        
        logger.info(f"Disconnect state saved for user {user_id}")
        return True
    
    async def can_recover_session(self, user_id: str) -> bool:
        """Check if a session can be recovered for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            True if session can be recovered, False otherwise.
        """
        if not user_id:
            return False
        
        # First check local cache
        if user_id in self.pending_reconnections:
            data = self.pending_reconnections[user_id]
            disconnect_time = data.get("disconnect_time")
            reconnect_attempts = data.get("reconnect_attempts", 0)
            
            # Check reconnection window
            if (disconnect_time and 
                (datetime.now() - disconnect_time).total_seconds() <= RECONNECT_GRACE_PERIOD and
                reconnect_attempts < RECONNECT_MAX_ATTEMPTS):
                return True
        
        # If not found locally and in distributed mode, check Redis
        if self.distributed_mode and self.redis_client:
            reconnect_key = f"ws_reconnect:{user_id}"
            reconnect_data = await self.redis_client.get(reconnect_key)
            
            if reconnect_data:
                try:
                    data = json.loads(reconnect_data)
                    disconnect_time_str = data.get("disconnect_time")
                    reconnect_attempts = data.get("reconnect_attempts", 0)
                    
                    if disconnect_time_str:
                        disconnect_time = datetime.fromisoformat(disconnect_time_str)
                        
                        # Check reconnection window
                        if ((datetime.now() - disconnect_time).total_seconds() <= RECONNECT_GRACE_PERIOD and
                            reconnect_attempts < RECONNECT_MAX_ATTEMPTS):
                            
                            # Cache data locally
                            data["disconnect_time"] = disconnect_time
                            self.pending_reconnections[user_id] = data
                            
                            return True
                except (json.JSONDecodeError, ValueError):
                    pass
        
        return False
    
    async def get_reconnect_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get reconnection state for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            Reconnection state if available, None otherwise.
        """
        if not user_id:
            return None
        
        # First check local cache
        if user_id in self.pending_reconnections:
            return self.pending_reconnections[user_id]
        
        # If not found locally and in distributed mode, check Redis
        if self.distributed_mode and self.redis_client:
            reconnect_key = f"ws_reconnect:{user_id}"
            reconnect_data = await self.redis_client.get(reconnect_key)
            
            if reconnect_data:
                try:
                    data = json.loads(reconnect_data)
                    
                    # Convert ISO format strings back to datetime objects
                    for key in ["disconnect_time"]:
                        if key in data and isinstance(data[key], str):
                            try:
                                data[key] = datetime.fromisoformat(data[key])
                            except ValueError:
                                pass
                    
                    # Cache data locally
                    self.pending_reconnections[user_id] = data
                    
                    return data
                except json.JSONDecodeError:
                    pass
        
        return None
    
    async def increment_reconnect_attempts(self, user_id: str) -> int:
        """Increment reconnection attempts for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            New number of reconnection attempts.
        """
        if not user_id:
            return 0
        
        # Get current state
        state = await self.get_reconnect_state(user_id)
        
        if not state:
            return 0
        
        # Increment attempts
        attempts = state.get("reconnect_attempts", 0) + 1
        state["reconnect_attempts"] = attempts
        
        # Update state
        if self.distributed_mode and self.redis_client:
            reconnect_key = f"ws_reconnect:{user_id}"
            
            # Convert datetime objects to strings
            data_to_store = state.copy()
            for key, value in data_to_store.items():
                if isinstance(value, datetime):
                    data_to_store[key] = value.isoformat()
            
            # Update with remaining TTL
            ttl = await self.redis_client.ttl(reconnect_key)
            if ttl > 0:
                await self.redis_client.setex(
                    reconnect_key,
                    ttl,
                    json.dumps(data_to_store)
                )
        
        # Update local cache
        self.pending_reconnections[user_id] = state
        
        return attempts
    
    async def clear_reconnect_state(self, user_id: str) -> bool:
        """Clear reconnection state for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            True if successful, False otherwise.
        """
        if not user_id:
            return False
        
        # Clear from local cache
        if user_id in self.pending_reconnections:
            del self.pending_reconnections[user_id]
        
        # Clear from Redis if in distributed mode
        if self.distributed_mode and self.redis_client:
            reconnect_key = f"ws_reconnect:{user_id}"
            await self.redis_client.delete(reconnect_key)
        
        return True
    
    async def check_redirect(self, user_id: str, current_instance_id: str) -> Optional[Dict[str, Any]]:
        """Check if a user should be redirected to another instance.
        
        Args:
            user_id: User ID.
            current_instance_id: Current instance ID.
            
        Returns:
            Redirect information if needed, None otherwise.
        """
        if not self.distributed_mode or not self.redis_client:
            return None
        
        try:
            # Check if user is connected to another instance
            instance_key = f"ws_user_instance:{user_id}"
            instance_id = await self.redis_client.get(instance_key)
            
            if instance_id:
                instance_id = instance_id.decode('utf-8')
                
                # If connected to a different instance, redirect
                if instance_id != current_instance_id:
                    # Verify instance is still active
                    instance_heartbeat_key = f"ws_instance_heartbeat:{instance_id}"
                    active = await self.redis_client.exists(instance_heartbeat_key)
                    
                    if active:
                        return {
                            "should_redirect": True,
                            "instance_id": instance_id
                        }
            
            # No redirect needed, register current instance
            await self.redis_client.setex(
                instance_key,
                300,  # 5 minutes
                current_instance_id
            )
            
            return None
        except Exception as e:
            logger.error(f"Error checking redirect for user {user_id}: {str(e)}")
            return None
    
    async def handle_remote_connection(self, user_id: str, event: Dict[str, Any]) -> None:
        """Handle connection event from another instance.
        
        Args:
            user_id: User ID.
            event: Event data.
        """
        instance_id = event.get("instance_id")
        if not instance_id:
            return
        
        # Update user instance map
        self.user_instance_map[user_id] = instance_id
    
    async def handle_remote_disconnection(self, user_id: str, event: Dict[str, Any]) -> None:
        """Handle disconnection event from another instance.
        
        Args:
            user_id: User ID.
            event: Event data.
        """
        instance_id = event.get("instance_id")
        if not instance_id:
            return
        
        # Only remove from map if it's the same instance
        if user_id in self.user_instance_map and self.user_instance_map[user_id] == instance_id:
            del self.user_instance_map[user_id]
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.distributed_mode and self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")
                
        self.reconnect_tokens.clear()
        self.pending_reconnections.clear()
        self.user_instance_map.clear()
