"""Observer pattern implementation for AI Knowledge Forest.

This module provides a generic observer pattern implementation that can be used
across different components of the system for event handling.
"""
import logging
import asyncio
from typing import Dict, Set, TypeVar, Generic, Any, Optional, List, Protocol, runtime_checkable, Callable, Union, Awaitable, cast

# Generic type for event data
T = TypeVar('T')
# Generic type for event identifiers
ID = TypeVar('ID')

logger = logging.getLogger(__name__)

# Type aliases for event handlers
SyncHandler = Callable[[T], None]
AsyncHandler = Callable[[T], Awaitable[None]]
EventHandler = Union[SyncHandler[T], AsyncHandler[T]]


@runtime_checkable
class Observer(Protocol[T]):
    """Protocol defining the interface for observer objects."""
    
    async def notify(self, event_data: T) -> None:
        """Notify the observer of an event.
        
        Args:
            event_data: Data associated with the event
        """
        ...


class Observable(Generic[ID, T]):
    """Observable class that notifies observers when events occur.
    
    This class implements the observable part of the observer pattern,
    allowing observers to register for events of interest.
    """
    
    def __init__(self):
        """Initialize the observable."""
        self._observers: Dict[ID, Set[EventHandler[T]]] = {}
    
    def add_observer(self, event_id: ID, observer: EventHandler[T]) -> None:
        """Add an observer for an event.
        
        Args:
            event_id: Identifier for the event
            observer: Observer function or method
        """
        if event_id not in self._observers:
            self._observers[event_id] = set()
        self._observers[event_id].add(observer)
    
    def remove_observer(self, event_id: ID, observer: EventHandler[T]) -> None:
        """Remove an observer for an event.
        
        Args:
            event_id: Identifier for the event
            observer: Observer function or method
        """
        if event_id in self._observers and observer in self._observers[event_id]:
            self._observers[event_id].remove(observer)
            # Clean up empty sets
            if not self._observers[event_id]:
                del self._observers[event_id]
    
    async def notify_observers(self, event_id: ID, event_data: T) -> None:
        """Notify all observers of an event.
        
        Args:
            event_id: Identifier for the event
            event_data: Data associated with the event
        """
        if event_id not in self._observers:
            return
            
        # Make a copy of the observers set to avoid modification during iteration
        observers = self._observers[event_id].copy()
        
        # Execute all observer handlers
        for observer in observers:
            try:
                # Check if the observer is a coroutine function or a regular function
                if asyncio.iscoroutinefunction(observer):
                    # It's an async handler
                    await cast(AsyncHandler[T], observer)(event_data)
                else:
                    # It's a sync handler
                    cast(SyncHandler[T], observer)(event_data)
            except Exception as e:
                logger.error(f"Error notifying observer for event {event_id}: {str(e)}")
    
    def has_observers(self, event_id: ID) -> bool:
        """Check if there are any observers for an event.
        
        Args:
            event_id: Identifier for the event
            
        Returns:
            True if there are observers for the event
        """
        return event_id in self._observers and bool(self._observers[event_id])
    
    def get_observer_count(self, event_id: ID) -> int:
        """Get the number of observers for an event.
        
        Args:
            event_id: Identifier for the event
            
        Returns:
            Number of observers for the event
        """
        if event_id not in self._observers:
            return 0
        return len(self._observers[event_id])
    
    def get_registered_events(self) -> List[ID]:
        """Get all registered event types.
        
        Returns:
            List of registered event identifiers
        """
        return list(self._observers.keys())


class EventBus(Generic[ID, T]):
    """Centralized event bus for publishing and subscribing to events.
    
    This class provides a global event bus that allows components to
    communicate without direct dependencies.
    """
    
    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[ID, Set[EventHandler[T]]] = {}
    
    def subscribe(self, event_id: ID, handler: EventHandler[T]) -> None:
        """Subscribe to an event.
        
        Args:
            event_id: Identifier for the event
            handler: Function that handles the event
        """
        if event_id not in self._subscribers:
            self._subscribers[event_id] = set()
        self._subscribers[event_id].add(handler)
        logger.debug(f"Subscribed to event: {event_id}")
    
    def unsubscribe(self, event_id: ID, handler: EventHandler[T]) -> None:
        """Unsubscribe from an event.
        
        Args:
            event_id: Identifier for the event
            handler: Function that handles the event
        """
        if event_id in self._subscribers and handler in self._subscribers[event_id]:
            self._subscribers[event_id].remove(handler)
            # Clean up empty sets
            if not self._subscribers[event_id]:
                del self._subscribers[event_id]
            logger.debug(f"Unsubscribed from event: {event_id}")
    
    async def publish(self, event_id: ID, event_data: T) -> None:
        """Publish an event to all subscribers.
        
        Args:
            event_id: Identifier for the event
            event_data: Data associated with the event
        """
        if event_id not in self._subscribers:
            return
            
        # Make a copy of the subscribers set to avoid modification during iteration
        subscribers = self._subscribers[event_id].copy()
        
        # Execute all subscriber handlers
        for handler in subscribers:
            try:
                # Check if the handler is a coroutine function or a regular function
                if asyncio.iscoroutinefunction(handler):
                    # It's an async handler
                    await cast(AsyncHandler[T], handler)(event_data)
                else:
                    # It's a sync handler
                    cast(SyncHandler[T], handler)(event_data)
            except Exception as e:
                logger.error(f"Error in event handler for event {event_id}: {str(e)}")
    
    def has_subscribers(self, event_id: ID) -> bool:
        """Check if there are any subscribers for an event.
        
        Args:
            event_id: Identifier for the event
            
        Returns:
            True if there are subscribers for the event
        """
        return event_id in self._subscribers and bool(self._subscribers[event_id])
    
    def get_subscriber_count(self, event_id: ID) -> int:
        """Get the number of subscribers for an event.
        
        Args:
            event_id: Identifier for the event
            
        Returns:
            Number of subscribers for the event
        """
        if event_id not in self._subscribers:
            return 0
        return len(self._subscribers[event_id])
    
    def get_registered_events(self) -> List[ID]:
        """Get all registered event types.
        
        Returns:
            List of registered event identifiers
        """
        return list(self._subscribers.keys())
