"""Gemini Integration for AI interactions.

This module provides integration with Google's Gemini models using the SDK.
"""
import logging
import os
import json
import time
from typing import Dict, List, Optional, Any, Union

try:
    # First try the new SDK format
    from google import genai
    HAS_NEW_SDK = True
except ImportError:
    # Otherwise try the old format
    try:
        import google.generativeai as genai
        HAS_NEW_SDK = False
    except ImportError:
        raise ImportError("Neither 'google-genai' nor 'google-generativeai' packages are installed")

from src.ai.base_agent import LLMProvider

# Setup logging
logger = logging.getLogger(__name__)

class GeminiConnector(LLMProvider):
    """Connector for Google's Gemini models."""
    
    MODEL_CAPABILITIES = {
        "gemini-2.0-flash-thinking-exp-01-21": {
            "chat": True,
            "text": True,
            "text_generation": True,
            "image_generation": False,
            "image_analysis": False,
            "thinking": True
        },
        "gemini-2.5-pro-exp-03-25": {
            "chat": True,
            "text": True,
            "text_generation": True,
            "image_generation": False,
            "image_analysis": True,
            "thinking": True
        },
        "gemini-2.0-flash-exp-image-generation": {
            "chat": False,
            "text": False,
            "text_generation": False,
            "image_generation": True,
            "image_analysis": False,
            "thinking": False
        }
    }
    
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp-01-21", priority: int = 1):
        """Initialize the Gemini connector.
        
        Args:
            model_name: The model name to use.
            priority: The priority (lower number means higher priority).
        """
        super().__init__(model_name, priority)
        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("AI_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.temperature = float(os.environ.get("GEMINI_TEMPERATURE", "0.7"))
        self.model = None
        self.client = None
        self.supports_conversation_history = False  # Gemini doesn't support our conversation_history parameter
    
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
        """Initialize the Gemini connector.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        try:
            if not self.api_key:
                logger.warning("GOOGLE_API_KEY not found in environment variables")
                return False
            
            # Create a new client
            if HAS_NEW_SDK:
                # For the new SDK
                self.client = genai.Client(api_key=self.api_key)
            else:
                # For the old SDK
                genai.configure(api_key=self.api_key)
            
            # Get models listing if available
            try:
                if HAS_NEW_SDK:
                    # For new SDK
                    models = self.client.models.list()
                    logger.info(f"Available models: {[m.name for m in models]}")
                else:
                    # For old SDK
                    models = genai.list_models()
                    logger.info(f"Available models: {[m.name for m in models]}")
            except Exception as e:
                logger.warning(f"Could not list models: {e}")
            
            self.is_initialized = True
            logger.info(f"Gemini connector initialized with model {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Error initializing Gemini connector: {e}")
            self.is_initialized = False
            return False
    
    async def generate_response(self, message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate a response using Gemini.
        
        Args:
            message: The user message.
            conversation_history: Optional conversation history.
            
        Returns:
            The AI response.
        """
        try:
            if not self.is_initialized:
                if not self.initialize():
                    raise ValueError(f"Failed to initialize Gemini connector with model {self.model_name}")
            
            # Generate response with retry
            def _call_api():
                # Common generation config
                generation_config = {
                    "temperature": self.temperature,
                    "top_p": 0.95,
                    "top_k": 40,
                }
                
                if HAS_NEW_SDK:
                    # For new SDK
                    return self.client.models.generate_content(
                        model=self.model_name,
                        contents=message,
                        config=generation_config
                    )
                else:
                    # For old SDK
                    model = genai.GenerativeModel(self.model_name)
                    return model.generate_content(
                        message,
                        generation_config=generation_config
                    )
            
            response = self.retry_with_exponential_backoff(_call_api)
            
            # Extract and return the text response
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].content.parts[0].text
            else:
                # Fallback for non-standard response structure
                try:
                    return str(response)
                except:
                    return "I couldn't generate a response. Please try again."
            
        except Exception as e:
            logger.exception(f"Error generating response with Gemini: {e}")
            return f"Error generating response: {str(e)}"
    
    async def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using a simple prompt.
        
        Args:
            prompt: The prompt text.
            system_prompt: Optional system prompt.
            
        Returns:
            The generated text.
        """
        try:
            if not self.is_initialized:
                if not self.initialize():
                    return f"Failed to initialize Gemini connector with model {self.model_name}"
            
            # Call generate_response, which handles both SDKs
            if system_prompt:
                enhanced_prompt = f"{system_prompt}\n\n{prompt}"
                return await self.generate_response(enhanced_prompt)
            else:
                return await self.generate_response(prompt)
            
        except Exception as e:
            logger.exception(f"Error generating text with Gemini: {e}")
            return f"Error generating text: {str(e)}"
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get the capabilities of this LLM provider.
        
        Returns:
            Dictionary of capabilities.
        """
        return self.MODEL_CAPABILITIES.get(self.model_name, {
            "chat": True,
            "text": True,
            "text_generation": True,
            "image_generation": False,
            "image_analysis": False,
            "thinking": False
        })
