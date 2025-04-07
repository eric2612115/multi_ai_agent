"""Console test for verifying the AI keys setup.

This script verifies that the AI keys are properly configured.
"""
import os
import sys
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Import the AI keys setup
import src.ai_keys_setup

# Import the settings
from src.common.config import get_settings

def test_ai_keys():
    """Test that AI keys are properly configured."""
    settings = get_settings()
    
    # Print the AI-related settings
    print("=== AI Settings ===")
    print(f"Default service: {settings.ai.default_service}")
    print(f"Max tokens: {settings.ai.max_tokens}")
    print(f"Enable advanced models: {settings.ai.enable_advanced_models}")
    print(f"Embedding dimensions: {settings.ai.embedding_dimensions}")
    
    # Check for Gemini API key
    if settings.ai.gemini_api_key:
        print(f"✅ Gemini API key: {'*' * len(settings.ai.gemini_api_key)}")
    else:
        print("❌ Gemini API key: Not configured")
    
    print(f"Gemini model name: {settings.ai.gemini_model_name}")
    print(f"Gemini embedding model: {settings.ai.gemini_embedding_model}")
    
    # Check for Claude API key
    if settings.ai.claude_api_key:
        print(f"✅ Claude API key: {'*' * len(settings.ai.claude_api_key)}")
    else:
        print("❌ Claude API key: Not configured")
    
    print(f"Claude model name: {settings.ai.claude_model_name}")
    print(f"Claude API version: {settings.ai.claude_api_version}")
    
    # Check for Firecrawl API key
    if settings.ai.firecrawl_api_key:
        print(f"✅ Firecrawl API key: {'*' * len(settings.ai.firecrawl_api_key)}")
    else:
        print("❌ Firecrawl API key: Not configured")
    
    print(f"Firecrawl API URL: {settings.ai.firecrawl_api_url}")
    
    # Check environment variables
    print("\n=== Environment Variables ===")
    for key in os.environ:
        if 'API_KEY' in key or 'GEMINI' in key or 'CLAUDE' in key or 'ANTHROPIC' in key or 'FIRECRAWL' in key:
            value = '*' * len(os.environ[key])
            print(f"{key}: {value}")

if __name__ == "__main__":
    test_ai_keys()
