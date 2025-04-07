"""WebSocket session storage and management.

This module provides session storage and management for WebSocket connections,
supporting both in-memory and distributed sessions.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
import json

from src.common.config import get_settings

# Setup logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

class WebSocketSessionStore:
    """Storage and management for WebSocket session data.
    
    Supports:
    - In-memory session storage
    - Session state tracking
    - Session recovery
    - Distributed session synchronization
    """
    
    def __init__(self):
        """Initialize the session store."""
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_lock = asyncio.Lock()
        self.redis_client = None
        self.distributed_mode = getattr(settings, "USE_DISTRIBUTED_MODE", False)
    
    async def initialize(self):
        """Initialize the session store."""
        if self.distributed_mode:
            try:
                import redis.asyncio as redis
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self.redis_client = redis.from_url(redis_url)
                await self.redis_client.ping()
                logger.info("Session store initialized with Redis backend")
            except ImportError:
                logger.warning("Redis package not available, using in-memory session store")
                self.distributed_mode = False
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                logger.warning("Falling back to in-memory session store")
                self.distributed_mode = False
        
        if not self.distributed_mode:
            logger.info("Session store initialized with in-memory backend")
    
    async def create_or_update_session(self, user_id: str, session_data: Dict[str, Any]) -> bool:
        """Create or update a session.
        
        Args:
            user_id: User ID.
            session_data: Session data to store.
            
        Returns:
            True if successful, False otherwise.
        """
        if not user_id:
            return False
        
        try:
            now = datetime.now()
            
            # Update timestamps
            session_data['updated_at'] = now
            if 'created_at' not in session_data:
                session_data['created_at'] = now
            
            # Store session
            if self.distributed_mode and self.redis_client:
                # Store in Redis
                session_key = f"ws_session:{user_id}"
                
                # Merge with existing data if available
                existing_data = await self.redis_client.get(session_key)
                if existing_data:
                    try:
                        existing_session = json.loads(existing_data)
                        # Preserve creation time and other metadata
                        if 'created_at' in existing_session:
                            session_data['created_at'] = existing_session['created_at']
                        # Update with new data
                        existing_session.update(session_data)
                        session_data = existing_session
                    except json.JSONDecodeError:
                        pass
                
                # Convert datetime objects to strings
                for key, value in session_data.items():
                    if isinstance(value, datetime):
                        session_data[key] = value.isoformat()
                
                # Store in Redis with 24 hour expiry
                await self.redis_client.setex(
                    session_key,
                    60 * 60 * 24,  # 24 hours in seconds
                    json.dumps(session_data)
                )
                
                # Publish update event
                await self.redis_client.publish(
                    "ws_sessions",
                    json.dumps({
                        "action": "session_update",
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
            else:
                # Store in memory
                async with self.session_lock:
                    # Create new session or update existing one
                    if user_id not in self.sessions:
                        self.sessions[user_id] = session_data
                    else:
                        self.sessions[user_id].update(session_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating/updating session for {user_id}: {str(e)}")
            return False
    
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a session.
        
        Args:
            user_id: User ID.
            
        Returns:
            Session data or None if not found.
        """
        if not user_id:
            return None
        
        try:
            if self.distributed_mode and self.redis_client:
                # Get from Redis
                session_key = f"ws_session:{user_id}"
                session_data = await self.redis_client.get(session_key)
                
                if not session_data:
                    return None
                
                # Parse JSON
                session = json.loads(session_data)
                
                # Convert ISO format strings back to datetime objects
                for key in ['created_at', 'updated_at', 'last_activity']:
                    if key in session and isinstance(session[key], str):
                        try:
                            session[key] = datetime.fromisoformat(session[key])
                        except ValueError:
                            pass
                
                return session
            else:
                # Get from memory
                async with self.session_lock:
                    return self.sessions.get(user_id)
        except Exception as e:
            logger.error(f"Error getting session for {user_id}: {str(e)}")
            return None
    
    async def update_session(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields in a session.
        
        Args:
            user_id: User ID.
            updates: Fields to update.
            
        Returns:
            True if successful, False otherwise.
        """
        if not user_id or not updates:
            return False
        
        try:
            # Get current session
            session = await self.get_session(user_id)
            
            if not session:
                # Create new session with updates
                return await self.create_or_update_session(user_id, updates)
            
            # Update session
            session.update(updates)
            session['updated_at'] = datetime.now()
            
            return await self.create_or_update_session(user_id, session)
        except Exception as e:
            logger.error(f"Error updating session for {user_id}: {str(e)}")
            return False
    
    async def delete_session(self, user_id: str) -> bool:
        """Delete a session.
        
        Args:
            user_id: User ID.
            
        Returns:
            True if successful, False otherwise.
        """
        if not user_id:
            return False
            
        try:
            if self.distributed_mode and self.redis_client:
                # Delete from Redis
                session_key = f"ws_session:{user_id}"
                await self.redis_client.delete(session_key)
                
                # Publish invalidation event
                await self.redis_client.publish(
                    "ws_sessions",
                    json.dumps({
                        "action": "session_invalidate",
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
            else:
                # Delete from memory
                async with self.session_lock:
                    if user_id in self.sessions:
                        del self.sessions[user_id]
            
            return True
        except Exception as e:
            logger.error(f"Error deleting session for {user_id}: {str(e)}")
            return False
    
    async def update_activity(self, user_id: str) -> bool:
        """Update the last activity timestamp for a session.
        
        Args:
            user_id: User ID.
            
        Returns:
            True if successful, False otherwise.
        """
        return await self.update_session(user_id, {'last_activity': datetime.now()})
    
    async def get_inactive_sessions(self, timeout_seconds: int = 3600) -> List[str]:
        """Get a list of user IDs with inactive sessions.
        
        Args:
            timeout_seconds: Timeout in seconds.
            
        Returns:
            List of user IDs with inactive sessions.
        """
        inactive_users = []
        now = datetime.now()
        timeout = timedelta(seconds=timeout_seconds)
        
        try:
            if self.distributed_mode and self.redis_client:
                # Get all session keys
                keys = []
                cursor = 0
                pattern = "ws_session:*"
                
                while True:
                    cursor, partial_keys = await self.redis_client.scan(cursor, pattern, 100)
                    keys.extend(partial_keys)
                    if cursor == 0:
                        break
                
                # Check each session
                for key in keys:
                    session_data = await self.redis_client.get(key)
                    if not session_data:
                        continue
                    
                    try:
                        session = json.loads(session_data)
                        user_id = key.split(":", 1)[1]
                        
                        last_activity = None
                        if 'last_activity' in session:
                            if isinstance(session['last_activity'], str):
                                last_activity = datetime.fromisoformat(session['last_activity'])
                            else:
                                last_activity = session['last_activity']
                        
                        if last_activity and (now - last_activity) > timeout:
                            inactive_users.append(user_id)
                    except (json.JSONDecodeError, ValueError):
                        pass
            else:
                # Check in-memory sessions
                async with self.session_lock:
                    for user_id, session in self.sessions.items():
                        last_activity = session.get('last_activity')
                        if last_activity and (now - last_activity) > timeout:
                            inactive_users.append(user_id)
            
            return inactive_users
        except Exception as e:
            logger.error(f"Error getting inactive sessions: {str(e)}")
            return []
    
    async def handle_remote_update(self, event: Dict[str, Any]) -> None:
        """Handle session update event from another instance.
        
        Args:
            event: Event data.
        """
        # For local updates in distributed mode, 
        # we don't need to do anything as Redis is already updated
        pass
    
    async def handle_remote_invalidation(self, event: Dict[str, Any]) -> None:
        """Handle session invalidation event from another instance.
        
        Args:
            event: Event data.
        """
        user_id = event.get("user_id")
        if not user_id:
            return
            
        # If using in-memory sessions, also invalidate local copy
        if not self.distributed_mode:
            return
            
        async with self.session_lock:
            if user_id in self.sessions:
                del self.sessions[user_id]
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.distributed_mode and self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")
                
        self.sessions.clear()
