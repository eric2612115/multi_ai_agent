"""Message event handlers and API routes.

This module registers event handlers for message events and provides API routes
for message operations.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from common.auth import get_current_user, User
from services.event_bus import EventBus
from services.message_storage import MessageStorageService

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/messages", tags=["messages"])

async def register_message_handlers():
    """Register message event handlers."""
    logger.info("Registering message event handlers")
    
    # Get event bus
    event_bus = EventBus()
    
    # Get message storage service
    storage_service = MessageStorageService()
    
    # Register event handlers
    
    # Handler for new messages to ensure they're saved to the database
    @event_bus.on("message.created")
    async def handle_message_created(message_data):
        logger.debug(f"Handling message.created event: {message_data.get('id')}")
        try:
            # Ensure the message is saved in the database
            saved_id = await storage_service.save_message(
                conversation_id=message_data.get('conversation_id'),
                message=message_data
            )
            logger.debug(f"Message saved with ID: {saved_id}")
            
            # Emit message saved event
            await event_bus.emit("message.saved", {
                "id": saved_id,
                "conversation_id": message_data.get('conversation_id')
            })
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            # Emit error event
            await event_bus.emit("message.error", {
                "error": str(e),
                "message_id": message_data.get('id'),
                "conversation_id": message_data.get('conversation_id')
            })
    
    # Handler for message updates
    @event_bus.on("message.updated")
    async def handle_message_updated(message_data):
        logger.debug(f"Handling message.updated event: {message_data.get('id')}")
        try:
            # Update the message in the database
            updated = await storage_service.update_message(
                message_id=message_data.get('id'),
                update_data=message_data
            )
            
            if updated:
                logger.debug(f"Message updated: {message_data.get('id')}")
                # Emit message updated event
                await event_bus.emit("message.saved", {
                    "id": message_data.get('id'),
                    "conversation_id": message_data.get('conversation_id'),
                    "updated": True
                })
            else:
                logger.warning(f"Message not found for update: {message_data.get('id')}")
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            # Emit error event
            await event_bus.emit("message.error", {
                "error": str(e),
                "message_id": message_data.get('id'),
                "conversation_id": message_data.get('conversation_id')
            })
    
    logger.info("Message event handlers registered successfully")
    return storage_service

# API endpoints for additional message operations

@router.get("/status")
async def get_message_status():
    """Get message storage status."""
    try:
        storage_service = MessageStorageService()
        connected = await storage_service.mongo_provider.is_connected()
        
        return {
            "status": "connected" if connected else "disconnected",
            "timestamp": await storage_service.mongo_provider.get_current_time() if connected else None,
        }
    except Exception as e:
        logger.error(f"Error getting message storage status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message storage status"
        )

@router.get("/conversation/{conversation_id}")
async def get_conversation_messages(
    conversation_id: str = Path(..., description="The conversation ID"),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, description="Maximum number of messages to return"),
    skip: int = Query(0, description="Number of messages to skip")
):
    """Get messages for a conversation."""
    try:
        storage_service = MessageStorageService()
        
        # Ensure connection to MongoDB
        if not await storage_service.mongo_provider.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Message storage service is not connected"
            )
            
        # Get the messages
        messages = await storage_service.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
            skip=skip
        )
        
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages),
            "total": await storage_service.count_conversation_messages(conversation_id)
        }
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation messages: {str(e)}"
        )

@router.delete("/conversation/{conversation_id}")
async def delete_conversation_messages(
    conversation_id: str = Path(..., description="The conversation ID"),
    current_user: User = Depends(get_current_user)
):
    """Delete all messages for a conversation."""
    try:
        storage_service = MessageStorageService()
        
        # Ensure connection to MongoDB
        if not await storage_service.mongo_provider.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Message storage service is not connected"
            )
            
        # Delete the messages
        count = await storage_service.delete_conversation_messages(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "deleted_count": count
        }
    except Exception as e:
        logger.error(f"Error deleting conversation messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation messages: {str(e)}"
        )
