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

from src.ai.base_agent import BaseAgent, LLMProvider
from src.ai.gemini_integration import GeminiConnector
from src.ai.anthropic_integration import AnthropicConnector

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
            from src.ai.prompts import get_system_prompt
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
            
            # Only register image model for specialized image-related tasks
            # We don't register it by default for chat agent to avoid confusion
            # The image model will be registered when needed for image generation tasks
            logger.info("Skipping image model registration for general chat agent")
            
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
        
        # If enhanced mode is explicitly requested, use Pro model
        if use_enhanced_model:
            provider = self.get_filtered_provider(model_filter, lambda m: m.priority >= 5)
        else:
            # Use Chain of Thought to determine if we need Pro model
            provider = await self._choose_model_with_cot(message, model_filter)
        
        if not provider:
            return "I'm sorry, but I don't have text generation capabilities available right now."
        
        # Process the message with conversation history
        try:
            # Format conversation history for the provider
            formatted_history = self._format_conversation_history_for_provider(provider.model_name)
            
            # Check if the provider supports conversation_history parameter
            if hasattr(provider, 'supports_conversation_history') and provider.supports_conversation_history:
                # Generate response using the formatted history
                response = await provider.generate_text(
                    message, 
                    system_prompt=self.system_prompt,
                    conversation_history=formatted_history
                )
            else:
                # For providers that don't support conversation_history, use the system prompt with context
                context_prompt = self.system_prompt + "\n\nConversation context:\n"
                for msg in formatted_history[-5:]:  # Use last 5 messages as context
                    context_prompt += f"{msg['role']}: {msg['content']}\n"
                context_prompt += f"\nUser: {message}\nAssistant:"
                
                response = await provider.generate_text(
                    context_prompt,
                    system_prompt=None  # Already included in context_prompt
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
        
        # Always use the thinking-capable model for this mode
        # Note: For thinking mode, we don't do model selection as thinking is explicitly requested
        thinking_model = None
        for provider in self.llm_providers:
            if provider.is_initialized and provider.get_capabilities().get("thinking", False):
                thinking_model = provider
                break
        
        if not thinking_model:
            # Fallback to regular processing with pro model
            logger.warning("No thinking model available, falling back to regular pro model")
            return await self.process_message(message, use_enhanced_model=True)
            
        # Process with thinking model
        try:
            # Format conversation history for the provider
            formatted_history = self._format_conversation_history_for_provider(thinking_model.model_name)
            
            # Generate thinking response
            thinking_prompt = f"{self.system_prompt}\n\nThink step by step about the following question:\n{message}"
            
            # Check if the provider supports conversation_history parameter
            if hasattr(thinking_model, 'supports_conversation_history') and thinking_model.supports_conversation_history:
                response = await thinking_model.generate_text(
                    thinking_prompt,
                    conversation_history=formatted_history
                )
            else:
                # For providers that don't support conversation_history, use the system prompt with context
                context_prompt = thinking_prompt + "\n\nConversation context:\n"
                for msg in formatted_history[-5:]:  # Use last 5 messages as context
                    context_prompt += f"{msg['role']}: {msg['content']}\n"
                context_prompt += "\nThink step by step:"
                
                response = await thinking_model.generate_text(context_prompt)
            
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
            from src.services.message_storage import MessageStorageService
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
    
    async def _choose_model_with_cot(self, message: str, model_filter) -> Optional[LLMProvider]:
        """Choose appropriate model using Chain of Thought.
        
        This method uses a flash model to decide if a more powerful model is needed.
        
        Args:
            message: The user message.
            model_filter: Function to filter models by capability.
            
        Returns:
            Selected provider or None if no suitable provider found.
        """
        try:
            # Always first try to find a flash model for evaluation
            flash_model = self.get_filtered_provider(
                lambda m: m.get_capabilities().get("text_generation", False) and 
                          "flash" in m.model_name.lower()
            )
            
            # If no flash model available, fall back to any model
            if not flash_model:
                logger.warning("No flash model available for CoT model selection, using default provider")
                return self.get_filtered_provider(model_filter)
            
            # Create prompt for the flash model to evaluate complexity
            evaluation_prompt = f"""
            分析以下用户问题的复杂度，并判断是否需要更先进的AI模型回答：
            
            用户问题: {message}
            
            请考虑：
            1. 问题是否需要深度理解或复杂推理
            2. 回答是否需要专业知识或详细解释
            3. 上下文信息的复杂程度和数量
            4. 问题是否包含多个子问题或要求
            
            如果问题简单，只需输出: FLASH_SUFFICIENT
            如果问题需要深度思考或复杂推理，输出: NEED_PRO_MODEL
            
            只输出决定，不要解释理由:
            """
            
            # Get flash model's decision
            decision = await flash_model.generate_text(evaluation_prompt)
            logger.info(f"Model selection decision: {decision}")
            
            # Based on the decision, choose appropriate model
            if "NEED_PRO_MODEL" in decision:
                logger.info("Selected Pro model based on CoT decision")
                return self.get_filtered_provider(model_filter, lambda m: m.priority >= 5)
            else:
                logger.info("Selected Flash model based on CoT decision")
                return flash_model
                
        except Exception as e:
            logger.error(f"Error in CoT model selection: {e}, falling back to default")
            # On any error, fall back to default selection logic
            return self.get_filtered_provider(model_filter)
    
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
            from src.services.message_storage import MessageStorageService
            from src.services.event_bus import EventBus
            
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
