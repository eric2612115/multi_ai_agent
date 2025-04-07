"""Knowledge distillation API endpoints.

This module provides REST API endpoints for knowledge distillation and extraction.
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status

from src.common.auth import get_current_user, User
from src.forest.extraction_distiller import KnowledgeDistiller
from src.common.exceptions import ExtractionError

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/knowledge/distill", tags=["knowledge-distillation"])

# Initialize distiller
knowledge_distiller = KnowledgeDistiller()

@router.post("/principles/{topic_id}")
async def distill_principles(
    topic_id: str = Path(..., description="The topic ID to distill principles from"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Distill core principles from a topic.
    
    Args:
        topic_id: The topic ID to distill principles from.
        current_user: The current authenticated user.
        
    Returns:
        Dictionary with distilled principles info.
        
    Raises:
        HTTPException: If distillation fails.
    """
    try:
        principles = await knowledge_distiller.distill_core_principles(current_user.id, topic_id)
        
        return {
            "status": "success",
            "principles_count": len(principles),
            "principles": principles
        }
    except ExtractionError as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Distillation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during distillation"
        )

@router.post("/cross-domain")
async def extract_cross_domain_insights(
    topic_ids: List[str] = Body(..., embed=True, description="List of topic IDs to extract cross-domain insights from"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Extract cross-domain insights from multiple topics.
    
    Args:
        topic_ids: List of topic IDs to extract insights from.
        current_user: The current authenticated user.
        
    Returns:
        Dictionary with extracted insights info.
        
    Raises:
        HTTPException: If extraction fails.
    """
    if len(topic_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two topics are required for cross-domain insights"
        )
    
    try:
        insights = await knowledge_distiller.extract_cross_domain_insights(current_user.id, topic_ids)
        
        return {
            "status": "success",
            "insights_count": len(insights),
            "insights": insights
        }
    except ExtractionError as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cross-domain extraction failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during extraction"
        )

@router.post("/enhance/{node_id}")
async def enhance_node_explanation(
    node_id: str = Path(..., description="The node ID to enhance"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enhance a node's explanation.
    
    Args:
        node_id: The node ID to enhance.
        current_user: The current authenticated user.
        
    Returns:
        Dictionary with enhanced node info.
        
    Raises:
        HTTPException: If enhancement fails.
    """
    try:
        enhanced_node = await knowledge_distiller.enhance_node_explanation(current_user.id, node_id)
        
        return {
            "status": "success",
            "node": enhanced_node
        }
    except ExtractionError as e:
        logger.error(f"Enhancement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enhancement failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during enhancement"
        )