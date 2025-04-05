"""Environment variable loader for AI API keys.

This module ensures environment variables are properly loaded from .env files.
"""
import os
import logging
from dotenv import load_dotenv, find_dotenv

# Setup logging
logger = logging.getLogger(__name__)

def load_environment_variables():
    """Load environment variables from .env file and map API keys as needed."""
    # Find and load the .env file
    env_file = find_dotenv()
    if env_file:
        logger.info(f"Loading environment variables from {env_file}")
        load_dotenv(env_file)
    else:
        logger.warning("No .env file found")

    # Check if we have the required API keys
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        # Map to the expected format
        os.environ["AI_GEMINI_API_KEY"] = gemini_key
        logger.info("Mapped GEMINI_API_KEY to AI_GEMINI_API_KEY")
    
    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    if claude_key:
        # Map to the expected format
        os.environ["AI_CLAUDE_API_KEY"] = claude_key
        logger.info("Mapped ANTHROPIC_API_KEY to AI_CLAUDE_API_KEY")
    
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    if firecrawl_key:
        # Map to the expected format
        os.environ["AI_FIRECRAWL_API_KEY"] = firecrawl_key
        logger.info("Mapped FIRECRAWL_API_KEY to AI_FIRECRAWL_API_KEY")

    # Set default model names if specified
    gemini_model = os.environ.get("GEMINI_STANDARD_MODEL")
    if gemini_model:
        os.environ["AI_GEMINI_MODEL_NAME"] = gemini_model
        logger.info(f"Set AI_GEMINI_MODEL_NAME to {gemini_model}")

    claude_model = os.environ.get("CLAUDE_STANDARD_MODEL")
    if claude_model:
        os.environ["AI_CLAUDE_MODEL_NAME"] = claude_model
        logger.info(f"Set AI_CLAUDE_MODEL_NAME to {claude_model}")

# Call this function when this module is imported
load_environment_variables()
