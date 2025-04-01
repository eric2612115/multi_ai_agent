"""Tests for the Claude client."""
import os
import pytest
from dotenv import load_dotenv

from multi_ai_agent.clients import ClaudeClient

# Load environment variables
load_dotenv()

@pytest.fixture
def claude_client():
    """Create a Claude client for testing."""
    # Skip if no API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY environment variable not set")
    
    return ClaudeClient()

def test_generate_text(claude_client):
    """Test text generation."""
    response = claude_client.generate_text(
        "Write a short poem about artificial intelligence.",
        max_tokens=200
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    
def test_count_tokens(claude_client):
    """Test token counting."""
    count = claude_client.count_tokens(
        "This is a test sentence for counting tokens."
    )
    
    assert isinstance(count, int)
    assert count > 0
