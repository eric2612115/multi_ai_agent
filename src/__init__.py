"""Multi-AI Agent System with Knowledge Forest.

This is a modular system that integrates multiple AI services with knowledge
organization capabilities. It provides abstractions for AI models, storage,
and knowledge management.
"""

__version__ = "2.0.0"

# Convenience imports for the most commonly used functionality
from src.ai.factory import (
    get_ai_model,
    get_text_generation_model,
    get_embedding_model, 
    get_search_model,
    get_web_extraction_model
)

from src.forest import (
    init_knowledge_forest,
    get_knowledge_extractor,
    get_knowledge_processor,
    get_graph_manager
)

from src.storage import (
    get_document_storage,
    get_vector_storage,
    get_cache_storage,
    get_message_queue
)

from src.common.config import get_settings

# Initialize logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

__all__ = [
    # Version
    "__version__",
    
    # AI factory functions
    "get_ai_model",
    "get_text_generation_model",
    "get_embedding_model",
    "get_search_model",
    "get_web_extraction_model",
    
    # Forest functions
    "init_knowledge_forest",
    "get_knowledge_extractor",
    "get_knowledge_processor",
    "get_graph_manager",
    
    # Storage functions
    "get_document_storage",
    "get_vector_storage",
    "get_cache_storage",
    "get_message_queue",
    
    # Config
    "get_settings"
]
