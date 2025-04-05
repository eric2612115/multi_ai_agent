"""Knowledge extraction service.

This module provides a service for extracting knowledge from text using the KnowledgeExtractor.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from forest.extraction import KnowledgeExtractor
from forest.models import KnowledgeExtractionResult
from common.exceptions import ExtractionError

logger = logging.getLogger(__name__)

class KnowledgeExtractionService:
    """Service for extracting knowledge from content."""
    
    def __init__(self, extractor: Optional[KnowledgeExtractor] = None):
        """Initialize the knowledge extraction service.
        
        Args:
            extractor: Optional knowledge extractor.
        """
        self.extractor = extractor or KnowledgeExtractor()
    
    async def extract_knowledge(self, content: str, user_id: str, 
                             metadata: Optional[Dict[str, Any]] = None) -> KnowledgeExtractionResult:
        """Extract knowledge from content.
        
        Args:
            content: The content to extract knowledge from.
            user_id: The user ID.
            metadata: Optional metadata.
            
        Returns:
            The extraction result.
            
        Raises:
            ExtractionError: If extraction fails.
        """
        try:
            # Prepare message object for the extractor
            message = {
                "_id": metadata.get("message_id", "generated_" + datetime.utcnow().isoformat()),
                "text": content,
                "user_id": user_id,
                **(metadata or {})
            }
            
            # Optional context if available in metadata
            context = metadata.get("context") if metadata else None
            
            # Extract knowledge
            result = await self.extractor.extract_knowledge(message, context)
            
            return result
            
        except Exception as e:
            logger.error(f"Knowledge extraction failed: {str(e)}")
            raise ExtractionError(f"Failed to extract knowledge: {str(e)}")

# Add the is_valid method as an extension to KnowledgeExtractionResult
def is_valid(self) -> bool:
    """Check if an extraction result is valid and useful.
    
    Returns:
        True if valid, False otherwise.
    """
    # Check if embedding is present
    if not self.embedding or len(self.embedding) == 0:
        return False
        
    # Check if we have entities or a summary
    if (not self.entities or len(self.entities) == 0) and not self.summary:
        return False
        
    return True

# Add the method to the class
KnowledgeExtractionResult.is_valid = is_valid
