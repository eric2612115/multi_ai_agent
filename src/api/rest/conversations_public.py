"""Public REST API for conversations.

This module provides public REST API endpoints for retrieving and managing conversations without authentication.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path, Body, status
from pydantic import BaseModel, Field
from datetime import datetime

from src.services.message_storage import MessageStorageService

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/public/conversations", tags=["public-conversations"])

# Models
class Message(BaseModel):
    content: str = Field(..., description="Message content")
    message_type: str = Field("user", description="Message type (user or assistant)")
    timestamp: Optional[str] = Field(None, description="Message timestamp (ISO format)")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

class CreateConversationRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    first_message: Optional[str] = Field(None, description="First message content")

class CreateMessageRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    content: str = Field(..., description="Message content")
    message_type: str = Field("user", description="Message type (user or assistant)")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

# Endpoints
@router.post("/", response_model=Dict[str, Any])
async def create_conversation(
    request: CreateConversationRequest = Body(...)
):
    """Create a new conversation.
    
    Args:
        request: The conversation creation request.
        
    Returns:
        The created conversation.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Generate IDs
        conversation_id = str(uuid.uuid4())
        
        # Create conversation
        conversation = {
            "_id": conversation_id,
            "user_id": request.user_id,
            "title": request.title or "New Conversation",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "message_count": 0
        }
        
        # Save conversation
        await storage_service.mongo_provider.save_document(
            collection="conversations",
            document=conversation
        )
        
        # Add first message if provided
        if request.first_message:
            message_id = str(uuid.uuid4())
            message = {
                "_id": message_id,
                "conversation_id": conversation_id,
                "user_id": request.user_id,
                "message_type": "user",
                "content": request.first_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Save message
            await storage_service.mongo_provider.save_document(
                collection="messages",
                document=message
            )
            
            # Update message count
            await storage_service.mongo_provider.update_document(
                collection="conversations",
                document_id=conversation_id,
                update_data={"message_count": 1}
            )
            
            conversation["message_count"] = 1
        
        # Return conversation
        return {
            "id": conversation_id,
            "user_id": request.user_id,
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "message_count": conversation["message_count"]
        }
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the conversation."
        )

@router.get("/user/{user_id}", response_model=Dict[str, Any])
async def get_user_conversations(
    user_id: str = Path(..., description="User ID"),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get all conversations for a user.
    
    Args:
        user_id: The user ID.
        limit: Maximum number of conversations to return.
        skip: Number of conversations to skip.
        
    Returns:
        A list of conversations.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Get conversations
        conversations = await storage_service.get_user_conversations(
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        
        # Get total count
        total = len(conversations)  # This is approximate since we're limiting the query
        
        # Format the response
        return {
            "conversations": conversations,
            "total": total
        }
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving conversations."
        )

@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation_messages(
    conversation_id: str = Path(..., description="Conversation ID"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get all messages for a conversation.
    
    Args:
        conversation_id: The conversation ID.
        user_id: The user ID.
        limit: Maximum number of messages to return.
        skip: Number of messages to skip.
        
    Returns:
        A list of messages.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Verify the conversation belongs to the user
        conversation = await storage_service.mongo_provider.get_document(
            collection="conversations",
            document_id=conversation_id
        )
        
        if not conversation or conversation.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or you don't have permission to access it."
            )
        
        # Get messages
        messages = await storage_service.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
            skip=skip
        )
        
        # Get total count
        total = conversation.get("message_count", 0)
        
        # Format the response
        return {
            "messages": messages,
            "conversation_id": conversation_id,
            "total": total
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving conversation messages."
        )

@router.post("/{conversation_id}/messages", response_model=Dict[str, Any])
async def create_conversation_message(
    conversation_id: str = Path(..., description="Conversation ID"),
    request: CreateMessageRequest = Body(...)
):
    """Create a new message in a conversation.
    
    Args:
        conversation_id: The conversation ID.
        request: The message creation request.
        
    Returns:
        The created message.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Verify the conversation belongs to the user
        conversation = await storage_service.mongo_provider.get_document(
            collection="conversations",
            document_id=conversation_id
        )
        
        if not conversation or conversation.get("user_id") != request.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or you don't have permission to access it."
            )
        
        # Generate ID
        message_id = str(uuid.uuid4())
        
        # Create message
        message = {
            "id": message_id,
            "conversation_id": conversation_id,
            "user_id": request.user_id,
            "message_type": request.message_type,
            "content": request.content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": request.metadata
        }
        
        # Save message
        await storage_service.save_message(conversation_id, message)
        
        # Publish message created event
        event_bus = storage_service.event_bus
        await event_bus.publish("message.created", {
            "user_id": request.user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "message_type": request.message_type,
            "content": request.content,
            "timestamp": message["timestamp"]
        })
        
        # Return message
        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "user_id": request.user_id,
            "message_type": request.message_type,
            "content": request.content,
            "timestamp": message["timestamp"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the message."
        )
