"""Prompt templates for AI models.

This module provides centralized management of prompt templates for AI models.
Templates can be composed and customized for different use cases.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# Base system prompts
SYSTEM_PROMPTS = {
    "knowledge_forest_assistant": """
    You are the assistant for AI Knowledge Forest, an intelligent system specialized in organizing and managing knowledge.
    You can:
    - Help users build and manage knowledge graphs
    - Answer questions and automatically integrate answers into the knowledge network
    - Identify connections between concepts and establish links
    - Summarize complex information and transform it into structured knowledge
    
    When users ask questions, you analyze the problem, provide helpful answers, and automatically add important concepts to their knowledge forest.
    If users ask who you are or what you can do, introduce yourself as the AI Knowledge Forest assistant, rather than just discussing the base model.
    Your main goal is to help users organize and expand their knowledge network.
    """,
    
    "knowledge_extraction": """
    You are a knowledge extraction expert, skilled at identifying key concepts, entities, and relationships in text.
    Focus on extracting:
    - Main concepts and ideas (abstract concepts)
    - Named entities (people, organizations, locations, products)
    - Key terms and keywords
    - Relationships between concepts
    
    Organize the extracted knowledge in a structured way that can be used to build a knowledge graph.
    """
}

# Task-specific prompt templates
PROMPT_TEMPLATES = {
    "extract_concepts": """
    Extract the key concepts, entities, and terms from the following text.
    Categorize each extraction as one of the following types:
    - keyword: Important terms or phrases
    - entity: Named entities such as people, organizations, products, etc.
    - concept: Abstract ideas or theoretical constructs
    - question: Questions or inquiries that are present in the text
    
    Text to analyze:
    {text}
    
    Format your response as a JSON object with an "entities" array:
    {{
        "entities": [
            {{
                "text": "extracted text",
                "type": "keyword/entity/concept/question"
            }},
            ...
        ]
    }}
    """,
    
    "extract_relationships": """
    Identify relationships between the following entities extracted from text:
    
    {entity_list}
    
    Original text:
    {text}
    
    For each relationship, specify:
    1. Source entity
    2. Target entity
    3. Relationship type (relates_to, extends, branches_from, cross_links, causes, explains)
    4. Strength (0.0 to 1.0)
    5. Brief context
    
    Format your response as JSON:
    {{
        "relationships": [
            {{
                "source": "source entity",
                "target": "target entity",
                "type": "relationship_type",
                "strength": 0.8,
                "context": "explanation"
            }},
            ...
        ]
    }}
    """,
    
    "summarize_content": """
    Generate a concise summary (1-2 sentences) of the key information in the following text.
    Focus on the main points, ideas, or questions.
    
    Text to summarize:
    {text}
    """,
    
    "placement_decision": """
    Determine how to place the following new knowledge in an existing knowledge graph.
    
    New knowledge:
    {extraction_result}
    
    Existing similar nodes:
    {similar_nodes}
    
    Current topic clusters:
    {topic_clusters}
    
    Decide between:
    1. Create new root node (for brand new topics)
    2. Create child node (for extending existing topics)
    3. Update existing node (for additional information about existing nodes)
    
    Format your response as JSON:
    {{
        "decision": "create_new|create_child|update_existing",
        "reason": "explanation for decision",
        "parent_node_id": "id if creating child or updating existing",
        "relationship_type": "relationship type if creating child"
    }}
    """
}

def get_system_prompt(prompt_key: str) -> str:
    """Get a system prompt by key.
    
    Args:
        prompt_key: The prompt key.
        
    Returns:
        The system prompt or a default prompt if not found.
    """
    return SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["knowledge_forest_assistant"])

def get_prompt_template(template_key: str) -> str:
    """Get a prompt template by key.
    
    Args:
        template_key: The template key.
        
    Returns:
        The prompt template or an empty string if not found.
    """
    return PROMPT_TEMPLATES.get(template_key, "")

def format_prompt(template_key: str, **kwargs) -> str:
    """Format a prompt template with the provided variables.
    
    Args:
        template_key: The template key.
        **kwargs: Variables to format the template with.
        
    Returns:
        The formatted prompt.
    """
    template = get_prompt_template(template_key)
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing variable in prompt template {template_key}: {e}")
        return template
    except Exception as e:
        logger.error(f"Error formatting prompt template {template_key}: {e}")
        return template

def combine_prompts(system_prompt_key: str, template_key: str, **kwargs) -> str:
    """Combine a system prompt and a formatted template.
    
    Args:
        system_prompt_key: The system prompt key.
        template_key: The template key.
        **kwargs: Variables to format the template with.
        
    Returns:
        The combined prompt.
    """
    system_prompt = get_system_prompt(system_prompt_key)
    formatted_template = format_prompt(template_key, **kwargs)
    
    return f"{system_prompt}\n\n{formatted_template}"
