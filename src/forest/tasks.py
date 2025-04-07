"""Task handler for knowledge forest.

This module provides functionality for handling asynchronous tasks
related to knowledge extraction, placement, and graph updates.
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
from functools import wraps

from src.forest.extraction_service import KnowledgeExtractionService
from src.forest.placement import KnowledgePlacementService
from src.forest.graph import KnowledgeGraphManager
from src.forest.models import KnowledgeExtractionResult, PlacementDecision, GraphUpdateResult
from src.services.event_bus import EventBus
from src.services.task_queue import TaskQueue
from src.common.config import get_settings
from src.common.exceptions import TaskHandlerError

settings = get_settings()
logger = logging.getLogger(__name__)


class KnowledgeForestTaskHandler:
    """Task handler for processing knowledge forest operations asynchronously."""

    def __init__(self,
                 extraction_service: Optional[KnowledgeExtractionService] = None,
                 placement_service: Optional[KnowledgePlacementService] = None,
                 graph_manager: Optional[KnowledgeGraphManager] = None,
                 event_bus: Optional[EventBus] = None,
                 task_queue: Optional[TaskQueue] = None):
        """Initialize the task handler.
        
        Args:
            extraction_service: Optional knowledge extraction service.
            placement_service: Optional knowledge placement service.
            graph_manager: Optional knowledge graph manager.
            event_bus: Optional event bus for publishing events.
            task_queue: Optional task queue for managing async tasks.
        """
        self.extraction_service = extraction_service
        self.placement_service = placement_service
        self.graph_manager = graph_manager
        self.event_bus = event_bus
        self.task_queue = task_queue

        # Lazy initialize services if not provided
        try:
            if self.extraction_service is None:
                self.extraction_service = KnowledgeExtractionService()
        except Exception as e:
            logger.error(f"Failed to initialize extraction service: {str(e)}")
            self.extraction_service = None

        try:
            if self.placement_service is None:
                self.placement_service = KnowledgePlacementService()
        except Exception as e:
            logger.error(f"Failed to initialize placement service: {str(e)}")
            self.placement_service = None

        try:
            if self.graph_manager is None:
                self.graph_manager = KnowledgeGraphManager()
        except Exception as e:
            logger.error(f"Failed to initialize graph manager: {str(e)}")
            self.graph_manager = None

        # Initialize event bus if not provided
        if self.event_bus is None:
            self.event_bus = EventBus()

        # Initialize task queue if not provided
        if self.task_queue is None:
            self.task_queue = TaskQueue()

        # State tracking
        self._running_tasks = {}
        self._task_lock = asyncio.Lock()

        # Initialize the handler
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up event listeners for the task handler."""
        # Listen for message events that might trigger knowledge extraction
        self.event_bus.subscribe("message.created", self._handle_message_created)
        self.event_bus.subscribe("message.updated", self._handle_message_updated)

        # Listen for user feedback on knowledge nodes
        self.event_bus.subscribe("knowledge.feedback", self._handle_knowledge_feedback)

        # Listen for manual knowledge operations
        self.event_bus.subscribe("knowledge.extract_request", self._handle_extract_request)
        self.event_bus.subscribe("knowledge.update_request", self._handle_update_request)
        self.event_bus.subscribe("knowledge.delete_request", self._handle_delete_request)

    async def start(self) -> None:
        """Start the task handler."""
        logger.info("Starting Knowledge Forest Task Handler")
        await self.task_queue.start()

    async def stop(self) -> None:
        """Stop the task handler."""
        logger.info("Stopping Knowledge Forest Task Handler")
        await self.task_queue.stop()

        # Cancel any running tasks
        async with self._task_lock:
            for task_id, task in self._running_tasks.items():
                if not task.done():
                    task.cancel()

    async def process_message(self, message_data: Dict[str, Any]) -> str:
        """Process a message for knowledge extraction and graph updates.
        
        Args:
            message_data: The message data.
            
        Returns:
            Task ID for tracking.
            
        Raises:
            TaskHandlerError: If task creation fails.
        """
        try:
            # Check if essential services are available
            if not self.extraction_service:
                logger.warning("Knowledge extraction service is not available")
                return "no_extraction_service"
                
            if not self.placement_service:
                logger.warning("Knowledge placement service is not available")
                return "no_placement_service"
                
            if not self.graph_manager:
                logger.warning("Knowledge graph manager is not available")
                return "no_graph_manager"
                
            # Create a unique task ID
            task_id = f"knowledge_extraction_{datetime.utcnow().timestamp()}"

            # Add the task, make sure method will still work even if task_id is passed as kwarg
            task = await self.task_queue.add_task(
                self._execute_knowledge_pipeline,
                message_data=message_data,
                task_id=task_id
            )

            # Track the task
            async with self._task_lock:
                self._running_tasks[task_id] = task

            # Log and return the task ID
            logger.info(f"Scheduled knowledge processing task: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"Failed to create knowledge processing task: {str(e)}")
            raise TaskHandlerError(f"Failed to schedule knowledge processing: {str(e)}")

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task.
        
        Args:
            task_id: The task ID.
            
        Returns:
            Task status information.
            
        Raises:
            TaskHandlerError: If task status retrieval fails.
        """
        try:
            # Get the task if it exists
            task = self._running_tasks.get(task_id)

            if task is None:
                return {
                    "task_id": task_id,
                    "status": "not_found",
                    "message": "Task not found"
                }

            # Check if the task is done
            if task.done():
                # Check if it completed successfully or with an exception
                try:
                    result = task.result()
                    status = "completed"
                    message = "Task completed successfully"
                except asyncio.CancelledError:
                    status = "cancelled"
                    message = "Task was cancelled"
                    result = None
                except Exception as e:
                    status = "failed"
                    message = f"Task failed: {str(e)}"
                    result = None
            else:
                status = "running"
                message = "Task is still running"
                result = None

            # Return the status
            return {
                "task_id": task_id,
                "status": status,
                "message": message,
                "result": result
            }

        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            raise TaskHandlerError(f"Failed to get task status: {str(e)}")

    async def _execute_knowledge_pipeline(self, message_data: Dict[str, Any], task_id: str = None) -> Dict[str, Any]:
        """Execute the full knowledge pipeline.
        
        Args:
            message_data: The message data.
            task_id: The task ID (optional, will be passed by TaskQueue).
            
        Returns:
            Result of the pipeline execution.
        """
        try:
            # Extract necessary information from message data
            user_id = message_data.get("user_id")
            conversation_id = message_data.get("conversation_id")
            message_id = message_data.get("message_id")
            content = message_data.get("content", "")

            # Optional metadata
            metadata = message_data.get("metadata", {})

            # Extract knowledge
            logger.info(f"[{task_id}] Extracting knowledge from message")
            extraction_result = await self.extraction_service.extract_knowledge(
                content=content,
                user_id=user_id,
                metadata=metadata
            )

            # If no knowledge extracted, return early
            if not extraction_result or not extraction_result.is_valid():
                logger.info(f"[{task_id}] No valid knowledge extracted")

                # Publish event about no knowledge extracted
                await self.event_bus.publish(
                    "knowledge.extraction_complete",
                    {
                        "task_id": task_id,
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "status": "no_knowledge",
                        "extraction_result": None
                    }
                )

                return {
                    "status": "no_knowledge",
                    "task_id": task_id,
                    "message": "No valid knowledge extracted"
                }

            # Publish event about successful extraction
            await self.event_bus.publish(
                "knowledge.extraction_complete",
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "status": "extracted",
                    "extraction_result": extraction_result.dict()
                }
            )

            # Decide placement
            logger.info(f"[{task_id}] Deciding knowledge placement")
            placement_decision = await self.placement_service.decide_placement(
                extraction_result=extraction_result,
                user_id=user_id
            )

            # Publish event about placement decision
            await self.event_bus.publish(
                "knowledge.placement_decided",
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "status": "placement_decided",
                    "placement_decision": placement_decision.dict()
                }
            )

            # Update the graph
            logger.info(f"[{task_id}] Updating knowledge graph")
            update_result = await self.graph_manager.update_graph(
                extraction_result=extraction_result,
                placement_decision=placement_decision,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )

            # Publish event about graph update
            await self.event_bus.publish(
                "knowledge.graph_updated",
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "status": "graph_updated",
                    "update_result": update_result.dict()
                }
            )

            # Check for cross-links if we created a new node
            if update_result.nodes_created and len(update_result.nodes_created) > 0:
                logger.info(f"[{task_id}] Detecting cross-links")

                for node_id in update_result.nodes_created:
                    # Find potential cross-links
                    cross_links = await self.placement_service.detect_cross_links(
                        node_id=node_id,
                        user_id=user_id
                    )

                    # If cross-links found, publish event
                    if cross_links and len(cross_links) > 0:
                        await self.event_bus.publish(
                            "knowledge.cross_links_detected",
                            {
                                "task_id": task_id,
                                "user_id": user_id,
                                "node_id": node_id,
                                "cross_links": cross_links
                            }
                        )

            # Return successful result
            return {
                "status": "success",
                "task_id": task_id,
                "message": "Knowledge processing completed successfully",
                "extraction_result": extraction_result.dict(),
                "placement_decision": placement_decision.dict(),
                "update_result": update_result.dict()
            }

        except Exception as e:
            logger.error(f"[{task_id}] Knowledge pipeline failed: {str(e)}")

            # Publish event about pipeline failure
            await self.event_bus.publish(
                "knowledge.pipeline_failed",
                {
                    "task_id": task_id,
                    "user_id": message_data.get("user_id"),
                    "conversation_id": message_data.get("conversation_id"),
                    "message_id": message_data.get("message_id"),
                    "status": "failed",
                    "error": str(e)
                }
            )

            # Re-raise the exception to be caught by the task queue
            raise

    async def _handle_message_created(self, event_data: Dict[str, Any]) -> None:
        """Handle message created events.
        
        Args:
            event_data: The event data.
        """
        try:
            # Check if this is a user message and should be processed
            if event_data.get("message_type") == "user" and settings.knowledge_forest.enable_auto_classification:
                await self.process_message(event_data)
        except Exception as e:
            logger.error(f"Error handling message.created event: {str(e)}")

    async def _handle_message_updated(self, event_data: Dict[str, Any]) -> None:
        """Handle message updated events.
        
        Args:
            event_data: The event data.
        """
        try:
            # Check if this is a user message and should be processed
            if event_data.get("message_type") == "user" and settings.knowledge_forest.enable_auto_classification:
                await self.process_message(event_data)
        except Exception as e:
            logger.error(f"Error handling message.updated event: {str(e)}")

    async def _handle_knowledge_feedback(self, event_data: Dict[str, Any]) -> None:
        """Handle knowledge feedback events.
        
        Args:
            event_data: The event data.
        """
        try:
            # Extract the feedback data
            node_id = event_data.get("node_id")
            user_id = event_data.get("user_id")
            feedback_type = event_data.get("feedback_type")
            feedback_data = event_data.get("feedback_data", {})

            # Log the feedback
            logger.info(f"Received knowledge feedback: {feedback_type} for node {node_id}")

            # Handle different types of feedback
            if feedback_type == "correct":
                # User confirms the knowledge is correct, no action needed
                pass

            elif feedback_type == "incorrect":
                # User indicates the knowledge is incorrect
                # TODO: Implement correction logic
                pass

            elif feedback_type == "merge":
                # User suggests merging with another node
                target_node_id = feedback_data.get("target_node_id")
                if target_node_id:
                    # Schedule a merge task
                    await self.task_queue.add_task(
                        self._merge_nodes,
                        source_node_id=node_id,
                        target_node_id=target_node_id,
                        user_id=user_id
                    )

            elif feedback_type == "split":
                # User suggests splitting a node
                split_info = feedback_data.get("split_info", {})
                if split_info:
                    # Schedule a split task
                    await self.task_queue.add_task(
                        self._split_node,
                        node_id=node_id,
                        split_info=split_info,
                        user_id=user_id
                    )

            elif feedback_type == "delete":
                # User wants to delete a node
                # Schedule a delete task
                await self.task_queue.add_task(
                    self._delete_node,
                    node_id=node_id,
                    user_id=user_id
                )

        except Exception as e:
            logger.error(f"Error handling knowledge.feedback event: {str(e)}")

    async def _handle_extract_request(self, event_data: Dict[str, Any]) -> None:
        """Handle manual knowledge extraction requests.
        
        Args:
            event_data: The event data.
        """
        try:
            # Process as a regular message
            await self.process_message(event_data)
        except Exception as e:
            logger.error(f"Error handling knowledge.extract_request event: {str(e)}")

    async def _handle_update_request(self, event_data: Dict[str, Any]) -> None:
        """Handle manual knowledge update requests.
        
        Args:
            event_data: The event data.
        """
        try:
            # Extract the necessary data
            node_id = event_data.get("node_id")
            user_id = event_data.get("user_id")
            update_data = event_data.get("update_data", {})

            # Schedule an update task
            await self.task_queue.add_task(
                self._update_node,
                node_id=node_id,
                update_data=update_data,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error handling knowledge.update_request event: {str(e)}")

    async def _handle_delete_request(self, event_data: Dict[str, Any]) -> None:
        """Handle manual knowledge deletion requests.
        
        Args:
            event_data: The event data.
        """
        try:
            # Extract the necessary data
            node_id = event_data.get("node_id")
            user_id = event_data.get("user_id")

            # Schedule a delete task
            await self.task_queue.add_task(
                self._delete_node,
                node_id=node_id,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error handling knowledge.delete_request event: {str(e)}")

    async def _merge_nodes(self, source_node_id: str, target_node_id: str, user_id: str) -> None:
        """Merge two nodes.
        
        Args:
            source_node_id: The source node ID.
            target_node_id: The target node ID.
            user_id: The user ID.
        """
        try:
            # TODO: Implement node merging logic
            # This should combine the information from both nodes
            # and update all edges to point to the merged node

            # For now, just log that this would be implemented
            logger.info(f"Would merge node {source_node_id} into {target_node_id} for user {user_id}")

            # Publish event about merger
            await self.event_bus.publish(
                "knowledge.nodes_merged",
                {
                    "user_id": user_id,
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "status": "merged"
                }
            )
        except Exception as e:
            logger.error(f"Failed to merge nodes: {str(e)}")

            # Publish event about merger failure
            await self.event_bus.publish(
                "knowledge.merge_failed",
                {
                    "user_id": user_id,
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "status": "failed",
                    "error": str(e)
                }
            )

    async def _split_node(self, node_id: str, split_info: Dict[str, Any], user_id: str) -> None:
        """Split a node into multiple nodes.
        
        Args:
            node_id: The node ID to split.
            split_info: Information about how to split the node.
            user_id: The user ID.
        """
        try:
            # TODO: Implement node splitting logic
            # This should create new nodes based on the split information
            # and update edges accordingly

            # For now, just log that this would be implemented
            logger.info(f"Would split node {node_id} for user {user_id} with info: {split_info}")

            # Publish event about split
            await self.event_bus.publish(
                "knowledge.node_split",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "split",
                    "split_info": split_info
                }
            )
        except Exception as e:
            logger.error(f"Failed to split node: {str(e)}")

            # Publish event about split failure
            await self.event_bus.publish(
                "knowledge.split_failed",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "failed",
                    "error": str(e)
                }
            )

    async def _delete_node(self, node_id: str, user_id: str) -> None:
        """Delete a node.
        
        Args:
            node_id: The node ID to delete.
            user_id: The user ID.
        """
        try:
            # TODO: Implement node deletion logic
            # This should delete the node and all its edges

            # For now, just log that this would be implemented
            logger.info(f"Would delete node {node_id} for user {user_id}")

            # Publish event about deletion
            await self.event_bus.publish(
                "knowledge.node_deleted",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "deleted"
                }
            )
        except Exception as e:
            logger.error(f"Failed to delete node: {str(e)}")

            # Publish event about deletion failure
            await self.event_bus.publish(
                "knowledge.delete_failed",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "failed",
                    "error": str(e)
                }
            )

    async def _update_node(self, node_id: str, update_data: Dict[str, Any], user_id: str) -> None:
        """Update a node.
        
        Args:
            node_id: The node ID to update.
            update_data: The data to update.
            user_id: The user ID.
        """
        try:
            # TODO: Implement node update logic
            # This should update the node with the new data

            # For now, just log that this would be implemented
            logger.info(f"Would update node {node_id} for user {user_id} with data: {update_data}")

            # Publish event about update
            await self.event_bus.publish(
                "knowledge.node_updated",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "updated",
                    "update_data": update_data
                }
            )
        except Exception as e:
            logger.error(f"Failed to update node: {str(e)}")

            # Publish event about update failure
            await self.event_bus.publish(
                "knowledge.update_failed",
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "status": "failed",
                    "error": str(e)
                }
            )
