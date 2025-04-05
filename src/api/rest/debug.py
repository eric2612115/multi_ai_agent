"""
Debug API endpoints for system health checks and diagnostics
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from dependencies.mongodb import get_mongodb_provider

router = APIRouter(
    prefix="/api/debug",
    tags=["debug"],
    responses={404: {"description": "Not found"}}
)

@router.get("/mongodb/status", response_model=Dict[str, Any])
async def check_mongodb_status(mongodb=Depends(get_mongodb_provider)):
    """
    Check MongoDB connection status
    
    Returns:
        Dict with connection status and details
    """
    if not mongodb:
        raise HTTPException(status_code=500, detail="MongoDB provider not initialized")
    
    try:
        # Check connection by trying to run a simple command
        is_connected = await mongodb.is_connected()
        db_stats = await mongodb.get_database_stats() if is_connected else None
        
        return {
            "status": "connected" if is_connected else "disconnected",
            "client_info": str(mongodb.client) if mongodb.client else None,
            "database": mongodb.database_name,
            "stats": db_stats,
            "collections": await mongodb.list_collections() if is_connected else []
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking MongoDB status: {str(e)}"
        )
