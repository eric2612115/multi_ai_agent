"""Event bus for system communication.

This module provides an event bus for publishing and subscribing to events
throughout the system.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
import json
from bson import ObjectId
from datetime import datetime

logger = logging.getLogger(__name__)

# 自定义JSON编码器，处理ObjectId和其他特殊类型
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles ObjectId and other special types."""
    
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class EventBus:
    """Event bus for system communication.
    
    This class provides a simple publish-subscribe mechanism for
    asynchronous event-driven communication between components.
    """
    
    _instance = None
    
    def __new__(cls):
        """Create a new instance of EventBus or return the existing one (singleton)."""
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the event bus."""
        if self._initialized:
            return
            
        self._subscribers = {}
        self._event_history = {}
        self._lock = asyncio.Lock()
        self._max_history = 100  # Maximum number of events to keep in history per type
        self._initialized = True
        
        logger.info("Event bus initialized")
    
    async def publish(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish an event to subscribers.
        
        Args:
            event_type: The type of event.
            event_data: The event data.
        """
        # Convert objects like ObjectId to serializable form to avoid issues with JSON serialization
        # First convert to JSON and back to create a clean deep copy with serializable types
        try:
            serialized_data = json.dumps(event_data, cls=CustomJSONEncoder)
            clean_event_data = json.loads(serialized_data)
        except Exception as e:
            logger.error(f"Failed to serialize event data: {str(e)}")
            # Fallback to the original data and hope for the best
            clean_event_data = event_data
            
        async with self._lock:
            # Add to history
            if event_type not in self._event_history:
                self._event_history[event_type] = []
                
            history = self._event_history[event_type]
            history.append(clean_event_data)
            
            # Trim history if too long
            if len(history) > self._max_history:
                self._event_history[event_type] = history[-self._max_history:]
                
            # Get subscribers for this event type
            subscribers = self._subscribers.get(event_type, [])
            
        # Notify subscribers (outside the lock to prevent deadlocks)
        for subscriber in subscribers:
            try:
                await subscriber(clean_event_data)
            except Exception as e:
                logger.error(f"Error in event subscriber for {event_type}: {str(e)}")
                
        logger.debug(f"Published event {event_type} with data: {serialized_data[:200]}...")
    
    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Subscribe to an event type.
        
        Args:
            event_type: The type of event to subscribe to.
            callback: The callback function to call when an event is published.
                      Must be an async function.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
            
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to event type: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """Unsubscribe from an event type.
        
        Args:
            event_type: The type of event to unsubscribe from.
            callback: The callback function to remove.
            
        Returns:
            True if the subscription was removed, False otherwise.
        """
        if event_type not in self._subscribers:
            return False
            
        subscribers = self._subscribers[event_type]
        if callback in subscribers:
            subscribers.remove(callback)
            logger.debug(f"Unsubscribed from event type: {event_type}")
            return True
            
        return False
    
    async def get_event_history(self, event_type: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get the history of events for a specific type.
        
        Args:
            event_type: The type of event to get history for.
            limit: Optional limit on the number of events to return.
            
        Returns:
            List of events, newest first.
        """
        async with self._lock:
            history = self._event_history.get(event_type, [])
            
            if limit is not None:
                return history[-limit:]
            else:
                return history.copy()
    
    async def clear_history(self, event_type: Optional[str] = None) -> None:
        """Clear the event history.
        
        Args:
            event_type: Optional event type to clear. If None, all history is cleared.
        """
        async with self._lock:
            if event_type is None:
                self._event_history = {}
            elif event_type in self._event_history:
                self._event_history[event_type] = []
                
    def on(self, event_type: str):
        """Decorator for subscribing to events.
        
        Args:
            event_type: The type of event to subscribe to.
            
        Returns:
            A decorator function that registers the decorated function as a subscriber.
        """
        def decorator(func: Callable[[Dict[str, Any]], Awaitable[None]]):
            self.subscribe(event_type, func)
            return func
        return decorator
    
    async def emit(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Emit an event (alias for publish).
        
        Args:
            event_type: The type of event.
            event_data: The event data.
        """
        # Just pass through to publish
        await self.publish(event_type, event_data)
