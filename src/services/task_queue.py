"""Task queue service.

This module provides a task queue for managing asynchronous tasks.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple
import uuid
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskQueue:
    """Task queue for managing asynchronous tasks.
    
    This class provides functionality for scheduling, executing, and tracking
    asynchronous tasks.
    """
    
    _instance = None
    
    def __new__(cls):
        """Create a new instance of TaskQueue or return the existing one (singleton)."""
        if cls._instance is None:
            cls._instance = super(TaskQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the task queue."""
        if self._initialized:
            return
            
        self._tasks = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._max_concurrent_tasks = 10
        self._semaphore = asyncio.Semaphore(self._max_concurrent_tasks)
        self._initialized = True
        
        logger.info("Task queue initialized")
    
    async def start(self) -> None:
        """Start the task queue."""
        async with self._lock:
            self._running = True
        logger.info("Task queue started")
    
    async def stop(self) -> None:
        """Stop the task queue."""
        async with self._lock:
            self._running = False
            
            # Cancel all running tasks
            for task_id, task_info in self._tasks.items():
                task = task_info.get("task")
                if task and not task.done():
                    logger.info(f"Cancelling task {task_id}")
                    task.cancel()
                    
        logger.info("Task queue stopped")
    
    async def add_task(self, func: Callable, *args, **kwargs) -> asyncio.Task:
        """Add a task to the queue.
        
        Args:
            func: The async function to execute.
            *args: Arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            The asyncio Task object.
            
        Raises:
            RuntimeError: If the task queue is not running.
        """
        async with self._lock:
            if not self._running:
                raise RuntimeError("Task queue is not running")
                
            # Generate a task ID if not provided
            task_id = kwargs.pop("task_id", str(uuid.uuid4()))
            
            # Create a wrapper function that acquires and releases the semaphore
            async def task_wrapper():
                async with self._semaphore:
                    try:
                        # Update task status
                        self._tasks[task_id]["status"] = "running"
                        self._tasks[task_id]["started_at"] = datetime.utcnow()
                        
                        # Execute the task
                        result = await func(*args, **kwargs)
                        
                        # Update task status
                        self._tasks[task_id]["status"] = "completed"
                        self._tasks[task_id]["completed_at"] = datetime.utcnow()
                        self._tasks[task_id]["result"] = result
                        
                        return result
                    except asyncio.CancelledError:
                        # Update task status
                        self._tasks[task_id]["status"] = "cancelled"
                        self._tasks[task_id]["completed_at"] = datetime.utcnow()
                        raise
                    except Exception as e:
                        # Update task status
                        self._tasks[task_id]["status"] = "failed"
                        self._tasks[task_id]["completed_at"] = datetime.utcnow()
                        self._tasks[task_id]["error"] = str(e)
                        
                        # Log the error
                        logger.error(f"Task {task_id} failed: {str(e)}")
                        raise
            
            # Create the task
            try:
                # Attempt to create the task with proper parameters
                task = asyncio.create_task(task_wrapper())
            except TypeError as e:
                # Handle missing arguments error
                logger.error(f"Invalid arguments for task {task_id}: {str(e)}")
                # Try to fix missing parameters if possible
                if str(e).find("missing 1 required positional argument: 'task_id'") != -1:
                    # The task requires a task_id parameter but it wasn't passed
                    logger.info(f"Attempting to fix missing task_id parameter for task {task_id}")
                    kwargs["task_id"] = task_id
                    # Create a new wrapper with fixed arguments
                    async def fixed_task_wrapper():
                        async with self._semaphore:
                            try:
                                self._tasks[task_id]["status"] = "running"
                                self._tasks[task_id]["started_at"] = datetime.utcnow()
                                result = await func(*args, **kwargs)
                                self._tasks[task_id]["status"] = "completed"
                                self._tasks[task_id]["completed_at"] = datetime.utcnow()
                                self._tasks[task_id]["result"] = result
                                return result
                            except Exception as e:
                                self._tasks[task_id]["status"] = "failed"
                                self._tasks[task_id]["completed_at"] = datetime.utcnow()
                                self._tasks[task_id]["error"] = str(e)
                                logger.error(f"Task {task_id} failed: {str(e)}")
                                raise
                    task = asyncio.create_task(fixed_task_wrapper())
                else:
                    # Can't fix the issue, raise the original error
                    raise
            
            # Store task info
            self._tasks[task_id] = {
                "task": task,
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None
            }
            
            logger.info(f"Added task {task_id} to queue")
            return task
    
    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a task.
        
        Args:
            task_id: The task ID.
            
        Returns:
            Task information, or None if the task is not found.
        """
        async with self._lock:
            task_info = self._tasks.get(task_id)
            
            if task_info:
                # Create a copy without the task object
                result = {k: v for k, v in task_info.items() if k != "task"}
                
                # Add task status
                task = task_info.get("task")
                if task:
                    if task.done():
                        if task.cancelled():
                            result["status"] = "cancelled"
                        elif task.exception():
                            result["status"] = "failed"
                            result["error"] = str(task.exception())
                        else:
                            result["status"] = "completed"
                    else:
                        result["status"] = "running"
                
                return result
            
            return None
    
    async def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get information about all tasks.
        
        Args:
            status: Optional status filter.
            
        Returns:
            List of task information.
        """
        async with self._lock:
            result = []
            
            for task_id, task_info in self._tasks.items():
                # Create a copy without the task object
                info = {k: v for k, v in task_info.items() if k != "task"}
                
                # Add task status
                task = task_info.get("task")
                if task:
                    if task.done():
                        if task.cancelled():
                            info["status"] = "cancelled"
                        elif task.exception():
                            info["status"] = "failed"
                            info["error"] = str(task.exception())
                        else:
                            info["status"] = "completed"
                    else:
                        info["status"] = "running"
                
                # Apply status filter
                if status is None or info["status"] == status:
                    # Add task ID
                    info["task_id"] = task_id
                    result.append(info)
            
            return result
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.
        
        Args:
            task_id: The task ID.
            
        Returns:
            True if the task was cancelled, False otherwise.
        """
        async with self._lock:
            task_info = self._tasks.get(task_id)
            
            if not task_info:
                return False
                
            task = task_info.get("task")
            
            if task and not task.done():
                task.cancel()
                logger.info(f"Cancelled task {task_id}")
                return True
            
            return False
    
    async def clear_completed_tasks(self, max_age_seconds: int = 3600) -> int:
        """Clear completed, cancelled, or failed tasks from the queue.
        
        Args:
            max_age_seconds: Maximum age in seconds for completed tasks to keep.
            
        Returns:
            Number of tasks cleared.
        """
        async with self._lock:
            now = time.time()
            to_remove = []
            
            for task_id, task_info in self._tasks.items():
                task = task_info.get("task")
                
                if task and task.done():
                    completed_at = task_info.get("completed_at")
                    
                    if completed_at:
                        age = now - completed_at.timestamp()
                        
                        if age > max_age_seconds:
                            to_remove.append(task_id)
            
            # Remove tasks
            for task_id in to_remove:
                del self._tasks[task_id]
                
            logger.info(f"Cleared {len(to_remove)} completed tasks")
            return len(to_remove)
