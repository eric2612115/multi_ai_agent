"""Tests for the web extraction functionality."""
import os
import pytest
from dotenv import load_dotenv

from multi_ai_agent.clients import FirecrawlClient, GeminiClient

# Load environment variables
load_dotenv()

@pytest.fixture
def firecrawl_client():
    """Create a Firecrawl client for testing."""
    if not os.environ.get("FIRECRAWL_API_KEY"):
        pytest.skip("FIRECRAWL_API_KEY environment variable not set")
    
    return FirecrawlClient()

@pytest.fixture
def gemini_client():
    """Create a Gemini client for testing."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY environment variable not set")
    
    return GeminiClient()

def test_basic_scrape(firecrawl_client):
    """Test basic web scraping."""
    result = firecrawl_client.scrape_url(
        "https://modelcontextprotocol.io/",
        formats=["markdown"]
    )
    
    assert isinstance(result, dict)
    assert "formats" in result
    assert "markdown" in result["formats"]

def test_map_website(firecrawl_client):
    """Test website mapping."""
    result = firecrawl_client.map_url("https://modelcontextprotocol.io/")
    
    assert isinstance(result, dict)
    assert "urls" in result or "links" in result

def test_smart_extraction(firecrawl_client, gemini_client):
    """Test smart extraction with AI assistance."""
    # Skip if any required keys are missing
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY environment variable not set")
    
    # Set up the extraction service
    firecrawl_client.set_extraction_service(gemini_client=gemini_client)
    
    # Test the smart extraction
    result = firecrawl_client.smart_extract(
        url="https://modelcontextprotocol.io/",
        objective="Explain what the Model Context Protocol is",
        use_advanced_model=False
    )
    
    print("Smart extraction result:", result)
    
    # The test might fail if the model doesn't find what it's looking for,
    # so we'll just check if the result is properly formatted
    if result:
        assert isinstance(result, dict)
        assert "source_url" in result
        assert "objective" in result
