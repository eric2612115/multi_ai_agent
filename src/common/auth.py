"""Authentication utilities with disabled verification for testing.

This module provides functionality for user authentication and authorization.
All authentication has been temporarily disabled for testing purposes.
"""
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from bson import ObjectId

from src.common.config import get_settings

# Get settings
settings = get_settings()

# Setup logging
logger = logging.getLogger(__name__)

# Setup OAuth2 - use a dummy endpoint that doesn't require actual authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# User model
class User(BaseModel):
    """User model."""
    
    id: Union[str, ObjectId] = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="Email address")
    disabled: Optional[bool] = Field(False, description="Whether the user is disabled")
    
    class Config:
        arbitrary_types_allowed = True

# Token models
class Token(BaseModel):
    """Token model."""
    
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Token data model."""
    
    username: Optional[str] = None
    id: Optional[str] = None

# Functions for token creation and validation
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token.
    
    Args:
        data: The data to encode in the token.
        expires_delta: Optional expiration time.
        
    Returns:
        The encoded JWT token.
    """
    # Just return a dummy token
    return "dummy_token_for_testing"

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> User:
    """Get the current user from a token.
    
    THIS FUNCTION HAS BEEN MODIFIED FOR TESTING TO ALWAYS RETURN A TEST USER.
    
    Args:
        token: The JWT token (ignored).
        
    Returns:
        A test user.
    """
    # Always return a default test user
    return User(
        id="user123",
        username="user123",
        email="user@example.com"
    )

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[User]:
    """Get the current user from a token, or None if no valid token is provided.
    
    Args:
        token: The JWT token.
        
    Returns:
        The current user, or None.
    """
    # Always return a default test user
    return await get_current_user()

async def get_user_from_token(token: str) -> Optional[User]:
    """Get a user from a token.
    
    Args:
        token: The JWT token.
        
    Returns:
        The user, or None if the token is invalid.
    """
    # Always return a default test user
    return User(
        id="user123",
        username="user123",
        email="user@example.com"
    )
