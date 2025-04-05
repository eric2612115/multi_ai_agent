import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid
import os
from abc import ABC, abstractmethod

from services.event_bus import EventBus
from forest.extraction_service import KnowledgeExtractionService

# Setup logging
logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Base LLM provider class."""
    
    def __init__(self, model_name: str, priority: int = 1):
        """Initialize the LLM provider.
        
        Args:
            model_name: The model name.
            priority: The priority (lower number means higher priority).
        """
        self.model_name = model_name
        self.priority = priority
        self.is_initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the LLM provider.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def generate_response(self, message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate a response.
        
        Args:
            message: The message to generate a response for.
            conversation_history: Optional conversation history.
            
        Returns:
            The generated response.
        """
        pass
    
    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using a simple prompt.
        
        Args:
            prompt: The prompt text.
            system_prompt: Optional system prompt.
            
        Returns:
            The generated text.
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """Get the capabilities of this LLM provider.
        
        Returns:
            Dictionary of capabilities.
        """
        pass

class BaseAgent:
    """Base agent for AI interactions."""
    
    def __init__(self, user_id: str):
        """Initialize the base agent.
        
        Args:
            user_id: The user ID.
        """
        self.user_id = user_id
        self.event_bus = EventBus()
        self.extraction_service = KnowledgeExtractionService()
        self.conversation_history = []
        self.llm_providers = []
        self.is_llm_initialized = False
        self.system_prompt = ""  # 系統提示，子類可重寫
    
    def register_llm_provider(self, provider: LLMProvider):
        """Register an LLM provider.
        
        Args:
            provider: The LLM provider to register.
        """
        self.llm_providers.append(provider)
        # Sort providers by priority
        self.llm_providers.sort(key=lambda x: x.priority)
        print(f"Registered LLM provider {provider.model_name} with priority {provider.priority}")
        logger.info(f"Registered LLM provider {provider.model_name} with priority {provider.priority}")
    
    def initialize_llm_providers(self):
        """Initialize all registered LLM providers."""
        if not self.llm_providers:
            logger.warning("No LLM providers registered")
            return False
        
        success = False
        for provider in self.llm_providers:
            try:
                if provider.initialize():
                    logger.info(f"Successfully initialized LLM provider {provider.model_name}")
                    success = True
                else:
                    logger.warning(f"Failed to initialize LLM provider {provider.model_name}")
            except Exception as e:
                logger.error(f"Error initializing LLM provider {provider.model_name}: {str(e)}")
        
        # Even if not all providers initialized successfully, if at least one did, we can proceed
        self.is_llm_initialized = success
        return success
    
    async def process_message(self, message: str, use_enhanced_model: bool = False) -> str:
        """Process a user message and generate a response.
        
        Args:
            message: The user message.
            use_enhanced_model: Whether to use an enhanced model.
            
        Returns:
            The AI response.
        """
        try:
            # Add user message to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            
            # Make sure we have a system prompt in the conversation history
            if self.system_prompt and not any(msg.get("role") == "system" for msg in self.conversation_history):
                # Add system prompt at the beginning
                self.conversation_history.insert(0, {
                    "role": "system",
                    "content": self.system_prompt
                })
                logger.debug(f"Added system prompt to conversation history")
            
            # Make sure LLM providers are initialized
            if not self.is_llm_initialized:
                self.initialize_llm_providers()
                if not self.is_llm_initialized:
                    return "I'm currently unable to process your request due to a technical issue with my language models. Please try again later."
            
            # Select provider based on enhanced flag
            provider = None
            if use_enhanced_model:
                # Try to find an enhanced provider (priority > 1)
                for p in self.llm_providers:
                    if p.priority > 1 and p.is_initialized:
                        provider = p
                        break
            
            # If no enhanced provider found or enhanced not requested, use highest priority provider
            if not provider:
                for p in self.llm_providers:
                    if p.is_initialized:
                        provider = p
                        break
            
            if not provider:
                return "I'm currently unable to process your request due to a technical issue with my language models. Please try again later."
            
            # Generate response using the selected provider
            response = provider.generate_response(message, self.conversation_history)
            
            # Add AI response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Extract knowledge if enabled
            try:
                # This runs in the background, we don't wait for it
                message_id = str(uuid.uuid4())
                conversation_id = str(uuid.uuid4())
                asyncio.create_task(self.extraction_service.extract_knowledge(
                    content=f"User: {message}\nAssistant: {response}",
                    user_id=self.user_id,
                    metadata={
                        "message_id": message_id,
                        "conversation_id": conversation_id
                    }
                ))
            except Exception as extract_error:
                logger.error(f"Error extracting knowledge: {extract_error}")
            
            return response
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return f"I encountered an error while processing your message: {str(e)}"
