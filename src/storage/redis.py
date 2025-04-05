"""Redis storage implementation.

This module implements the CacheStorage and MessageQueue interfaces using Redis.
"""
import os
import json
import logging
import pickle
from typing import Dict, List, Optional, Any, Tuple, Union

import redis.asyncio as redis
from redis.asyncio.client import Redis
from redis.exceptions import RedisError, ConnectionError

from storage.base import CacheStorage, MessageQueue
from common.config import get_settings
from common.exceptions import StorageConnectionError, StorageQueryError

settings = get_settings()
logger = logging.getLogger(__name__)

class RedisProvider(CacheStorage, MessageQueue):
    """Redis implementation of the CacheStorage and MessageQueue interfaces."""
    
    def __init__(self, connection_uri: Optional[str] = None, prefix: str = ""):
        """Initialize the Redis provider.
        
        Args:
            connection_uri: Optional connection URI. If not provided, it will be loaded from settings.
            prefix: Optional key prefix for namespacing.
        """
        self.connection_uri = connection_uri or settings.db.redis_uri
        self.prefix = prefix
        self.client = None
        self.pubsub = None
        self._subscribed_channels = set()
    
    async def connect(self) -> bool:
        """Connect to Redis.
        
        Returns:
            True if connected successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
        """
        try:
            self.client = redis.from_url(self.connection_uri, decode_responses=True)
            # Test the connection
            await self.client.ping()
            logger.debug(f"Connected to Redis at {self.connection_uri}")
            return True
        except ConnectionError as e:
            raise StorageConnectionError(f"Failed to connect to Redis: {str(e)}")
        except Exception as e:
            raise StorageConnectionError(f"Unexpected error connecting to Redis: {str(e)}")
    
    async def close(self) -> None:
        """Close the Redis connection."""
        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None
            
        if self.client:
            await self.client.close()
            self.client = None
    
    async def is_connected(self) -> bool:
        """Check if connected to Redis.
        
        Returns:
            True if connected.
        """
        if not self.client:
            return False
        
        try:
            # Test the connection
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def _ensure_connected(self) -> None:
        """Ensure that we are connected to Redis.
        
        Raises:
            StorageConnectionError: If connection failed.
        """
        if not await self.is_connected():
            if not self.client:
                await self.connect()
            else:
                raise StorageConnectionError("Lost connection to Redis")
    
    def _prefix_key(self, key: str) -> str:
        """Add prefix to a key if a prefix is set.
        
        Args:
            key: The key.
            
        Returns:
            The prefixed key.
        """
        return f"{self.prefix}:{key}" if self.prefix else key
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key.
        
        Args:
            key: The key.
            
        Returns:
            The value, or None if not found.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            value = await self.client.get(prefixed_key)
            
            if value is None:
                return None
            
            # Try to decode JSON, fall back to the raw value
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            raise StorageQueryError(f"Failed to get value: {str(e)}")
    
    async def set(self, key: str, value: Any, expiry: Optional[int] = None) -> bool:
        """Set a value.
        
        Args:
            key: The key.
            value: The value to set.
            expiry: Optional expiry time in seconds.
            
        Returns:
            True if set successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            
            # Convert value to string if it's not already
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)
            
            if expiry is not None:
                await self.client.setex(prefixed_key, expiry, value)
            else:
                await self.client.set(prefixed_key, value)
            
            return True
        except Exception as e:
            raise StorageQueryError(f"Failed to set value: {str(e)}")
    
    async def delete(self, key: str) -> bool:
        """Delete a value.
        
        Args:
            key: The key.
            
        Returns:
            True if deleted, False if the key didn't exist.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            result = await self.client.delete(prefixed_key)
            
            # Redis returns the number of keys deleted
            return result > 0
        except Exception as e:
            raise StorageQueryError(f"Failed to delete value: {str(e)}")
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key.
            
        Returns:
            True if the key exists.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            result = await self.client.exists(prefixed_key)
            
            # Redis returns 1 if the key exists, 0 otherwise
            return result > 0
        except Exception as e:
            raise StorageQueryError(f"Failed to check if key exists: {str(e)}")
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set an expiry time on a key.
        
        Args:
            key: The key.
            seconds: The expiry time in seconds.
            
        Returns:
            True if the expiry was set, False if the key doesn't exist.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            result = await self.client.expire(prefixed_key, seconds)
            
            # Redis returns 1 if the timeout was set, 0 otherwise
            return result > 0
        except Exception as e:
            raise StorageQueryError(f"Failed to set expiry: {str(e)}")
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a value.
        
        Args:
            key: The key.
            amount: The amount to increment by (default: 1).
            
        Returns:
            The new value, or None if the operation failed.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            
            if amount == 1:
                result = await self.client.incr(prefixed_key)
            else:
                result = await self.client.incrby(prefixed_key, amount)
            
            return result
        except Exception as e:
            raise StorageQueryError(f"Failed to increment value: {str(e)}")
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a value.
        
        Args:
            key: The key.
            amount: The amount to decrement by (default: 1).
            
        Returns:
            The new value, or None if the operation failed.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            
            if amount == 1:
                result = await self.client.decr(prefixed_key)
            else:
                result = await self.client.decrby(prefixed_key, amount)
            
            return result
        except Exception as e:
            raise StorageQueryError(f"Failed to decrement value: {str(e)}")
    
    # MessageQueue interface methods
    
    async def publish(self, channel: str, message: Any) -> bool:
        """Publish a message to a channel.
        
        Args:
            channel: The channel name.
            message: The message to publish.
            
        Returns:
            True if published successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_channel = self._prefix_key(channel)
            
            # Convert message to JSON if it's not a string
            if not isinstance(message, str):
                message = json.dumps(message)
            
            # Publish the message
            recipients = await self.client.publish(prefixed_channel, message)
            
            # Return True if there were recipients (even if 0)
            return True
        except Exception as e:
            raise StorageQueryError(f"Failed to publish message: {str(e)}")
    
    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel.
        
        Args:
            channel: The channel name.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Initialize PubSub if needed
            if self.pubsub is None:
                self.pubsub = self.client.pubsub()
            
            prefixed_channel = self._prefix_key(channel)
            
            # Subscribe to the channel
            await self.pubsub.subscribe(prefixed_channel)
            
            # Add to set of subscribed channels
            self._subscribed_channels.add(prefixed_channel)
        except Exception as e:
            raise StorageQueryError(f"Failed to subscribe to channel: {str(e)}")
    
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.
        
        Args:
            channel: The channel name.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        if self.pubsub is None:
            return
        
        try:
            prefixed_channel = self._prefix_key(channel)
            
            # Unsubscribe from the channel
            await self.pubsub.unsubscribe(prefixed_channel)
            
            # Remove from set of subscribed channels
            if prefixed_channel in self._subscribed_channels:
                self._subscribed_channels.remove(prefixed_channel)
        except Exception as e:
            raise StorageQueryError(f"Failed to unsubscribe from channel: {str(e)}")
    
    async def get_message(self, timeout: Optional[float] = None) -> Optional[Tuple[str, Any]]:
        """Get a message from subscribed channels.
        
        Args:
            timeout: Optional timeout in seconds.
            
        Returns:
            A tuple of (channel, message), or None if no message is available.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        if self.pubsub is None or not self._subscribed_channels:
            return None
        
        try:
            # Get a message
            message = await self.pubsub.get_message(timeout=timeout)
            
            if message is None or message["type"] != "message":
                return None
            
            channel = message["channel"]
            data = message["data"]
            
            # Try to parse as JSON
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass
            
            # Remove prefix from channel name if present
            if self.prefix and channel.startswith(f"{self.prefix}:"):
                channel = channel[len(self.prefix) + 1:]
            
            return (channel, data)
        except Exception as e:
            raise StorageQueryError(f"Failed to get message: {str(e)}")
    
    async def push(self, queue: str, item: Any) -> bool:
        """Push an item to a queue.
        
        Args:
            queue: The queue name.
            item: The item to push.
            
        Returns:
            True if pushed successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_queue = self._prefix_key(queue)
            
            # Convert item to JSON if it's not a string
            if not isinstance(item, str):
                item = json.dumps(item)
            
            # Push to the list (queue)
            await self.client.lpush(prefixed_queue, item)
            
            return True
        except Exception as e:
            raise StorageQueryError(f"Failed to push item to queue: {str(e)}")
    
    async def pop(self, queue: str, timeout: Optional[float] = None) -> Optional[Any]:
        """Pop an item from a queue.
        
        Args:
            queue: The queue name.
            timeout: Optional timeout in seconds. If provided, the method will block until
                an item is available or the timeout is reached.
            
        Returns:
            The popped item, or None if no item is available.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_queue = self._prefix_key(queue)
            
            if timeout is not None:
                # Blocking pop
                result = await self.client.brpop(prefixed_queue, timeout=timeout)
                
                if result is None:
                    return None
                
                # brpop returns (key, value)
                _, item = result
            else:
                # Non-blocking pop
                item = await self.client.rpop(prefixed_queue)
                
                if item is None:
                    return None
            
            # Try to parse as JSON
            try:
                return json.loads(item)
            except json.JSONDecodeError:
                return item
        except Exception as e:
            raise StorageQueryError(f"Failed to pop item from queue: {str(e)}")
    
    # Additional Redis-specific methods
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get a field from a hash.
        
        Args:
            key: The hash key.
            field: The field name.
            
        Returns:
            The field value, or None if not found.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            value = await self.client.hget(prefixed_key, field)
            
            if value is None:
                return None
            
            # Try to decode JSON, fall back to the raw value
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            raise StorageQueryError(f"Failed to get hash field: {str(e)}")
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set a field in a hash.
        
        Args:
            key: The hash key.
            field: The field name.
            value: The value to set.
            
        Returns:
            True if set successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            
            # Convert value to string if it's not already
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)
            
            # Set the field
            await self.client.hset(prefixed_key, field, value)
            
            return True
        except Exception as e:
            raise StorageQueryError(f"Failed to set hash field: {str(e)}")
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields from a hash.
        
        Args:
            key: The hash key.
            
        Returns:
            Dictionary of field names to values.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            prefixed_key = self._prefix_key(key)
            values = await self.client.hgetall(prefixed_key)
            
            if not values:
                return {}
            
            # Try to decode JSON values
            result = {}
            for field, value in values.items():
                try:
                    result[field] = json.loads(value)
                except json.JSONDecodeError:
                    result[field] = value
            
            return result
        except Exception as e:
            raise StorageQueryError(f"Failed to get all hash fields: {str(e)}")
