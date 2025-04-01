"""Main MCP server implementation for the Multi-AI Agent."""
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context

from multi_ai_agent.clients import GeminiClient, ClaudeClient, FirecrawlClient

# Load environment variables
load_dotenv()

# Initialize the MCP server
mcp = FastMCP("Multi-AI Agent")


@dataclass
class AppContext:
    """Application context shared between tools."""
    gemini: GeminiClient
    claude: ClaudeClient
    firecrawl: FirecrawlClient
    config: Dict[str, Any]


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context."""
    # Initialize on startup
    gemini = GeminiClient()
    claude = ClaudeClient()
    firecrawl = FirecrawlClient()
    
    # Set up the web extraction service
    firecrawl.set_extraction_service(gemini_client=gemini, claude_client=claude)
    
    config = {
        "default_service": os.environ.get("DEFAULT_AI_SERVICE", "gemini"),
        "max_tokens": int(os.environ.get("MAX_TOKENS", 1024)),
        "advanced_models_enabled": os.environ.get("ENABLE_ADVANCED_MODELS", "false").lower() == "true",
    }
    
    try:
        yield AppContext(
            gemini=gemini,
            claude=claude,
            firecrawl=firecrawl,
            config=config
        )
    finally:
        # Cleanup on shutdown (if needed)
        pass


# Pass lifespan to server
mcp = FastMCP("Multi-AI Agent", lifespan=app_lifespan)


# === AI TEXT GENERATION TOOLS ===

@mcp.tool()
def generate_text(prompt: str, model: Optional[str] = None, service: Optional[str] = None, 
                  max_tokens: Optional[int] = None, ctx: Context = None) -> str:
    """Generate text using AI.
    
    Args:
        prompt: The prompt to generate text from.
        model: The specific model to use (e.g., "gemini-2.0-flash" or "claude-3-5-sonnet-20240620").
        service: The AI service to use ("gemini" or "claude"). Defaults to configured default.
        max_tokens: The maximum number of tokens to generate. Defaults to configured default.
        ctx: The MCP context.
        
    Returns:
        The generated text.
    """
    app_ctx = ctx.request_context.lifespan_context
    
    # Determine which service to use
    if not service:
        service = app_ctx.config["default_service"]
    
    max_tokens = max_tokens or app_ctx.config["max_tokens"]
    
    ctx.info(f"Generating text using {service} service")
    
    if service.lower() == "gemini":
        client = app_ctx.gemini
        if model:
            client.set_model(model)
        return client.generate_text(prompt, max_tokens)
    elif service.lower() == "claude":
        client = app_ctx.claude
        if model:
            client.set_model(model)
        return client.generate_text(prompt, max_tokens)
    else:
        raise ValueError(f"Unsupported service: {service}")


@mcp.tool()
def search_web(query: str, ctx: Context = None) -> str:
    """Search the web using Gemini's search capabilities.
    
    Args:
        query: The search query.
        ctx: The MCP context.
        
    Returns:
        The search results.
    """
    app_ctx = ctx.request_context.lifespan_context
    ctx.info(f"Searching the web for: {query}")
    return app_ctx.gemini.search_web(query)


@mcp.tool()
def count_tokens(text: str, ctx: Context = None) -> int:
    """Count the number of tokens in a text using Claude.
    
    Args:
        text: The text to count tokens for.
        ctx: The MCP context.
        
    Returns:
        The token count.
    """
    app_ctx = ctx.request_context.lifespan_context
    return app_ctx.claude.count_tokens(text)


# === BASIC WEB SCRAPING TOOLS ===

@mcp.tool()
def scrape_url(url: str, formats: List[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """Scrape a URL using Firecrawl.
    
    Args:
        url: The URL to scrape.
        formats: The formats to return (e.g., ["markdown", "html"]). Defaults to ["markdown"].
        ctx: The MCP context.
        
    Returns:
        The scraped content.
    """
    app_ctx = ctx.request_context.lifespan_context
    ctx.info(f"Scraping URL: {url}")
    return app_ctx.firecrawl.scrape_url(url, formats)


@mcp.tool()
def map_website(url: str, search: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """Map a website to get its structure.
    
    Args:
        url: The URL to map.
        search: Optional search term to filter URLs.
        ctx: The MCP context.
        
    Returns:
        The site map.
    """
    app_ctx = ctx.request_context.lifespan_context
    ctx.info(f"Mapping website: {url}")
    return app_ctx.firecrawl.map_url(url, search)


# === ADVANCED WEB EXTRACTION TOOLS ===

@mcp.tool()
def smart_extract_from_website(
    url: str, 
    objective: str, 
    use_advanced_model: bool = False,
    ctx: Context = None
) -> Dict[str, Any]:
    """Extract information from a website based on a specific objective.
    
    This tool uses AI to find relevant pages on a website and extract
    information that matches your objective.
    
    Args:
        url: The website URL to analyze.
        objective: What information you want to find (be specific).
        use_advanced_model: Whether to use advanced (more expensive) AI models for better results.
        ctx: The MCP context.
        
    Returns:
        Extracted information or error message.
    """
    app_ctx = ctx.request_context.lifespan_context
    
    # Check if advanced models are enabled if requested
    if use_advanced_model and not app_ctx.config["advanced_models_enabled"]:
        ctx.info("Advanced models are disabled in configuration. Using standard models.")
        use_advanced_model = False
    
    ctx.info(f"Extracting information from {url} with objective: {objective}")
    
    result = app_ctx.firecrawl.smart_extract(
        url=url,
        objective=objective,
        use_advanced_model=use_advanced_model
    )
    
    if not result:
        return {
            "success": False,
            "message": "Could not find information matching your objective. Try refining your objective or using a different website."
        }
    
    return {
        "success": True,
        "data": result,
        "message": "Successfully extracted information."
    }


@mcp.tool()
def advanced_extract_from_urls(
    urls: List[str],
    objective: str,
    entity: Optional[str] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Perform advanced extraction from specific URLs using Firecrawl's extract API.
    
    This tool is more powerful but uses more resources. It works best when you
    already know which URLs contain the information you want.
    
    Args:
        urls: List of URLs to extract information from.
        objective: What information you want to extract (be specific).
        entity: Optional entity name for context (e.g., company name).
        ctx: The MCP context.
        
    Returns:
        Extracted structured information or error message.
    """
    app_ctx = ctx.request_context.lifespan_context
    
    # Check if advanced models are enabled
    if not app_ctx.config["advanced_models_enabled"]:
        return {
            "success": False,
            "message": "Advanced extraction is disabled in configuration. Enable ENABLE_ADVANCED_MODELS in .env file."
        }
    
    ctx.info(f"Performing advanced extraction from {len(urls)} URLs")
    
    result = app_ctx.firecrawl.advanced_extract(
        urls=urls,
        prompt=objective,
        entity=entity
    )
    
    if not result:
        return {
            "success": False,
            "message": "Advanced extraction failed. Check your URLs and objective or try again later."
        }
    
    return {
        "success": True,
        "data": result,
        "message": "Successfully extracted information."
    }


