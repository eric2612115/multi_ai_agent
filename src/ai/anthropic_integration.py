"""Anthropic Integration for AI interactions.

This module provides integration with Anthropic's Claude models.
"""
import logging
import os
import json
import time
from typing import Dict, List, Optional, Any, Union
import anthropic

from src.ai.base_agent import LLMProvider

# Setup logging
logger = logging.getLogger(__name__)

class AnthropicConnector(LLMProvider):
    """Connector for Anthropic's Claude models."""
    
    def __init__(self, model_name: str = "claude-3-7-sonnet-20250219", priority: int = 10):
        """Initialize the Anthropic connector.
        
        Args:
            model_name: The model name to use.
            priority: The priority (lower number means higher priority).
        """
        super().__init__(model_name, priority)
        # Get API key from environment
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        self.max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "4000"))
        self.temperature = float(os.environ.get("ANTHROPIC_TEMPERATURE", "0.7"))
    
    def retry_with_exponential_backoff(self, func, max_retries=3, base_delay=1, max_delay=10):
        """Retry a function with exponential backoff.
        
        Args:
            func: The function to retry.
            max_retries: Maximum number of retries.
            base_delay: Base delay in seconds.
            max_delay: Maximum delay in seconds.
            
        Returns:
            The result of the function call.
            
        Raises:
            The last exception raised by the function.
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt == max_retries - 1:
                    raise
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"Attempt {attempt + 1} failed with error: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
        raise last_exception  # Should never get here, but just in case
    
    def initialize(self) -> bool:
        """Initialize the Anthropic connector.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        try:
            if not self.api_key:
                logger.warning("ANTHROPIC_API_KEY not found in environment variables")
                return False
            
            # Initialize client
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.is_initialized = True
            logger.info(f"Anthropic connector initialized with model {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Error initializing Anthropic connector: {e}")
            self.is_initialized = False
            return False
    
    def generate_response(self, message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate a response using Anthropic's Claude.
        
        Args:
            message: The user message.
            conversation_history: Optional conversation history.
            
        Returns:
            The AI response.
        """
        try:
            # Make sure we're initialized
            if not self.is_initialized:
                if not self.initialize():
                    raise ValueError("Failed to initialize Anthropic connector")
            
            # Format messages for Anthropic's API
            messages = []
            
            if conversation_history:
                # Add conversation history, limiting to last 10 messages for context
                history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
                for entry in history:
                    if entry["role"] == "user":
                        messages.append({"role": "user", "content": entry["content"]})
                    elif entry["role"] == "assistant":
                        messages.append({"role": "assistant", "content": entry["content"]})
            else:
                # If no history, just add the current message
                messages.append({"role": "user", "content": message})
            
            # Generate response with retry
            def _call_api():
                return self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=messages,
                    system="You are an intelligent knowledge assistant. Provide informative, accurate, and helpful responses. Focus on a combination of comprehensive, factually accurate information while being conversational and engaging. When appropriate, organize information in a clear structure. Avoid fabricating information, express uncertainty when appropriate."
                )
            
            response = self.retry_with_exponential_backoff(_call_api)
            
            # Extract and return the text response
            return response.content[0].text
            
        except Exception as e:
            logger.exception(f"Error generating response with Anthropic: {e}")
            raise
    
    def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using a simple prompt.
        
        Args:
            prompt: The prompt text.
            system_prompt: Optional system prompt.
            
        Returns:
            The generated text.
        """
        try:
            # Make sure we're initialized
            if not self.is_initialized:
                if not self.initialize():
                    return "Failed to initialize Anthropic connector"
            
            # Build messages
            messages = [{"role": "user", "content": prompt}]
            
            # Generate response with retry
            def _call_api():
                return self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=messages,
                    system=system_prompt or "You are a helpful assistant."
                )
            
            response = self.retry_with_exponential_backoff(_call_api)
            
            # Extract and return the text response
            return response.content[0].text
            
        except Exception as e:
            logger.exception(f"Error generating text with Anthropic: {e}")
            return f"Error generating text: {str(e)}"
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get the capabilities of this LLM provider.
        
        Returns:
            Dictionary of capabilities.
        """
        return {
            "chat": True,
            "text": True,
            "image_generation": False,
            "image_analysis": True,
            "thinking": True
        }
