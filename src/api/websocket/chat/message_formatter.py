"""Message formatter for chat WebSocket.

This module provides formatting utilities for chat messages with standardized format.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Message formatter for chat messages."""
    
    # Message format version
    # Increment this when the message format changes
    MESSAGE_FORMAT_VERSION = "1.0.0"
    
    @staticmethod
    def format_message(sender: str, text: str, message_type: str = "normal", 
                      message_id: str = None, metadata: Dict[str, Any] = None,
                      sub_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Format a chat message with standardized structure.
        
        Args:
            sender: The message sender.
            text: The message text.
            message_type: The message type.
            message_id: Optional message ID. If not provided, a new UUID will be generated.
            metadata: Optional additional metadata to include.
            sub_messages: Optional list of sub-messages (for staged or multi-part responses).
            
        Returns:
            The formatted message.
        """
        message = {
            "id": message_id or str(uuid.uuid4()),
            "sender": sender,
            "text": text,
            "message_type": message_type,
            "timestamp": datetime.now().isoformat(),
            "format_version": MessageFormatter.MESSAGE_FORMAT_VERSION
        }
        
        # Add metadata if provided
        if metadata:
            message["metadata"] = metadata
            
        # Add sub-messages if provided
        if sub_messages:
            message["sub_messages"] = sub_messages
            
        return message
    
    @staticmethod
    def format_thinking(text: str, progress: float = None, step: str = None,
                      metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format a thinking message with progress tracking support.
        
        Args:
            text: The message text.
            progress: Optional progress value between 0.0 and 1.0.
            step: Optional current step description.
            metadata: Optional additional metadata to include.
            
        Returns:
            The formatted message.
        """
        metadata = metadata or {}
        if progress is not None:
            metadata["progress"] = max(0.0, min(1.0, float(progress)))
        if step:
            metadata["current_step"] = step
            
        return MessageFormatter.format_message("system", text, "thinking", metadata=metadata)
    
    @staticmethod
    def format_error(text: str, error_code: str = None, severity: str = "error",
                   details: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format an error message with detailed error information.
        
        Args:
            text: The error message text.
            error_code: Optional error code.
            severity: Error severity level (error, warning, critical).
            details: Optional detailed error information.
            metadata: Optional additional metadata to include.
            
        Returns:
            The formatted message.
        """
        metadata = metadata or {}
        if error_code:
            metadata["error_code"] = error_code
        metadata["severity"] = severity
        if details:
            metadata["details"] = details
            
        return MessageFormatter.format_message("system", text, "error", metadata=metadata)
    
    @staticmethod
    def format_ai_response(text: str, model_used: str = None, tokens: int = None,
                         processing_time: float = None, thinking_steps: List[Dict[str, Any]] = None,
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format an AI response message with support for thinking steps.
        
        Args:
            text: The message text.
            model_used: Optional name of the model used.
            tokens: Optional token count.
            processing_time: Optional processing time in seconds.
            thinking_steps: Optional list of thinking steps.
            metadata: Optional additional metadata to include.
            
        Returns:
            The formatted message.
        """
        metadata = metadata or {}
        if model_used:
            metadata["model"] = model_used
        if tokens is not None:
            metadata["tokens"] = tokens
        if processing_time is not None:
            metadata["processing_time"] = processing_time
            
        # Create sub-messages for thinking steps if provided
        sub_messages = None
        if thinking_steps:
            sub_messages = [
                {
                    "id": str(uuid.uuid4()),
                    "type": "thinking_step",
                    "content": step.get("content", ""),
                    "step_number": i + 1,
                    "timestamp": datetime.now().isoformat()
                }
                for i, step in enumerate(thinking_steps)
            ]
            
        return MessageFormatter.format_message(
            "agent", text, "normal", 
            metadata=metadata, 
            sub_messages=sub_messages
        )
    
    @staticmethod
    def format_status(status: str, progress: float = None, 
                    details: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format a status message with progress information.
        
        Args:
            status: The status text.
            progress: Optional progress value between 0.0 and 1.0.
            details: Optional additional details.
            
        Returns:
            The formatted message.
        """
        metadata = {"status": status}
        if progress is not None:
            metadata["progress"] = max(0.0, min(1.0, float(progress)))
        if details:
            metadata.update(details)
            
        return MessageFormatter.format_message("system", f"Status: {status}", "status", metadata=metadata)
    
    @staticmethod
    def format_heartbeat() -> Dict[str, Any]:
        """Format a heartbeat message.
        
        Returns:
            The formatted message.
        """
        return {
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "format_version": MessageFormatter.MESSAGE_FORMAT_VERSION
        }
    
    @staticmethod
    def format_welcome(user_id: str) -> Dict[str, Any]:
        """Format a welcome message.
        
        Args:
            user_id: The user ID.
            
        Returns:
            The formatted message.
        """
        try:
            # Create welcome message with standard format
            return MessageFormatter.format_message(
                sender="system",
                text="Welcome to the Knowledge Explorer!",
                message_type="welcome",
                metadata={"user_id": user_id}
            )
        except Exception as e:
            logger.error(f"Error formatting welcome message: {e}")
            # Return an absolute minimal message if there's an error
            return {
                "id": "welcome",
                "message_type": "welcome",
                "text": "Welcome",
                "format_version": MessageFormatter.MESSAGE_FORMAT_VERSION
            }
    
    @staticmethod
    def format_goodbye(reason: str = None) -> Dict[str, Any]:
        """Format a goodbye message.
        
        Args:
            reason: Optional reason for disconnection.
            
        Returns:
            The formatted message.
        """
        text = "Thank you for using the AI chat service. Goodbye!"
        metadata = {}
        
        if reason:
            text = f"{text} Reason: {reason}"
            metadata["disconnect_reason"] = reason
            
        return MessageFormatter.format_message("system", text, "goodbye", metadata=metadata)
    
    @staticmethod
    def format_image_response(image_url: str, caption: str = None, 
                            width: int = None, height: int = None,
                            prompt: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format an image response message with extended attributes.
        
        Args:
            image_url: The URL of the image.
            caption: Optional image caption.
            width: Optional image width.
            height: Optional image height.
            prompt: Optional prompt used to generate the image.
            metadata: Optional additional metadata.
            
        Returns:
            The formatted message.
        """
        metadata = metadata or {}
        metadata["image_url"] = image_url
        
        if width:
            metadata["width"] = width
        if height:
            metadata["height"] = height
        if prompt:
            metadata["generation_prompt"] = prompt
        
        text = caption or "Generated image"
        return MessageFormatter.format_message("agent", text, "image", metadata=metadata)
        
    @staticmethod
    def format_thinking_progress(current_step: str, total_steps: int, step_number: int,
                               step_details: str = None, progress: float = None) -> Dict[str, Any]:
        """Format a thinking progress message for multi-step AI reasoning.
        
        Args:
            current_step: The current step description.
            total_steps: Total number of steps.
            step_number: Current step number.
            step_details: Optional detailed step information.
            progress: Optional overall progress (0.0-1.0).
            
        Returns:
            The formatted message.
        """
        # Calculate progress if not provided
        if progress is None and total_steps > 0:
            progress = min(1.0, max(0.0, step_number / total_steps))
        
        metadata = {
            "current_step": current_step,
            "step_number": step_number,
            "total_steps": total_steps
        }
        
        if step_details:
            metadata["step_details"] = step_details
        if progress is not None:
            metadata["progress"] = progress
            
        text = f"Step {step_number}/{total_steps}: {current_step}"
        return MessageFormatter.format_message("system", text, "thinking_progress", metadata=metadata)