# === CONFIGURATION RESOURCES ===

@mcp.resource("config://services")
def get_services() -> str:
    """Get information about the available AI services."""
    return """
    Available AI Services:
    
    1. Gemini (Google)
       - Default model: gemini-2.0-flash
       - Capabilities: Text generation, Web search
       
    2. Claude (Anthropic)
       - Default model: claude-3-5-sonnet-20240620
       - Capabilities: Text generation, Token counting
       
    3. Firecrawl
       - Capabilities: Web scraping, Website mapping, Information extraction
    """


@mcp.resource("config://extraction-capabilities")
def get_extraction_capabilities(ctx: Context = None) -> str:
    """Get information about the available web extraction capabilities."""
    app_ctx = ctx.request_context.lifespan_context
    advanced_models_enabled = app_ctx.config["advanced_models_enabled"]
    
    return f"""
    Web Extraction Capabilities:
    
    1. Basic Web Scraping
       - Scrape a single URL to get its content in markdown or HTML format
       - Map a website to discover its structure and links
       
    2. Smart Extraction
       - Find relevant pages on a website based on your objective
       - Extract specific information matching your criteria
       - Process content intelligently using AI
       
    3. Advanced Extraction {"(ENABLED)" if advanced_models_enabled else "(DISABLED)"}
       - More powerful extraction with Gemini Pro models
       - Process PDFs and images to extract relevant content
       - Generate structured data from multiple sources
       
    Note: Advanced extraction features use more expensive AI models and are
    {"enabled" if advanced_models_enabled else "currently disabled. To enable them, set ENABLE_ADVANCED_MODELS=true in your .env file."}.
    """


@mcp.resource("config://default")
def get_default_config(ctx: Context = None) -> str:
    """Get the current default configuration."""
    app_ctx = ctx.request_context.lifespan_context
    
    return f"""
    Current Default Configuration:
    
    - Default AI service: {app_ctx.config['default_service']}
    - Max tokens: {app_ctx.config['max_tokens']}
    - Advanced models: {"Enabled" if app_ctx.config['advanced_models_enabled'] else "Disabled"}
    """


@mcp.prompt()
def search_and_generate(query: str) -> str:
    """Create a prompt to search the web and generate a response."""
    return f"""
    Please search the web for information about: {query}
    
    Then, generate a comprehensive response based on the search results.
    """


@mcp.prompt()
def extract_website_info(url: str, objective: str) -> str:
    """Create a prompt to extract specific information from a website."""
    return f"""
    Please extract information from the website: {url}
    
    I need to find: {objective}
    
    First, map the website to find relevant pages.
    Then, analyze those pages to extract the specific information I need.
    """


if __name__ == "__main__":
    mcp.run()
