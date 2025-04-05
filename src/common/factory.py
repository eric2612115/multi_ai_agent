"""Factory pattern implementation for AI Knowledge Forest.

This module provides a generic factory pattern implementation that can be used
across different components of the system.
"""
from typing import Dict, Type, TypeVar, Generic, Any, Optional, List, Callable

# Generic type for products created by factories
T = TypeVar('T')
# Generic type for product identifiers
ID = TypeVar('ID')

class Factory(Generic[ID, T]):
    """Generic factory class for creating objects.
    
    This class implements the factory pattern, allowing for registration and
    creation of different types of objects based on an identifier.
    """
    
    def __init__(self, default_type: Optional[ID] = None):
        """Initialize the factory.
        
        Args:
            default_type: Optional default type to use if not specified
        """
        self._registry: Dict[ID, Type[T]] = {}
        self._default_type = default_type
    
    def register(self, type_id: ID, product_class: Type[T]) -> None:
        """Register a product class with the factory.
        
        Args:
            type_id: Identifier for the product class
            product_class: The product class to register
        """
        self._registry[type_id] = product_class
    
    def create(self, type_id: Optional[ID] = None, *args: Any, **kwargs: Any) -> T:
        """Create a product instance.
        
        Args:
            type_id: Identifier for the product class (uses default if not specified)
            *args: Positional arguments to pass to the product constructor
            **kwargs: Keyword arguments to pass to the product constructor
            
        Returns:
            An instance of the product class
            
        Raises:
            ValueError: If the product type is not registered
        """
        # Use default type if not specified
        if type_id is None:
            if self._default_type is None:
                raise ValueError("No type_id specified and no default type registered")
            type_id = self._default_type
            
        # Get the product class
        product_class = self._registry.get(type_id)
        if product_class is None:
            raise ValueError(f"Unknown product type: {type_id}")
            
        # Create and return the product
        return product_class(*args, **kwargs)
    
    def get_registered_types(self) -> List[ID]:
        """Get all registered product types.
        
        Returns:
            List of registered product type identifiers
        """
        return list(self._registry.keys())
    
    def is_registered(self, type_id: ID) -> bool:
        """Check if a product type is registered.
        
        Args:
            type_id: Identifier for the product class
            
        Returns:
            True if the product type is registered
        """
        return type_id in self._registry


class LazyFactory(Generic[ID, T]):
    """Factory that lazily initializes product classes.
    
    This factory variant allows registration of factory functions rather than
    classes, which are only called when needed. This is useful for avoiding
    circular imports and reducing startup time.
    """
    
    def __init__(self, default_type: Optional[ID] = None):
        """Initialize the lazy factory.
        
        Args:
            default_type: Optional default type to use if not specified
        """
        self._registry: Dict[ID, Callable[[], Type[T]]] = {}
        self._cache: Dict[ID, Type[T]] = {}
        self._default_type = default_type
    
    def register(self, type_id: ID, factory_func: Callable[[], Type[T]]) -> None:
        """Register a factory function with the factory.
        
        Args:
            type_id: Identifier for the product class
            factory_func: Function that returns the product class
        """
        self._registry[type_id] = factory_func
    
    def create(self, type_id: Optional[ID] = None, *args: Any, **kwargs: Any) -> T:
        """Create a product instance.
        
        Args:
            type_id: Identifier for the product class (uses default if not specified)
            *args: Positional arguments to pass to the product constructor
            **kwargs: Keyword arguments to pass to the product constructor
            
        Returns:
            An instance of the product class
            
        Raises:
            ValueError: If the product type is not registered
        """
        # Use default type if not specified
        if type_id is None:
            if self._default_type is None:
                raise ValueError("No type_id specified and no default type registered")
            type_id = self._default_type
            
        # Get or create the product class
        product_class = self._cache.get(type_id)
        if product_class is None:
            factory_func = self._registry.get(type_id)
            if factory_func is None:
                raise ValueError(f"Unknown product type: {type_id}")
                
            # Get the class and cache it
            product_class = factory_func()
            self._cache[type_id] = product_class
            
        # Create and return the product
        return product_class(*args, **kwargs)
    
    def get_registered_types(self) -> List[ID]:
        """Get all registered product types.
        
        Returns:
            List of registered product type identifiers
        """
        return list(self._registry.keys())
    
    def is_registered(self, type_id: ID) -> bool:
        """Check if a product type is registered.
        
        Args:
            type_id: Identifier for the product class
            
        Returns:
            True if the product type is registered
        """
        return type_id in self._registry


class SingletonFactory(Factory[ID, T]):
    """Factory that creates singleton instances.
    
    This factory variant ensures that only one instance of each product type
    is created, reusing it for subsequent requests.
    """
    
    def __init__(self, default_type: Optional[ID] = None):
        """Initialize the singleton factory.
        
        Args:
            default_type: Optional default type to use if not specified
        """
        super().__init__(default_type)
        self._instances: Dict[ID, T] = {}
    
    def create(self, type_id: Optional[ID] = None, *args: Any, **kwargs: Any) -> T:
        """Create or get a singleton product instance.
        
        Args:
            type_id: Identifier for the product class (uses default if not specified)
            *args: Positional arguments to pass to the product constructor
            **kwargs: Keyword arguments to pass to the product constructor
            
        Returns:
            An instance of the product class
            
        Raises:
            ValueError: If the product type is not registered
        """
        # Use default type if not specified
        if type_id is None:
            if self._default_type is None:
                raise ValueError("No type_id specified and no default type registered")
            type_id = self._default_type
            
        # Check if we already have an instance
        if type_id in self._instances:
            return self._instances[type_id]
            
        # Create a new instance
        instance = super().create(type_id, *args, **kwargs)
        self._instances[type_id] = instance
        return instance
    
    def clear_instance(self, type_id: ID) -> None:
        """Clear a singleton instance, forcing a new one to be created next time.
        
        Args:
            type_id: Identifier for the product class
        """
        if type_id in self._instances:
            del self._instances[type_id]
    
    def clear_all_instances(self) -> None:
        """Clear all singleton instances."""
        self._instances.clear()
