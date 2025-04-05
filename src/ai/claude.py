"""Anthropic Claude AI model implementation.

This module implements the Claude AI model interfaces, providing text generation
and chat capabilities.
"""
import os
import json
import random
import time
import asyncio
from typing import Dict, List, Optional, Union, Any

import httpx
from anthropic import Anthropic, AsyncAnthropic

from ai.base import TextGenerationModel
from ai.factory import register_ai_model
from common.config import get_settings
from common.exceptions import AIServiceUnavailableError, AIRequestError, AIRateLimitError

settings = get_settings()

class ClaudeModel(TextGenerationModel):
    """Anthropic Claude AI model implementation."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize the Claude model.
        
        Args:
            api_key: Optional API key. If not provided, it will be loaded from settings.
            model_name: Optional model name. If not provided, it will be loaded from settings.
        """
        self.api_key = api_key or settings.ai.claude_api_key
        self._model_name = model_name or settings.ai.claude_model_name
        self._api_version = settings.ai.claude_api_version
        
        if not self.api_key:
            raise ValueError("Claude API key not provided and not found in settings")
            
        # Initialize synchronous and asynchronous clients
        self.client = Anthropic(api_key=self.api_key)
        self._async_client = None  # Lazy initialization
        
        # Fallback model
        self._gemini_fallback = None
    
    @property
    def model_name(self) -> str:
        """Get the current model name.
        
        Returns:
            The name of the model.
        """
        return self._model_name
    
    def set_model(self, model_name: str) -> None:
        """Set the model to use.
        
        Args:
            model_name: The name of the model to use.
        """
        self._model_name = model_name
    
    def is_available(self) -> bool:
        """Check if the Claude service is available.
        
        Returns:
            True if the service is available.
        """
        try:
            # Simple ping to the API
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": self.api_key, "anthropic-version": self._api_version}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    @property
    def async_client(self) -> AsyncAnthropic:
        """Get the async client, initializing it if necessary.
        
        Returns:
            The async client.
        """
        if self._async_client is None:
            self._async_client = AsyncAnthropic(api_key=self.api_key)
        return self._async_client
    
    async def generate_text(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        """Generate text based on a prompt.
        
        Args:
            prompt: The input prompt.
            max_tokens: Maximum number of tokens to generate.
            **kwargs: Additional parameters.
            
        Returns:
            Generated text.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        max_retries = kwargs.pop('max_retries', 3)
        initial_backoff = kwargs.pop('initial_backoff', 1.0)
        
        # Retry logic
        retries = 0
        backoff = initial_backoff
        
        while True:
            try:
                # Convert simple prompt to the chat format
                messages = [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
                
                # Use the async client
                response = await self.async_client.messages.create(
                    model=self._model_name,
                    max_tokens=max_tokens,
                    messages=messages,
                    **kwargs
                )
                
                return response.content[0].text
                
            except Exception as e:
                # Determine error type
                error_str = str(e).lower()
                is_rate_limit = (
                    hasattr(e, 'status_code') and getattr(e, 'status_code') in (429, 500, 503)
                ) or "rate limit" in error_str or "overloaded" in error_str
                
                if is_rate_limit:
                    retries += 1
                    if retries > max_retries:
                        # Switch to fallback after max retries
                        if kwargs.get('use_fallback', True):
                            return await self._fallback_to_gemini(prompt, max_tokens)
                        else:
                            raise AIRateLimitError(f"Claude service rate limited and retry limit exceeded: {str(e)}")
                    
                    # Calculate backoff time with jitter
                    jitter = random.uniform(0, 0.1 * backoff)
                    sleep_time = backoff + jitter
                    
                    # Log
                    print(f"Claude API rate limited, retrying in {sleep_time:.2f}s ({retries}/{max_retries})")
                    
                    # Sleep and retry
                    await asyncio.sleep(sleep_time)
                    
                    # Exponential backoff
                    backoff *= 2
                else:
                    # Other errors
                    if kwargs.get('use_fallback', True):
                        return await self._fallback_to_gemini(prompt, max_tokens)
                    else:
                        raise AIRequestError(f"Claude request error: {str(e)}")
    
    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 1024, **kwargs) -> str:
        """Generate a chat response.
        
        Args:
            messages: List of messages, each containing 'role' and 'content'.
            max_tokens: Maximum number of tokens to generate.
            **kwargs: Additional parameters.
            
        Returns:
            Generated response text.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        max_retries = kwargs.pop('max_retries', 3)
        initial_backoff = kwargs.pop('initial_backoff', 1.0)
        
        # Retry logic
        retries = 0
        backoff = initial_backoff
        
        while True:
            try:
                # Convert messages to Claude's format (should already be compatible)
                # Claude expects: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
                
                # Use the async client
                response = await self.async_client.messages.create(
                    model=self._model_name,
                    max_tokens=max_tokens,
                    messages=messages,
                    **kwargs
                )
                
                return response.content[0].text
                
            except Exception as e:
                # Determine error type
                error_str = str(e).lower()
                is_rate_limit = (
                    hasattr(e, 'status_code') and getattr(e, 'status_code') in (429, 500, 503)
                ) or "rate limit" in error_str or "overloaded" in error_str
                
                if is_rate_limit:
                    retries += 1
                    if retries > max_retries:
                        # Switch to fallback after max retries
                        if kwargs.get('use_fallback', True):
                            # Convert message format to a single prompt for Gemini
                            combined_prompt = "\n\n".join([
                                f"{msg['role']}: {msg['content']}"
                                for msg in messages
                            ])
                            return await self._fallback_to_gemini(combined_prompt, max_tokens)
                        else:
                            raise AIRateLimitError(f"Claude service rate limited and retry limit exceeded: {str(e)}")
                    
                    # Calculate backoff time with jitter
                    jitter = random.uniform(0, 0.1 * backoff)
                    sleep_time = backoff + jitter
                    
                    # Log
                    print(f"Claude API rate limited, retrying in {sleep_time:.2f}s ({retries}/{max_retries})")
                    
                    # Sleep and retry
                    await asyncio.sleep(sleep_time)
                    
                    # Exponential backoff
                    backoff *= 2
                else:
                    # Other errors
                    if kwargs.get('use_fallback', True):
                        # Convert message format to a single prompt for Gemini
                        combined_prompt = "\n\n".join([
                            f"{msg['role']}: {msg['content']}"
                            for msg in messages
                        ])
                        return await self._fallback_to_gemini(combined_prompt, max_tokens)
                    else:
                        raise AIRequestError(f"Claude request error: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: The text to count tokens in.
            
        Returns:
            Token count.
        """
        try:
            response = await self.async_client.messages.count_tokens(
                model=self._model_name,
                messages=[{"role": "user", "content": text}]
            )
            return response.input_tokens
        except Exception:
            # Fallback estimation
            # Claude tokens are roughly 4 characters per token
            return len(text) // 4
    
    async def _fallback_to_gemini(self, prompt: str, max_tokens: int = 1024) -> str:
        """Fall back to Gemini when Claude is unavailable.
        
        Args:
            prompt: The input prompt.
            max_tokens: Maximum number of tokens to generate.
            
        Returns:
            Generated text.
        """
        # Lazy load Gemini fallback
        if self._gemini_fallback is None:
            from ai.factory import get_ai_model
            try:
                self._gemini_fallback = get_ai_model("gemini")
                print("Using Gemini as fallback for Claude")
            except Exception as e:
                raise AIServiceUnavailableError(
                    f"Both Claude and Gemini fallback are unavailable. Claude error: service overloaded, "
                    f"Gemini error: {str(e)}"
                )
        
        try:
            return await self._gemini_fallback.generate_text(prompt, max_tokens=max_tokens)
        except Exception as e:
            raise AIServiceUnavailableError(
                f"Both Claude and Gemini fallback are unavailable. Claude error: service overloaded, "
                f"Gemini error: {str(e)}"
            )

# Register the model with the factory
register_ai_model("claude", ClaudeModel)
