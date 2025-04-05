"""Message storage service.

This module provides a service for storing and retrieving chat messages.
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

from services.event_bus import EventBus
from storage.mongodb import MongoDBProvider

logger = logging.getLogger(__name__)

class MessageStorageService:
    """Service for storing and retrieving chat messages."""
    
    _instance = None
    
    def __new__(cls):
        """Create a new instance of MessageStorageService or return the existing one (singleton)."""
        if cls._instance is None:
            cls._instance = super(MessageStorageService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the message storage service."""
        if self._initialized:
            return
            
        self.mongo_provider = MongoDBProvider()
        self.event_bus = EventBus()
        self._initialized = True
        self._is_listening = False
        
        logger.info("Message storage service initialized")
    
    async def start(self) -> None:
        """Start the message storage service."""
        # Check if MongoDB is connected
        if not await self.mongo_provider.is_connected():
            try:
                await self.mongo_provider.connect()
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {str(e)}")
                return
        
        # Create indexes
        try:
            # Index for user_id and conversation_id for faster lookups
            await self.mongo_provider.create_index(
                collection="conversations",
                keys={"user_id": 1},
                unique=False
            )
            
            await self.mongo_provider.create_index(
                collection="messages",
                keys={"conversation_id": 1, "timestamp": 1},
                unique=False
            )
            
            await self.mongo_provider.create_index(
                collection="messages",
                keys={"user_id": 1, "timestamp": -1},
                unique=False
            )
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
        
        # Subscribe to message events if not already listening
        if not self._is_listening:
            self.event_bus.subscribe("message.created", self._handle_message_created)
            self._is_listening = True
            logger.info("Started listening for message events")
    
    async def stop(self) -> None:
        """Stop the message storage service."""
        # Unsubscribe from events
        if self._is_listening:
            self.event_bus.unsubscribe("message.created", self._handle_message_created)
            self._is_listening = False
        
        # Close MongoDB connection
        if await self.mongo_provider.is_connected():
            await self.mongo_provider.close()
    
    async def _handle_message_created(self, event_data: Dict[str, Any]) -> None:
        """Handle message.created event.
        
        Args:
            event_data: Event data containing message details.
        """
        try:
            # Extract relevant information
            user_id = event_data.get("user_id")
            conversation_id = event_data.get("conversation_id")
            message_id = event_data.get("message_id")
            message_type = event_data.get("message_type")
            content = event_data.get("content")
            timestamp = event_data.get("timestamp")
            
            # Ensure all required fields are present
            if not all([user_id, conversation_id, message_id, message_type, content]):
                logger.error(f"Missing required fields in message event: {event_data}")
                return
            
            # Check if conversation exists
            conversation = await self.mongo_provider.get_document(
                collection="conversations",
                document_id=conversation_id
            )
            
            # Create conversation if it doesn't exist
            if not conversation:
                conversation = {
                    "_id": conversation_id,
                    "user_id": user_id,
                    "title": self._generate_conversation_title(content[:100]),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "message_count": 0
                }
                
                await self.mongo_provider.save_document(
                    collection="conversations",
                    document=conversation
                )
                logger.debug(f"Created new conversation: {conversation_id}")
            
            # Update conversation last updated time
            await self.mongo_provider.update_document(
                collection="conversations",
                document_id=conversation_id,
                update_data={
                    "updated_at": timestamp,
                    "message_count": (conversation.get("message_count", 0) + 1)
                }
            )
            
            # If this is an assistant message and we have enough context, generate summary and tags
            if message_type == "assistant" and conversation.get("message_count", 0) >= 3:
                asyncio.create_task(self._update_conversation_summary_and_tags(conversation_id))
            
            # Save message
            message = {
                "_id": message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "message_type": message_type,
                "content": content,
                "timestamp": timestamp
            }
            
            await self.mongo_provider.save_document(
                collection="messages",
                document=message
            )
            
            logger.debug(f"Saved message {message_id} to conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error handling message event: {str(e)}")
    
    def _generate_conversation_title(self, first_message: str) -> str:
        """Generate a title for a conversation based on the first message.
        
        Args:
            first_message: The first message in the conversation.
            
        Returns:
            A generated title.
        """
        # Simple implementation: use first few words or characters
        if len(first_message) <= 30:
            return first_message
        
        # Try to find a sentence break
        sentence_break = first_message.find(". ")
        if 10 <= sentence_break <= 50:
            return first_message[:sentence_break+1]
        
        # Fallback: just use the first 30 characters
        return first_message[:30] + "..."
    
    async def get_user_conversations(self, user_id: str, limit: int = 10, skip: int = 0) -> List[Dict[str, Any]]:
        """Get conversations for a user.
        
        Args:
            user_id: The user ID.
            limit: Maximum number of conversations to return.
            skip: Number of conversations to skip.
            
        Returns:
            List of conversation objects.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Query conversations for the user
            conversations = await self.mongo_provider.find_documents(
                collection="conversations",
                query={"user_id": user_id},
                sort={"updated_at": -1},  # Sort by most recent first
                limit=limit,
                skip=skip
            )
            
            return conversations
        except Exception as e:
            logger.error(f"Error getting user conversations: {str(e)}")
            return []
    
    async def get_conversation_messages(self, conversation_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a conversation.
        
        Args:
            conversation_id: The conversation ID.
            limit: Maximum number of messages to return.
            skip: Number of messages to skip.
            
        Returns:
            List of message objects.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Query messages for the conversation
            messages = await self.mongo_provider.find_documents(
                collection="messages",
                query={"conversation_id": conversation_id},
                sort={"timestamp": 1},  # Sort by oldest first
                limit=limit,
                skip=skip
            )
            
            return messages
        except Exception as e:
            logger.error(f"Error getting conversation messages: {str(e)}")
            return []

    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation and all its messages.
        
        Args:
            conversation_id: The conversation ID.
            user_id: The user ID (for security validation).
            
        Returns:
            True if deleted successfully.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Verify the conversation belongs to the user
            conversation = await self.mongo_provider.get_document(
                collection="conversations",
                document_id=conversation_id
            )
            
            if not conversation or conversation.get("user_id") != user_id:
                logger.warning(f"Attempted to delete conversation that doesn't belong to user: {user_id}")
                return False
            
            # Delete all messages in the conversation
            # Note: In a production system, this might be better handled as a background task
            # or with a bulk delete operation
            messages = await self.mongo_provider.find_documents(
                collection="messages",
                query={"conversation_id": conversation_id}
            )
            
            for message in messages:
                await self.mongo_provider.delete_document(
                    collection="messages",
                    document_id=message["_id"]
                )
            
            # Delete the conversation
            await self.mongo_provider.delete_document(
                collection="conversations",
                document_id=conversation_id
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            return False
    
    async def save_message(self, conversation_id: str, message: Dict[str, Any]) -> str:
        """Save a message to the database.
        
        Args:
            conversation_id: The conversation ID.
            message: The message data.
            
        Returns:
            The message ID.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Check if conversation exists
            conversation = await self.mongo_provider.get_document(
                collection="conversations",
                document_id=conversation_id
            )
            
            timestamp = message.get('timestamp') or datetime.utcnow().isoformat()
            
            # Create conversation if it doesn't exist
            if not conversation:
                conversation = {
                    "_id": conversation_id,
                    "user_id": message.get('user_id'),
                    "title": self._generate_conversation_title(message.get('content', '')[:100]),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "message_count": 0
                }
                
                await self.mongo_provider.save_document(
                    collection="conversations",
                    document=conversation
                )
                logger.debug(f"Created new conversation: {conversation_id}")
            
            # Update conversation last updated time
            await self.mongo_provider.update_document(
                collection="conversations",
                document_id=conversation_id,
                update_data={
                    "updated_at": timestamp,
                    "message_count": (conversation.get("message_count", 0) + 1)
                }
            )
            
            # If this is an assistant message and we have enough context, generate summary and tags
            if message.get('message_type') == "assistant" and conversation.get("message_count", 0) >= 3:
                asyncio.create_task(self._update_conversation_summary_and_tags(conversation_id))
            
            # Prepare message document
            message_doc = {
                "_id": message.get('id'),
                "conversation_id": conversation_id,
                "user_id": message.get('user_id'),
                "message_type": message.get('message_type', 'text'),
                "content": message.get('content'),
                "timestamp": timestamp,
                "metadata": message.get('metadata', {})
            }
            
            # Save message
            message_id = await self.mongo_provider.save_document(
                collection="messages",
                document=message_doc
            )
            
            logger.debug(f"Saved message {message_id} to conversation {conversation_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            raise
    
    async def update_message(self, message_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a message in the database.
        
        Args:
            message_id: The message ID.
            update_data: The data to update.
            
        Returns:
            True if updated successfully.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # First, get the current message
            message = await self.mongo_provider.get_document(
                collection="messages",
                document_id=message_id
            )
            
            if not message:
                logger.warning(f"Message not found for update: {message_id}")
                return False
            
            # Update only allowed fields
            allowed_fields = ['content', 'metadata', 'status']
            update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            # Add updated timestamp
            update_dict['updated_at'] = datetime.utcnow().isoformat()
            
            # Update the message
            success = await self.mongo_provider.update_document(
                collection="messages",
                document_id=message_id,
                update_data=update_dict
            )
            
            if success:
                logger.debug(f"Updated message: {message_id}")
                return True
            else:
                logger.warning(f"Failed to update message: {message_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}")
            return False
    
    async def count_conversation_messages(self, conversation_id: str) -> int:
        """Count messages in a conversation.
        
        Args:
            conversation_id: The conversation ID.
            
        Returns:
            The message count.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Get count from conversation document (faster than counting messages)
            conversation = await self.mongo_provider.get_document(
                collection="conversations",
                document_id=conversation_id
            )
            
            if conversation and "message_count" in conversation:
                return conversation["message_count"]
            
            # Fallback: count messages directly
            count = await self.mongo_provider.count_documents(
                collection="messages",
                query={"conversation_id": conversation_id}
            )
            
            return count
        except Exception as e:
            logger.error(f"Error counting conversation messages: {str(e)}")
            return 0
    
    async def delete_conversation_messages(self, conversation_id: str) -> int:
        """Delete all messages for a conversation.
        
        Args:
            conversation_id: The conversation ID.
            
        Returns:
            The number of messages deleted.
        """
        try:
            # Ensure MongoDB is connected
            if not await self.mongo_provider.is_connected():
                await self.mongo_provider.connect()
            
            # Get all messages for the conversation
            messages = await self.mongo_provider.find_documents(
                collection="messages",
                query={"conversation_id": conversation_id}
            )
            
            delete_count = 0
            for message in messages:
                success = await self.mongo_provider.delete_document(
                    collection="messages",
                    document_id=message["_id"]
                )
                if success:
                    delete_count += 1
            
            # Update the conversation message count
            await self.mongo_provider.update_document(
                collection="conversations",
                document_id=conversation_id,
                update_data={
                    "message_count": 0,
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
            
            return delete_count
        except Exception as e:
            logger.error(f"Error deleting conversation messages: {str(e)}")
            return 0
    
    async def _update_conversation_summary_and_tags(self, conversation_id: str) -> bool:
        """Generate and update summary and tags for a conversation.
        
        Args:
            conversation_id: The conversation ID.
            
        Returns:
            True if updated successfully.
        """
        try:
            # Get the conversation messages
            messages = await self.get_conversation_messages(conversation_id, limit=10)
            
            if not messages or len(messages) < 2:
                return False
            
            # For now, let's use a simple approach instead of calling an AI service
            # Extract the most recent messages for processing
            recent_msgs = messages[-5:] if len(messages) > 5 else messages
            
            # Extract potential keywords from content
            all_content = " ".join([msg.get("content", "") for msg in recent_msgs])
            
            # Simple keyword extraction based on frequency
            # Remove common words and punctuation
            common_words = ["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", 
                           "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had",
                           "do", "does", "did", "can", "could", "will", "would", "should", "may", "might",
                           "i", "you", "he", "she", "it", "we", "they", "this", "that", "these", "those",
                           "my", "your", "his", "her", "its", "our", "their"]
            
            # Clean and tokenize text
            words = all_content.lower().replace(".", " ").replace(",", " ").replace("?", " ").replace("!", " ").split()
            word_freq = {}
            
            for word in words:
                if word not in common_words and len(word) > 3:
                    if word in word_freq:
                        word_freq[word] += 1
                    else:
                        word_freq[word] = 1
            
            # Get top keywords
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            top_keywords = [word for word, freq in sorted_words[:5] if freq > 1]
            
            # Generate a simple summary
            last_user_msg = next((msg.get("content", "") for msg in reversed(messages) 
                                  if msg.get("message_type") == "user"), "")
            last_ai_msg = next((msg.get("content", "") for msg in reversed(messages) 
                                if msg.get("message_type") == "assistant"), "")
            
            # Create a simple summary
            summary = last_user_msg[:50] + "..." if len(last_user_msg) > 50 else last_user_msg
            if not summary or summary.strip() == "":
                summary = "Conversation about " + ", ".join(top_keywords[:3]) if top_keywords else "General conversation"
            
            # Update the conversation with the summary and tags
            update_data = {}
            update_data["summary"] = summary
            update_data["tags"] = top_keywords
            
            # Update the conversation
            success = await self.mongo_provider.update_document(
                collection="conversations",
                document_id=conversation_id,
                update_data=update_data
            )
            
            if success:
                logger.info(f"Updated summary and tags for conversation: {conversation_id}")
                return True
            else:
                logger.warning(f"Failed to update conversation: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating conversation summary and tags: {str(e)}")
            return False
    
    def _parse_summary_response(self, response: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """Parse the AI response to extract summary and tags.
        
        Args:
            response: The AI response text.
            
        Returns:
            Tuple of (summary, tags).
        """
        # Try to extract JSON structure
        try:
            # Check if we have a JSON object in the response
            if '{' in response and '}' in response:
                # Extract JSON substring
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Extract summary and tags
                summary = data.get("summary")
                tags = data.get("tags")
                
                # Ensure tags is a list
                if tags and isinstance(tags, str):
                    tags = [tag.strip() for tag in tags.split(",")]
                    
                return summary, tags
            
            # If not a clear JSON structure, try a more flexible approach
            summary_line = None
            tags = []
            
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("Summary:") or "summary" in line.lower():
                    summary_line = line.split(":", 1)[1].strip() if ":" in line else line
                elif line.startswith("Tags:") or "tags" in line.lower() or "keywords" in line.lower():
                    tag_part = line.split(":", 1)[1].strip() if ":" in line else line
                    # Split by commas, dashes, or other common separators
                    tags = [tag.strip() for tag in tag_part.replace(",", " ").replace("-", " ").split()]
            
            return summary_line, tags
            
        except Exception as e:
            logger.error(f"Error parsing summary response: {str(e)}")
            # Try a simpler approach as fallback
            
            lines = response.strip().split('\n')
            if len(lines) >= 2:
                summary = lines[0].strip()
                tags_line = lines[1].strip()
                if tags_line.startswith("Tags: "):
                    tags_line = tags_line[6:]
                tags = [tag.strip() for tag in tags_line.split(',')]
                return summary, tags
            
            return None, None
