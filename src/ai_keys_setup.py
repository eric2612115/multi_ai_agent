"""Environment variable adapter for AI keys.

This module maps existing environment variables to the format expected by the application.
"""
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)

def setup_ai_keys():
    """Set up AI keys by mapping existing environment variables to expected format."""
    # Map Gemini API key
    if os.environ.get('GEMINI_API_KEY') and not os.environ.get('AI_GEMINI_API_KEY'):
        os.environ['AI_GEMINI_API_KEY'] = os.environ.get('GEMINI_API_KEY')
        logger.info("Mapped GEMINI_API_KEY to AI_GEMINI_API_KEY")

    # Map Claude API key
    if os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('AI_CLAUDE_API_KEY'):
        os.environ['AI_CLAUDE_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY')
        logger.info("Mapped ANTHROPIC_API_KEY to AI_CLAUDE_API_KEY")

    # Map Firecrawl API key
    if os.environ.get('FIRECRAWL_API_KEY') and not os.environ.get('AI_FIRECRAWL_API_KEY'):
        os.environ['AI_FIRECRAWL_API_KEY'] = os.environ.get('FIRECRAWL_API_KEY')
        logger.info("Mapped FIRECRAWL_API_KEY to AI_FIRECRAWL_API_KEY")

    # Set model names based on environment variables if they exist
    if os.environ.get('GEMINI_STANDARD_MODEL'):
        os.environ['AI_GEMINI_MODEL_NAME'] = os.environ.get('GEMINI_STANDARD_MODEL')
        logger.info(f"Set AI_GEMINI_MODEL_NAME to {os.environ.get('GEMINI_STANDARD_MODEL')}")
    elif not os.environ.get('AI_GEMINI_MODEL_NAME'):
        os.environ['AI_GEMINI_MODEL_NAME'] = 'gemini-pro'
        logger.info("Set default AI_GEMINI_MODEL_NAME to gemini-pro")

    # Check if AI keys are now available
    if os.environ.get('AI_GEMINI_API_KEY'):
        logger.info("Gemini API key is configured")
    else:
        logger.warning("Gemini API key is not configured")

    if os.environ.get('AI_CLAUDE_API_KEY'):
        logger.info("Claude API key is configured")
    else:
        logger.warning("Claude API key is not configured")

    if os.environ.get('AI_FIRECRAWL_API_KEY'):
        logger.info("Firecrawl API key is configured")
    else:
        logger.warning("Firecrawl API key is not configured")

# Execute the setup when the module is imported
setup_ai_keys()
