"""REST API endpoints for reflection system.

This module provides API endpoints for the reflection system, 
allowing users to manage reflection cycles.
"""
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status

from src.forest.reflection.core import ReflectionSystem
from src.forest.models import ReflectionCycle, StringId
from src.api.rest.auth import get_current_user

router = APIRouter(prefix="/api/reflection", tags=["reflection"])
logger = logging.getLogger(__name__)

@router.post("/trigger", summary="Trigger a reflection cycle")
async def trigger_reflection(
    user_id: str = Depends(get_current_user),
    energy_budget: Optional[float] = Body(None, description="Optional energy budget for this cycle")
) -> Dict[str, Any]:
    """Trigger a reflection cycle manually.
    
    Returns:
        The reflection cycle ID or status
    """
    try:
        reflection_system = ReflectionSystem()
        
        # Start a reflection cycle
        cycle_id = await reflection_system.start_reflection_cycle(
            user_id=user_id,
            energy_budget=energy_budget,
            trigger_source="manual"
        )
        
        # Handle special cases
        if cycle_id == "disabled":
            return {
                "status": "error",
                "message": "Reflection is disabled",
                "cycle_id": None
            }
        elif cycle_id == "insufficient_nodes":
            return {
                "status": "error",
                "message": "Not enough nodes for reflection",
                "cycle_id": None
            }
            
        # Return the cycle ID
        return {
            "status": "success",
            "message": "Reflection cycle started",
            "cycle_id": cycle_id
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger reflection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger reflection: {str(e)}"
        )

@router.get("/cycles", summary="Get reflection cycles")
async def get_reflection_cycles(
    user_id: str = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of cycles to return"),
    status: Optional[str] = Query(None, description="Filter by status")
) -> List[Dict[str, Any]]:
    """Get reflection cycles for the current user.
    
    Returns:
        List of reflection cycles
    """
    try:
        reflection_system = ReflectionSystem()
        
        # Get cycles
        cycles = await reflection_system.get_user_reflection_cycles(
            user_id=user_id,
            limit=limit,
            status=status
        )
        
        return cycles
        
    except Exception as e:
        logger.error(f"Failed to get reflection cycles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reflection cycles: {str(e)}"
        )

@router.get("/cycles/{cycle_id}", summary="Get specific reflection cycle")
async def get_reflection_cycle(
    cycle_id: str = Path(..., description="The reflection cycle ID"),
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific reflection cycle.
    
    Returns:
        The reflection cycle data
    """
    try:
        reflection_system = ReflectionSystem()
        
        # Get the cycle
        cycle = await reflection_system.get_reflection_cycle(cycle_id)
        
        # Check if the cycle belongs to the user
        if cycle.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reflection cycle does not belong to this user"
            )
            
        return cycle
        
    except Exception as e:
        logger.error(f"Failed to get reflection cycle: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reflection cycle: {str(e)}"
        )

@router.delete("/cycles/{cycle_id}", summary="Cancel a reflection cycle")
async def cancel_reflection_cycle(
    cycle_id: str = Path(..., description="The reflection cycle ID"),
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cancel an ongoing reflection cycle.
    
    Returns:
        Status of the cancellation
    """
    try:
        reflection_system = ReflectionSystem()
        
        # First check if the cycle belongs to the user
        cycle = await reflection_system.get_reflection_cycle(cycle_id)
        if cycle.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reflection cycle does not belong to this user"
            )
            
        # Cancel the cycle
        success = await reflection_system.cancel_reflection_cycle(cycle_id)
        
        return {
            "status": "success" if success else "error",
            "message": "Reflection cycle cancelled" if success else "Failed to cancel cycle"
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel reflection cycle: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel reflection cycle: {str(e)}"
        )

@router.get("/gaps", summary="Get knowledge gaps")
async def get_knowledge_gaps(
    user_id: str = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of gaps to return"),
    status: Optional[str] = Query("open", description="Filter by status")
) -> List[Dict[str, Any]]:
    """Get knowledge gaps for the current user.
    
    Returns:
        List of knowledge gaps
    """
    try:
        # This requires accessing the database directly
        from src.storage.mongodb import MongoDBProvider
        storage = MongoDBProvider()
        
        # Build query
        query = {"user_id": user_id}
        if status:
            query["status"] = status
            
        # Get gaps
        gaps = await storage.find_documents(
            collection="knowledge_gaps",
            query=query,
            sort=[("severity", -1)],  # Most severe first
            limit=limit
        )
        
        return gaps
        
    except Exception as e:
        logger.error(f"Failed to get knowledge gaps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get knowledge gaps: {str(e)}"
        )
