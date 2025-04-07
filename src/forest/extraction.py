"""Knowledge extraction module.

This module provides functionality for extracting knowledge from conversations
using LLMs.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from ai.base import TextGenerationModel, EmbeddingModel
from ai.factory import get_text_generation_model, get_embedding_model
from forest.models import KnowledgeExtractionResult
from common.exceptions import ExtractionError

logger = logging.getLogger(__name__)

class KnowledgeExtractor:
    """Knowledge extraction from text using AI models."""
    
    def __init__(self, 
                text_model: Optional[TextGenerationModel] = None,
                embedding_model: Optional[EmbeddingModel] = None):
        """Initialize the knowledge extractor.
        
        Args:
            text_model: Optional text generation model.
            embedding_model: Optional embedding model.
        """
        self.text_model = text_model
        self.embedding_model = embedding_model
        
        # 确保模型已经被导入
        try:
            import src.ai.gemini
            import src.ai.claude
        except ImportError as e:
            logger.warning(f"Failed to import AI models: {e}")
        
        # Lazy initialize models if not provided
        if self.text_model is None:
            try:
                # 先初始化一个Gemini实例而不是使用工厂方法（避免可能的循环依赖）
                from src.ai.gemini import GeminiAI
                self.text_model = GeminiAI()
                logger.info("Successfully initialized GeminiAI directly as text model")
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiAI directly: {str(e)}")
                # Try with Claude
                try:
                    from src.ai.claude import ClaudeModel
                    self.text_model = ClaudeModel()
                    logger.info("Successfully initialized ClaudeModel directly as text model")
                except Exception as e2:
                    logger.warning(f"Failed to initialize Claude directly: {str(e2)}")
                    self.text_model = None
            
        if self.embedding_model is None:
            try:
                # 如果text_model是GeminiAI，可以直接用作embedding模型
                if hasattr(self.text_model, 'generate_embedding'):
                    self.embedding_model = self.text_model
                    logger.info("Using text model for embeddings")
                else:
                    # 尝试直接创建嵌入模型
                    from src.ai.gemini import GeminiAI
                    self.embedding_model = GeminiAI()
                    logger.info("Successfully initialized GeminiAI directly as embedding model")
            except Exception as e:
                logger.warning(f"Failed to initialize embedding model directly: {str(e)}")
                self.embedding_model = None
    
    async def extract_knowledge(self, message: Dict[str, Any], 
                              context: Optional[List[Dict[str, Any]]] = None) -> KnowledgeExtractionResult:
        """Extract knowledge from a message.
        
        Args:
            message: The message to extract knowledge from.
            context: Optional conversation context.
            
        Returns:
            The extraction result.
            
        Raises:
            ExtractionError: If extraction fails.
        """
        message_id = message.get("_id", "")
        text = message.get("text", "")
        
        if not text:
            raise ExtractionError("Message text is empty")
        
        # Check if models are available
        if not self.text_model:
            logger.warning("No text model available for knowledge extraction")
            # Return a minimal result
            return KnowledgeExtractionResult(
                message_id=str(message_id),
                embedding=[0.0] * 768,  # Default embedding dimension
                entities=[],
                relationships=[],
                summary=text[:150] + "..." if len(text) > 150 else text,
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Extract knowledge
        try:
            logger.info(f"[{message_id}] Extracting knowledge from message")
            
            # Start the embedding generation asynchronously
            embedding_task = asyncio.create_task(self._get_embedding(text))
            
            # Try to extract entities and summary in a single call to reduce API usage
            try:
                entities_and_summary = await self._extract_entities_and_summary(text, context)
                entities = entities_and_summary.get("entities", [])
                summary = entities_and_summary.get("summary", "")
                
                # If extraction failed, fall back to separate calls
                if not entities or not summary:
                    logger.warning("Combined entity and summary extraction failed, falling back to separate calls")
                    entities = await self._extract_entities(text, context)
                    summary = await self._generate_summary(text, context)
            except Exception as e:
                logger.warning(f"Combined extraction failed: {str(e)}, falling back to separate calls")
                # Fall back to separate calls
                entities = await self._extract_entities(text, context)
                summary = await self._generate_summary(text, context)
            
            # Wait for embedding to complete
            extraction_result = await embedding_task
            
            # Extract relationships based on the entities
            relationships = await self._extract_relationships(text, entities, context)
            
            # Create the result
            result = KnowledgeExtractionResult(
                message_id=str(message_id),
                embedding=extraction_result,
                entities=entities,
                relationships=relationships,
                summary=summary,
                timestamp=datetime.utcnow().isoformat()
            )
            
            return result
        except Exception as e:
            logger.error(f"Knowledge extraction failed: {str(e)}")
            
            # 即使发生错误，也返回一个最小的结果而不是抛出异常
            # 生成一个默认的嵌入向量
            from common.config import get_settings
            settings = get_settings()
            default_embedding = [0.0] * settings.ai.embedding_dimensions
            
            # 生成一个最简单的结果
            result = KnowledgeExtractionResult(
                message_id=str(message_id),
                embedding=default_embedding,
                entities=[],
                relationships=[],
                summary=text[:150] + "..." if len(text) > 150 else text,
                timestamp=datetime.utcnow().isoformat()
            )
            
            return result
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for a text.
        
        Args:
            text: The text to embed.
            
        Returns:
            The embedding vector.
            
        Raises:
            ExtractionError: If embedding generation fails.
        """
        if self.embedding_model is None:
            # Return a zero embedding as a fallback
            from common.config import get_settings
            settings = get_settings()
            return [0.0] * settings.ai.embedding_dimensions
            
        try:
            embedding = await self.embedding_model.generate_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            # Return a zero embedding as a fallback
            from common.config import get_settings
            settings = get_settings()
            return [0.0] * settings.ai.embedding_dimensions
    
    async def _extract_entities(self, text: str, context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extract entities from text.
        
        Args:
            text: The text to extract entities from.
            context: Optional conversation context.
            
        Returns:
            List of extracted entities.
        """
        prompt = self._create_entity_extraction_prompt(text, context)
        
        # First try the text-based approach since function calling might not be available
        try:
            entities = await self._extract_entities_with_prompt(prompt)
            if entities:
                return entities
        except Exception as e:
            logger.warning(f"Entity extraction with prompt failed, trying fallback: {str(e)}")
        
        # Then try function calling as a fallback
        try:
            # Only attempt function calling if the model supports it
            if hasattr(self.text_model, "function_call"):
                # Check if we're using a thinking model that doesn't support function calling
                model_name = getattr(self.text_model, "_model_name", "") 
                if "thinking-exp" in model_name or "flash-thinking-exp" in model_name:
                    logger.warning(f"Model {model_name} doesn't support function calling, using text-based extraction only")
                    return []
                    
                entities = await self._extract_entities_with_function_calling(text, context)
                return entities
            else:
                # If we've reached here and no entities from prompt method, just return empty list
                return []
        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")
            return []  # Return empty list on failure
    
    async def _extract_entities_with_function_calling(self, text: str, 
                                                   context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extract entities using function calling.
        
        Args:
            text: The text to extract from.
            context: Optional conversation context.
            
        Returns:
            List of extracted entities.
            
        Raises:
            NotImplementedError: If function calling is not supported.
        """
        # Check if the model supports function calling
        if not hasattr(self.text_model, "function_call"):
            raise NotImplementedError("Function calling not supported by the model")
        
        # Define the function schema
        schema = {
            "name": "extract_entities",
            "description": "Extract entities from text",
            "parameters": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "description": "List of extracted entities",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "The extracted entity text"
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Entity type (keyword, entity, concept, question)",
                                    "enum": ["keyword", "entity", "concept", "question"]
                                },
                                "source_span": {
                                    "type": "array",
                                    "description": "Character position in the original text [start, end]",
                                    "items": {
                                        "type": "integer"
                                    }
                                }
                            },
                            "required": ["text", "type"]
                        }
                    }
                },
                "required": ["entities"]
            }
        }
        
        # Create prompt for function calling
        messages = []
        
        # Add context if provided
        if context:
            for msg in context[-3:]:  # Use last 3 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        
        # Add the main instruction
        messages.append({
            "role": "user",
            "content": f"""
            Extract key concepts, entities, and terms from the following text.
            Categorize each as keyword, entity, concept, or question.
            
            Text: {text}
            """
        })
        
        # Call the function
        result = await self.text_model.function_call(
            messages=messages,
            functions=[schema],
            function_call={"name": "extract_entities"}
        )
        
        # Extract and return the entities
        if "arguments" in result and result["arguments"] is not None:
            arguments = result["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            return arguments.get("entities", [])
        else:
            logger.warning("No valid arguments in function call result")
            return []
        
        return []
    
    async def _extract_entities_with_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract entities using a structured prompt.
        
        Args:
            prompt: The prompt to use for extraction.
            
        Returns:
            List of extracted entities.
        """
        try:
            response = await self.text_model.generate_text(prompt)
            
            # Try to parse JSON from the response
            try:
                # Look for JSON content
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].strip()
                else:
                    json_str = response.strip()
                
                # Handle possible truncated or malformed JSON
                if not json_str.strip().endswith('}'):
                    logger.warning("JSON response appears truncated, attempting repair")
                    json_str = json_str + "}]}}"  # Attempt to close any unclosed brackets
                    
                # Parse the JSON
                try:
                    result = json.loads(json_str)
                    return result.get("entities", []) or result.get("extractions", [])
                except json.JSONDecodeError as je:
                    # Log specific JSON error
                    logger.error(f"JSON decode error: {je}")
                    # Try a more lenient approach - extract what we can
                    import re
                    entity_pattern = r'\{\s*"text"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"'
                    matches = re.findall(entity_pattern, json_str)
                    if matches:
                        logger.info(f"Extracted {len(matches)} entities using regex fallback")
                        return [{
                            "text": match[0],
                            "type": match[1]
                        } for match in matches]
                    return []
            except Exception as e:
                logger.error(f"Failed to parse entity extraction response: {str(e)}")
                logger.debug(f"Response was: {response}")
                return []
        except Exception as e:
            logger.error(f"Failed to generate entity extraction response: {str(e)}")
            return []
    
    def _create_entity_extraction_prompt(self, text: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Create a prompt for entity extraction with strict guidelines.
        
        Args:
            text: The text to extract from.
            context: Optional conversation context.
            
        Returns:
            The formatted prompt.
        """
        prompt = """
        Extract the key concepts, entities, and terms from the following text. 
        Follow these STRICT rules for extraction:
        
        1. CONTENT LENGTH LIMITS:
           - Each extraction must be between 2-50 characters
           - Longer concepts should be condensed to their essential form
           - Avoid extracting full sentences or paragraphs
           
        2. FORMATTING:
           - Extract the base form of terms (singular nouns, verb infinitives)
           - Use standard capitalization (proper nouns capitalized, common nouns lowercase)
           - Do not include punctuation at the beginning or end of extractions
           
        3. QUALITY STANDARDS:
           - Focus on substantive, meaningful terms that represent distinct concepts
           - Avoid overly generic terms unless they're central to the topic
           - Deduplicate variations of the same concept
           - Maximum of 15 extractions per text
           
        Categorize each extraction as one of the following types:
        - keyword: Important terms or phrases (maximum 8)
        - entity: Named entities such as people, organizations, products, etc. (maximum 5)
        - concept: Abstract ideas or theoretical constructs (maximum 5)
        - question: Questions or inquiries that are present in the text (maximum 3)
        
        For each extraction, provide:
        1. The extracted text
        2. The type (keyword, entity, concept, or question)
        3. If possible, the character position in the original text (start and end indices)
        
        Text to analyze:
        """
        
        # Add context if provided
        if context and len(context) > 0:
            context_str = "\n\nConversation context:\n"
            for msg in context[-3:]:  # Use last 3 messages as context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_str += f"{role}: {content}\n"
            prompt += context_str
        
        prompt += f"\n\nText: {text}\n\n"
        prompt += """
        Provide the extractions in the following JSON format:
        {
            "entities": [
                {
                    "text": "extracted text",
                    "type": "keyword/entity/concept/question",
                    "source_span": [start_index, end_index]  // Optional
                },
                ...
            ]
        }
        
        Remember:
        - Limit to maximum 15 total extractions
        - Each extraction must be between 2-50 characters
        - Prioritize precision and relevance over quantity
        """
        
        return prompt
    
    async def _generate_summary(self, text: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a summary of the text.
        
        Args:
            text: The text to summarize.
            context: Optional conversation context.
            
        Returns:
            The summary.
        """
        prompt = self._create_summary_prompt(text, context)
        
        try:
            summary = await self.text_model.generate_text(prompt, max_tokens=150)
            return summary
        except Exception as e:
            logger.error(f"Failed to generate summary: {str(e)}")
            # Return a truncated version of the text as a fallback
            return text[:150] + "..." if len(text) > 150 else text
    
    def _create_summary_prompt(self, text: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Create a prompt for generating a standardized summary.
        
        Args:
            text: The text to summarize.
            context: Optional conversation context.
            
        Returns:
            The formatted prompt.
        """
        prompt = """
        Generate a concise, focused summary of the key information in the following text.
        
        STRICT FORMATTING REQUIREMENTS:
        1. Length: Exactly 1-2 sentences, maximum 280 characters total
        2. Style: Clear, factual, and objective - avoid subjective language
        3. Structure: Start with the main subject/topic, then add key details
        4. Focus: Capture the most important information, not peripheral details
        5. Language: Use present tense when possible
        6. Tone: Formal and neutral
        
        Do NOT:
        - Include personal opinions or evaluations
        - Use first-person language or rhetorical questions
        - Start with "This text..." or similar meta-descriptions
        - Include unnecessary context or background information
        - Add information not present in the original text
        
        Text to summarize:
        """
        
        # Add context if provided
        if context and len(context) > 0:
            context_str = "\n\nConversation context:\n"
            for msg in context[-3:]:  # Use last 3 messages as context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_str += f"{role}: {content}\n"
            prompt += context_str
        
        prompt += f"\n\nText: {text}\n\n"
        prompt += "Summary (1-2 sentences, max 280 characters): "
        
        return prompt
    
    async def _extract_relationships(self, text: str, entities: List[Dict[str, Any]], 
                                  context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extract relationships between entities.
        
        Args:
            text: The text to extract from.
            entities: The extracted entities.
            context: Optional conversation context.
            
        Returns:
            List of extracted relationships.
        """
        # Skip if there are no entities or only one entity
        if not entities or len(entities) < 2:
            return []
            
        prompt = self._create_relationship_prompt(text, entities, context)
        
        # First try the text-based approach since function calling might not be available
        try:
            relationships = await self._extract_relationships_with_prompt(prompt)
            if relationships:
                return relationships
        except Exception as e:
            logger.warning(f"Relationship extraction with prompt failed, trying fallback: {str(e)}")
        
        # Then try function calling as a fallback
        try:
            # Only attempt function calling if the model supports it
            if hasattr(self.text_model, "function_call"):
                # Check if we're using a thinking model that doesn't support function calling
                model_name = getattr(self.text_model, "_model_name", "") 
                if "thinking-exp" in model_name or "flash-thinking-exp" in model_name:
                    logger.warning(f"Model {model_name} doesn't support function calling, using text-based extraction only for relationships")
                    return []
                
                relationships = await self._extract_relationships_with_function_calling(text, entities, context)
                return relationships
            else:
                # If we've reached here and no relationships from prompt method, just return empty list
                return []
        except Exception as e:
            logger.error(f"Relationship extraction failed: {str(e)}")
            return []  # Return empty list on failure
    
    async def _extract_relationships_with_function_calling(self, text: str, entities: List[Dict[str, Any]],
                                                      context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extract relationships using function calling.
        
        Args:
            text: The text to extract from.
            entities: The extracted entities.
            context: Optional conversation context.
            
        Returns:
            List of extracted relationships.
            
        Raises:
            NotImplementedError: If function calling is not supported.
        """
        # Check if the model supports function calling
        if not hasattr(self.text_model, "function_call"):
            raise NotImplementedError("Function calling not supported by the model")
        
        # Define the function schema
        schema = {
            "name": "extract_relationships",
            "description": "Extract relationships between entities",
            "parameters": {
                "type": "object",
                "properties": {
                    "relationships": {
                        "type": "array",
                        "description": "List of extracted relationships",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {
                                    "type": "string",
                                    "description": "The source entity text"
                                },
                                "target": {
                                    "type": "string",
                                    "description": "The target entity text"
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Relationship type",
                                    "enum": ["relates_to", "extends", "branches_from", "cross_links", "causes", "explains"]
                                },
                                "strength": {
                                    "type": "number",
                                    "description": "Relationship strength (0.0 to 1.0)",
                                    "minimum": 0.0,
                                    "maximum": 1.0
                                },
                                "context": {
                                    "type": "string",
                                    "description": "Brief explanation of the relationship"
                                }
                            },
                            "required": ["source", "target", "type"]
                        }
                    }
                },
                "required": ["relationships"]
            }
        }
        
        # Prepare entity list
        entity_list = "\n".join([f"- {e['text']} (Type: {e['type']})" for e in entities])
        
        # Create prompt for function calling
        messages = []
        
        # Add context if provided
        if context:
            for msg in context[-2:]:  # Use last 2 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        
        # Add the main instruction
        messages.append({
            "role": "user",
            "content": f"""
            Identify relationships between the following entities extracted from the text:
            
            {entity_list}
            
            Original text: {text}
            """
        })
        
        # Call the function
        result = await self.text_model.function_call(
            messages=messages,
            functions=[schema],
            function_call={"name": "extract_relationships"}
        )
        
        # Extract and return the relationships
        if "arguments" in result and result["arguments"] is not None:
            arguments = result["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            return arguments.get("relationships", [])
        else:
            logger.warning("No valid arguments in function call result for relationships")
            return []
        
        return []
    
    async def _extract_relationships_with_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract relationships using a structured prompt.
        
        Args:
            prompt: The prompt to use for extraction.
            
        Returns:
            List of extracted relationships.
        """
        try:
            response = await self.text_model.generate_text(prompt, max_tokens=1024)
            
            # Try to parse JSON from the response
            try:
                # Look for JSON content
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].strip()
                else:
                    json_str = response.strip()
                    
                # Handle possible truncated or malformed JSON
                if not json_str.strip().endswith('}'):
                    logger.warning("JSON response appears truncated, attempting repair")
                    json_str = json_str + "}]}}"  # Attempt to close any unclosed brackets
                    
                # Parse the JSON
                try:
                    result = json.loads(json_str)
                    return result.get("relationships", [])
                except json.JSONDecodeError as je:
                    # Log specific JSON error
                    logger.error(f"JSON decode error: {je}")
                    # Try a more lenient approach - extract what we can
                    import re
                    relationship_pattern = r'\{\s*"source"\s*:\s*"([^"]+)"\s*,\s*"target"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"'
                    matches = re.findall(relationship_pattern, json_str)
                    if matches:
                        logger.info(f"Extracted {len(matches)} relationships using regex fallback")
                        return [{
                            "source": match[0],
                            "target": match[1],
                            "type": match[2],
                            "strength": 0.5,  # Default strength
                            "context": "Extracted from malformed JSON"
                        } for match in matches]
                    return []
            except Exception as e:
                logger.error(f"Failed to parse relationship extraction response: {str(e)}")
                logger.debug(f"Response was: {response}")
                return []
        except Exception as e:
            logger.error(f"Failed to generate relationship extraction response: {str(e)}")
            return []
    
    async def _extract_entities_and_summary(self, text: str, context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Extract entities and generate summary in a single call to reduce API usage.
        
        Args:
            text: The text to extract from.
            context: Optional conversation context.
            
        Returns:
            Dictionary with entities and summary.
        """
        prompt = """
        Analyze the following text and provide BOTH a concise summary AND key entity extractions.
        
        SUMMARY REQUIREMENTS:
        - Length: Exactly 1-2 sentences, maximum 280 characters total
        - Style: Clear, factual, and objective - avoid subjective language
        - Focus: Capture the most important information, not peripheral details
        - Language: Use present tense when possible
        - Tone: Formal and neutral
        
        ENTITY EXTRACTION REQUIREMENTS:
        - Each extraction must be between 2-50 characters
        - Categorize each as: keyword, entity, concept, or question
        - Maximum 15 extractions total
        - Focus on substantive, meaningful terms
        
        Text to analyze:
        """
        
        # Add context if provided
        if context and len(context) > 0:
            context_str = "\n\nConversation context:\n"
            for msg in context[-3:]:  # Use last 3 messages as context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_str += f"{role}: {content}\n"
            prompt += context_str
        
        prompt += f"\n\nText: {text}\n\n"
        prompt += """
        Provide the results in the following JSON format:
        {
            "summary": "Concise summary here",
            "entities": [
                {
                    "text": "extracted text",
                    "type": "keyword/entity/concept/question"
                },
                ...
            ]
        }
        """
        
        try:
            response = await self.text_model.generate_text(prompt)
            
            # Try to parse JSON from the response
            try:
                # Look for JSON content
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].strip()
                else:
                    json_str = response.strip()
                
                # Handle possible truncated or malformed JSON
                if not json_str.strip().endswith('}'):
                    logger.warning("JSON response appears truncated, attempting repair")
                    json_str = json_str + "}}"  # Attempt to close any unclosed brackets
                    
                # Parse the JSON
                result = json.loads(json_str)
                return result
            except Exception as e:
                logger.error(f"Failed to parse combined extraction response: {str(e)}")
                logger.debug(f"Response was: {response}")
                raise
        except Exception as e:
            logger.error(f"Failed to generate combined extraction response: {str(e)}")
            raise
    
    def _create_relationship_prompt(self, text: str, entities: List[Dict[str, Any]], 
                                 context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Create a prompt for relationship extraction.
        
        Args:
            text: The text to extract from.
            entities: The extracted entities.
            context: Optional conversation context.
            
        Returns:
            The formatted prompt.
        """
        entity_list = "\n".join([f"- {e['text']} (Type: {e['type']})" for e in entities])
        
        prompt = f"""
        Identify relationships between the following entities extracted from the text:
        
        {entity_list}
        
        For each relationship you identify, provide:
        1. The source entity
        2. The target entity
        3. The type of relationship:
           - relates_to: General relation
           - extends: Elaborates or builds upon
           - branches_from: Represents a new direction but related
           - cross_links: Connects seemingly unrelated concepts
           - causes: Indicates causation
           - explains: One concept explains another
        4. The strength of the relationship (0.0 to 1.0)
        5. A brief context describing the relationship
        
        Original text:
        {text}
        """
        
        # Add context if provided
        if context and len(context) > 0:
            context_str = "\n\nConversation context:\n"
            for msg in context[-3:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_str += f"{role}: {content}\n"
            prompt += context_str
        
        prompt += """
        Provide the relationships in the following JSON format:
        {
            "relationships": [
                {
                    "source": "source entity text",
                    "target": "target entity text",
                    "type": "relationship_type",
                    "strength": 0.8,
                    "context": "brief explanation of the relationship"
                },
                ...
            ]
        }
        """
        
        return prompt
