"""Chat Agent for AI interactions.

This module provides a chat agent for AI interactions that can process
messages and generate responses using multiple LLM providers.
"""
import logging
import asyncio
import json
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid

from ai.base_agent import BaseAgent
from ai.gemini_integration import GeminiConnector
from ai.anthropic_integration import AnthropicConnector

# Setup logging
logger = logging.getLogger(__name__)

class ChatAgent(BaseAgent):
    """Chat agent for AI interactions."""
    
    def __init__(self, user_id: str, conversation_id: Optional[str] = None):
        """Initialize the chat agent.
        
        Args:
            user_id: The user ID.
            conversation_id: Optional conversation ID for tracking context.
        """
        super().__init__(user_id)
        # Set conversation ID
        self.conversation_id = conversation_id or str(uuid.uuid4())
        # Initialize conversation history
        self.conversation_history = []
        
        # Try to import centralized prompts, fallback to hardcoded if not available
        try:
            from ai.prompts import get_system_prompt
            self.system_prompt = get_system_prompt("knowledge_forest_assistant")
        except (ImportError, KeyError):
            # Fallback to hardcoded prompt
            self.system_prompt = """
            You are the assistant for AI Knowledge Forest, an intelligent system specialized in organizing and managing knowledge.
            You can:
            - Help users build and manage knowledge graphs
            - Answer questions and automatically integrate answers into the knowledge network
            - Identify connections between concepts and establish links
            - Summarize complex information and transform it into structured knowledge
            
            When users ask questions, you analyze the problem, provide helpful answers, and automatically add important concepts to their knowledge forest.
            If users ask who you are or what you can do, introduce yourself as the AI Knowledge Forest assistant, rather than just discussing the base model.
            Your main goal is to help users organize and expand their knowledge network.
            """
            
        self._setup_llm_providers()
    
    def _setup_llm_providers(self):
        """Set up the LLM providers for the agent."""
        try:
            # Set up Gemini providers with different models and priorities
            
            # Get model names from environment variables
            primary_model_name = os.environ.get("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash-thinking-exp-01-21")
            enhanced_model_name = os.environ.get("GEMINI_ENHANCED_MODEL", "gemini-2.5-pro-exp-03-25")
            image_model_name = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation")
            claude_model_name = os.environ.get("ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
            
            # Try to register primary Gemini model
            try:
                # Primary model: Gemini Flash Thinking (priority 1)
                primary_model = GeminiConnector(
                    model_name=primary_model_name,
                    priority=1
                )
                self.register_llm_provider(primary_model)
            except Exception as e:
                logger.warning(f"Could not register primary Gemini model: {e}")
            
            # Try to register enhanced model
            try:
                # Enhanced model 1: Gemini Pro (priority 5)
                enhanced_model1 = GeminiConnector(
                    model_name=enhanced_model_name,
                    priority=5
                )
                self.register_llm_provider(enhanced_model1)
            except Exception as e:
                logger.warning(f"Could not register enhanced Gemini model: {e}")
            
            # Try to register Anthropic model
            try:
                anthropic_model = AnthropicConnector(
                    model_name=claude_model_name,
                    priority=10
                )
                self.register_llm_provider(anthropic_model)
            except Exception as e:
                logger.warning(f"Could not register Anthropic model: {e}")
            
            # Try to register image model
            try:
                # Image generation model: Gemini Image Generation (priority 20)
                image_model = GeminiConnector(
                    model_name=image_model_name,
                    priority=20
                )
                self.register_llm_provider(image_model)
            except Exception as e:
                logger.warning(f"Could not register Gemini image model: {e}")
            
            # Initialize all providers if we have any
            if self.llm_providers:
                self.initialize_llm_providers()
            else:
                logger.error("No LLM providers could be registered")
                self.is_llm_initialized = False
            
        except Exception as e:
            logger.error(f"Error setting up LLM providers: {e}")
            self.is_llm_initialized = False
    
    async def process_message(self, message: str, use_enhanced_model: bool = False) -> str:
        """Process a message and return a response.
        
        Args:
            message: The user message.
            use_enhanced_model: Whether to use an enhanced model.
            
        Returns:
            The AI response.
        """
        # Load conversation history from database if available and history is empty
        if not self.conversation_history:
            await self._load_conversation_history()
        
        # Add the new message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Find a model to process the message
        model_filter = lambda m: m.get_capabilities().get("text_generation", False)
        
        if use_enhanced_model:
            # For enhanced mode, prefer Claude or Gemini Pro if available
            provider = self.get_filtered_provider(model_filter, lambda m: m.priority >= 5)
        else:
            # Otherwise use any available text generation model
            provider = self.get_filtered_provider(model_filter)
        
        if not provider:
            return "I'm sorry, but I don't have text generation capabilities available right now."
        
        # Process the message with conversation history
        try:
            # Format conversation history for the provider
            formatted_history = self._format_conversation_history_for_provider(provider.name)
            
            # Generate response using the formatted history
            response = await provider.generate_text(
                message, 
                system_prompt=self.system_prompt,
                conversation_history=formatted_history
            )
            
            # Add the response to history
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Save the updated conversation history asynchronously
            asyncio.create_task(self._save_conversation_message(message, response))
            
            return response
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"I'm sorry, but I encountered an error processing your message: {str(e)}"
    
    async def process_thinking_message(self, message: str) -> str:
        """Process a message with active thinking steps.
        
        This method uses the Gemini thinking model to process a message
        with active thinking steps, visible to the user.
        
        Args:
            message: The user message.
            
        Returns:
            The AI response.
        """
        # First load conversation history if empty
        if not self.conversation_history:
            await self._load_conversation_history()
            
        # Add the new message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Find a model with thinking capability
        thinking_model = None
        for provider in self.llm_providers:
            if provider.is_initialized and provider.get_capabilities().get("thinking", False):
                thinking_model = provider
                break
        
        if not thinking_model:
            # Fallback to regular processing
            return await self.process_message(message, use_enhanced_model=True)
            
        # Process with thinking model
        try:
            # Format conversation history for the provider
            formatted_history = self._format_conversation_history_for_provider(thinking_model.name)
            
            # Generate thinking response
            thinking_prompt = f"{self.system_prompt}\n\nThink step by step about the following question:\n{message}"
            response = await thinking_model.generate_text(
                thinking_prompt,
                conversation_history=formatted_history
            )
            
            # Add the response to history
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Save the updated conversation history asynchronously
            asyncio.create_task(self._save_conversation_message(message, response))
            
            return response
        except Exception as e:
            logger.error(f"Error processing thinking message: {e}")
            return f"I'm sorry, but I encountered an error while thinking about your question: {str(e)}"
    
    async def process_image_generation(self, prompt: str) -> Union[str, Dict[str, Any]]:
        """Generate an image based on a prompt.
        
        Args:
            prompt: The image generation prompt.
            
        Returns:
            The image URL or error message.
        """
        # Find a model with image generation capability
        image_model = None
        for provider in self.llm_providers:
            if provider.is_initialized and provider.get_capabilities().get("image_generation", False):
                image_model = provider
                break
        
        if not image_model:
            return "I'm sorry, but I don't have image generation capabilities available right now."
            
        # Generate image
        try:
            result = await image_model.generate_image(prompt)
            
            # Save to conversation history
            self.conversation_history.append({"role": "user", "content": f"[Image prompt]: {prompt}"})
            self.conversation_history.append({"role": "assistant", "content": f"[Generated image with caption]: {result.get('caption', 'Image')}"})
            
            # Save messages asynchronously
            asyncio.create_task(self._save_conversation_message(
                f"[Image prompt]: {prompt}", 
                f"[Generated image with caption]: {result.get('caption', 'Image')}"
            ))
            
            return result
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return f"I'm sorry, but I encountered an error generating the image: {str(e)}"
            
    async def _load_conversation_history(self) -> None:
        """Load conversation history from the database."""
        try:
            if not self.conversation_id:
                return
                
            # Import here to avoid circular import
            from services.message_storage import MessageStorageService
            storage = MessageStorageService()
            
            # Get messages for this conversation
            messages = await storage.get_conversation_messages(
                conversation_id=self.conversation_id,
                limit=50  # Reasonable limit for context
            )
            
            # Format messages for conversation history
            for msg in messages:
                role = "assistant" if msg.get("message_type") == "assistant" else "user"
                self.conversation_history.append({
                    "role": role,
                    "content": msg.get("content", "")
                })
                
            logger.info(f"Loaded {len(messages)} messages from conversation history")
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
    
    def _format_conversation_history_for_provider(self, provider_name: str) -> List[Dict[str, str]]:
        """Format conversation history for the specific provider.
        
        Args:
            provider_name: The provider name.
            
        Returns:
            Formatted conversation history.
        """
        # Use recent history to avoid context length issues
        recent_history = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history
        
        # For now, return as is - can be customized per provider if needed
        return recent_history
    
    async def _save_conversation_message(self, user_message: str, ai_response: str) -> None:
        """Save messages to the conversation history in database.
        
        Args:
            user_message: The user message.
            ai_response: The AI response.
        """
        try:
            # Import here to avoid circular import
            from services.message_storage import MessageStorageService
            from services.event_bus import EventBus
            
            storage = MessageStorageService()
            event_bus = EventBus()
            
            # Generate message IDs
            user_message_id = str(uuid.uuid4())
            ai_message_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            # Publish user message event
            await event_bus.publish("message.created", {
                "user_id": self.user_id,
                "conversation_id": self.conversation_id,
                "message_id": user_message_id,
                "message_type": "user",
                "content": user_message,
                "timestamp": timestamp
            })
            
            # Publish AI message event
            await event_bus.publish("message.created", {
                "user_id": self.user_id,
                "conversation_id": self.conversation_id,
                "message_id": ai_message_id,
                "message_type": "assistant",
                "content": ai_response,
                "timestamp": timestamp
            })
        except Exception as e:
            logger.error(f"Error saving conversation message: {e}")
