"""REST API for conversations.

This module provides REST API endpoints for retrieving and managing conversations.
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from pydantic import BaseModel, Field
from datetime import datetime

from src.common.auth import get_current_user, User
from src.common.config import get_settings
from src.services.message_storage import MessageStorageService

# Setup logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create router
router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Models
class Message(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    message_type: str
    content: str
    timestamp: str
    
    class Config:
        json_schema_extra: dict[str, dict[str, str]] = {
            "example": {
                "id": "12345",
                "conversation_id": "67890",
                "user_id": "user123",
                "message_type": "user",
                "content": "Hello, how can you help me?",
                "timestamp": "2025-01-01T12:00:00Z"
            }
        }

class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    tags: List[str] = Field(default_factory=list)
    summary: str = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "67890",
                "user_id": "user123",
                "title": "How to setup MongoDB",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-01T12:30:00Z",
                "message_count": 10,
                "tags": ["mongodb", "database", "setup"],
                "summary": "Discussion about MongoDB setup and configuration",
                "metadata": {"priority": "high"}
            }
        }

class ConversationList(BaseModel):
    conversations: List[Conversation]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversations": [
                    {
                        "id": "67890",
                        "user_id": "user123",
                        "title": "How to setup MongoDB",
                        "created_at": "2025-01-01T12:00:00Z",
                        "updated_at": "2025-01-01T12:30:00Z",
                        "message_count": 10
                    }
                ],
                "total": 1
            }
        }

class MessageList(BaseModel):
    messages: List[Message]
    conversation_id: str
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "id": "12345",
                        "conversation_id": "67890",
                        "user_id": "user123",
                        "message_type": "user",
                        "content": "Hello, how can you help me?",
                        "timestamp": "2025-01-01T12:00:00Z"
                    }
                ],
                "conversation_id": "67890",
                "total": 1
            }
        }

# Endpoints
@router.get("/", response_model=ConversationList)
async def get_conversations(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Get all conversations for the current user.
    
    Args:
        limit: Maximum number of conversations to return.
        skip: Number of conversations to skip.
        current_user: The current authenticated user.
        
    Returns:
        A list of conversations.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Get conversations
        conversations = await storage_service.get_user_conversations(
            user_id=current_user.id,
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

@router.get("/{conversation_id}", response_model=MessageList)
async def get_conversation_messages(
    conversation_id: str = Path(..., title="Conversation ID"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Get all messages for a conversation.
    
    Args:
        conversation_id: The conversation ID.
        limit: Maximum number of messages to return.
        skip: Number of messages to skip.
        current_user: The current authenticated user.
        
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
        
        if not conversation or conversation.get("user_id") != current_user.id:
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
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving conversation messages."
        )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str = Path(..., title="Conversation ID"),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation and all its messages.
    
    Args:
        conversation_id: The conversation ID.
        current_user: The current authenticated user.
        
    Returns:
        204 No Content on success.
    """
    try:
        # Get the storage service
        storage_service = MessageStorageService()
        
        # Delete the conversation
        success = await storage_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or you don't have permission to delete it."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the conversation."
        )
