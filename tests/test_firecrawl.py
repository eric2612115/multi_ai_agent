"""Tests for the Firecrawl client."""
import os
import pytest
from dotenv import load_dotenv

from multi_ai_agent.clients import FirecrawlClient

# Load environment variables
load_dotenv()

@pytest.fixture
def firecrawl_client():
    """Create a Firecrawl client for testing."""
    # Skip if no API key
    if not os.environ.get("FIRECRAWL_API_KEY"):
        pytest.skip("FIRECRAWL_API_KEY environment variable not set")
    
    return FirecrawlClient()

def test_scrape_url(firecrawl_client):
    """Test URL scraping."""
    result = firecrawl_client.scrape_url(
        "https://modelcontextprotocol.io/",
        formats=["markdown"]
    )
    
    assert isinstance(result, dict)
    assert "formats" in result
    assert "markdown" in result["formats"]
    
def test_map_url(firecrawl_client):
    """Test website mapping."""
    result = firecrawl_client.map_url(
        "https://modelcontextprotocol.io/"
    )
    
    assert isinstance(result, dict)
    assert "urls" in result
    assert len(result["urls"]) > 0
