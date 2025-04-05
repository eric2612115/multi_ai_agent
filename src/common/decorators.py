"""Decorators for common patterns in the AI Knowledge Forest.

This module provides decorators that can be applied to methods to handle
common patterns like error handling, energy tracking, and logging.
"""
import functools
import logging
import time
import traceback
from typing import Callable, Any, Optional, Type, TypeVar, cast, Dict, Union
import asyncio

from common.exceptions import BaseError

logger = logging.getLogger(__name__)

# Generic return type
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


def handle_errors(error_class: Type[BaseError] = BaseError) -> Callable[[F], F]:
    """Decorator for handling errors in a method.
    
    Args:
        error_class: Exception class to raise if an error occurs
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except error_class as e:
                # Re-raise errors of the same class
                raise
            except Exception as e:
                # Capture the full traceback
                tb = traceback.format_exc()
                logger.error(f"Error in {func.__name__}: {str(e)}\n{tb}")
                # Create a new exception of the specified class
                raise error_class(f"Error in {func.__name__}: {str(e)}")
                
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except error_class as e:
                # Re-raise errors of the same class
                raise
            except Exception as e:
                # Capture the full traceback
                tb = traceback.format_exc()
                logger.error(f"Error in {func.__name__}: {str(e)}\n{tb}")
                # Create a new exception of the specified class
                raise error_class(f"Error in {func.__name__}: {str(e)}")
                
        # Choose the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
            
    return decorator


def track_energy(amount: float = 1.0) -> Callable[[F], F]:
    """Decorator for tracking energy consumption of a method.
    
    Args:
        amount: Amount of energy to track for each call
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # Check if the class has a track_energy method
            if hasattr(self, 'track_energy') and callable(self.track_energy):
                self.track_energy(amount)
            return await func(self, *args, **kwargs)
                
        @functools.wraps(func)
        def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # Check if the class has a track_energy method
            if hasattr(self, 'track_energy') and callable(self.track_energy):
                self.track_energy(amount)
            return func(self, *args, **kwargs)
                
        # Choose the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
            
    return decorator


def log_operation(operation: Optional[str] = None) -> Callable[[F], F]:
    """Decorator for logging operations to both log file and database.
    
    Args:
        operation: Name of the operation (defaults to function name)
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # Determine operation name
            op_name = operation or func.__name__
            
            # Extract user_id from arguments if present
            user_id = kwargs.get('user_id')
            if user_id is None and args:
                # Check if the first argument might be a user_id
                if isinstance(args[0], str):
                    user_id = args[0]
            
            # Prepare details from kwargs (excluding user_id if present)
            details = {k: v for k, v in kwargs.items() if k != 'user_id' and not isinstance(v, (dict, list))}
            
            # Log the start of the operation
            logger.info(f"Starting operation: {op_name}")
            start_time = time.time()
            
            success = True
            result = None
            try:
                # Call the original function
                result = await func(self, *args, **kwargs)
                return result
            except Exception as e:
                success = False
                logger.error(f"Operation failed: {op_name} - {str(e)}")
                raise
            finally:
                # Calculate duration
                duration = time.time() - start_time
                
                # Add duration to details
                details['duration'] = duration
                
                # Include result status in details
                if isinstance(result, bool):
                    details['result_success'] = result
                
                # Log to database if the class has a log_operation method
                if hasattr(self, 'log_operation') and callable(self.log_operation):
                    try:
                        await self.log_operation(
                            operation=op_name,
                            user_id=user_id,
                            details=details,
                            success=success
                        )
                    except Exception as log_error:
                        logger.error(f"Failed to log operation to database: {str(log_error)}")
                
                # Log completion to logger
                if success:
                    logger.info(f"Completed operation: {op_name} in {duration:.2f}s")
                
        @functools.wraps(func)
        def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # For synchronous functions, we need to handle differently
            # as we can't await self.log_operation
            
            # Determine operation name
            op_name = operation or func.__name__
            
            # Log the start of the operation
            logger.info(f"Starting operation: {op_name}")
            start_time = time.time()
            
            success = True
            result = None
            try:
                # Call the original function
                result = func(self, *args, **kwargs)
                return result
            except Exception as e:
                success = False
                logger.error(f"Operation failed: {op_name} - {str(e)}")
                raise
            finally:
                # Calculate duration
                duration = time.time() - start_time
                
                # Log completion to logger
                if success:
                    logger.info(f"Completed operation: {op_name} in {duration:.2f}s")
                
        # Choose the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
            
    return decorator


def retry(attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Type[Exception] = Exception) -> Callable[[F], F]:
    """Decorator for retrying operations that might fail.
    
    Args:
        attempts: Maximum number of attempts
        delay: Initial delay between attempts in seconds
        backoff: Multiplier for delay after each attempt
        exceptions: Exception types to catch and retry
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts - 1:  # Don't sleep after the last attempt
                        logger.warning(f"Attempt {attempt + 1}/{attempts} failed for {func.__name__}: {str(e)}")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {attempts} attempts failed for {func.__name__}")
            
            # If we get here, all attempts failed
            raise last_exception
                
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts - 1:  # Don't sleep after the last attempt
                        logger.warning(f"Attempt {attempt + 1}/{attempts} failed for {func.__name__}: {str(e)}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {attempts} attempts failed for {func.__name__}")
            
            # If we get here, all attempts failed
            raise last_exception
                
        # Choose the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
            
    return decorator


def cache_result(ttl: float = 60.0) -> Callable[[F], F]:
    """Decorator for caching results of expensive operations.
    
    Args:
        ttl: Time-to-live for cached results in seconds
        
    Returns:
        Decorated function
    """
    cache: Dict[str, Dict[str, Union[Any, float]]] = {}
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create a key from the function name and arguments
            key = f"{func.__name__}:{args}:{kwargs}"
            
            # Check if the result is in the cache and not expired
            if key in cache:
                entry = cache[key]
                expiration = cast(float, entry["expiration"])
                if time.time() < expiration:
                    return entry["result"]
            
            # Not in cache or expired, call the function
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache[key] = {
                "result": result,
                "expiration": time.time() + ttl
            }
            
            return result
                
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create a key from the function name and arguments
            key = f"{func.__name__}:{args}:{kwargs}"
            
            # Check if the result is in the cache and not expired
            if key in cache:
                entry = cache[key]
                expiration = cast(float, entry["expiration"])
                if time.time() < expiration:
                    return entry["result"]
            
            # Not in cache or expired, call the function
            result = func(*args, **kwargs)
            
            # Cache the result
            cache[key] = {
                "result": result,
                "expiration": time.time() + ttl
            }
            
            return result
                
        # Choose the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
            
    return decorator
