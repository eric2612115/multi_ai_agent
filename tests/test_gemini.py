"""Tests for the Gemini client."""
import os
import pytest
from dotenv import load_dotenv

from multi_ai_agent.clients import GeminiClient

# Load environment variables
load_dotenv()

@pytest.fixture
def gemini_client():
    """Create a Gemini client for testing."""
    # Skip if no API key
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY environment variable not set")
    
    return GeminiClient()

def test_generate_text(gemini_client):
    """Test text generation."""
    response = gemini_client.generate_text(
        "Write a short poem about artificial intelligence.",
        max_tokens=200
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    
def test_search_web(gemini_client):
    """Test web search."""
    response = gemini_client.search_web(
        "What is the Model Context Protocol?"
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
