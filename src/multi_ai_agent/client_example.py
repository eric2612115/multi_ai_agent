"""Example client for the Multi-AI Agent MCP server."""
import asyncio
import os
import sys
import json
from typing import Optional, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def get_session():
    """Get a session with the MCP server."""
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="python",  # Executable
        args=["-m", "multi_ai_agent.main"],  # Run the main module
        env=None,  # Use current environment
    )
    
    read, write = await stdio_client(server_params).__aenter__()
    session = await ClientSession(read, write).__aenter__()
    
    # Initialize the connection
    await session.initialize()
    
    return session, read, write


async def close_session(session, read, write):
    """Close the session with the MCP server."""
    await session.__aexit__(None, None, None)
    await stdio_client(None).__aexit__(None, None, None)


async def run_generate_text(prompt, service=None, model=None):
    """Run the generate_text tool."""
    session, read, write = await get_session()
    
    try:
        print(f"Generating text for prompt: {prompt}")
        args = {"prompt": prompt}
        if service:
            args["service"] = service
        if model:
            args["model"] = model
            
        result = await session.call_tool("generate_text", arguments=args)
        print("\nGenerated text:")
        print(result)
    finally:
        await close_session(session, read, write)


async def run_scrape_url(url):
    """Run the scrape_url tool."""
    session, read, write = await get_session()
    
    try:
        print(f"Scraping URL: {url}")
        result = await session.call_tool(
            "scrape_url", 
            arguments={
                "url": url,
                "formats": ["markdown"]
            }
        )
        
        if isinstance(result, dict) and "formats" in result and "markdown" in result["formats"]:
            markdown = result["formats"]["markdown"]
            print(f"\nScraped content ({len(markdown)} characters):")
            # Print first 500 characters as preview
            print(markdown[:500] + "..." if len(markdown) > 500 else markdown)
        else:
            print("\nScraped content:")
            print(result)
    finally:
        await close_session(session, read, write)


async def run_search_web(query):
    """Run the search_web tool."""
    session, read, write = await get_session()
    
    try:
        print(f"Searching the web for: {query}")
        result = await session.call_tool("search_web", arguments={"query": query})
        print("\nSearch results:")
        print(result)
    finally:
        await close_session(session, read, write)


async def run_smart_extract(url, objective, use_advanced_model=False):
    """Run the smart_extract_from_website tool."""
    session, read, write = await get_session()
    
    try:
        print(f"Extracting information from: {url}")
        print(f"Objective: {objective}")
        print(f"Using advanced models: {use_advanced_model}")
        
        result = await session.call_tool(
            "smart_extract_from_website", 
            arguments={
                "url": url,
                "objective": objective,
                "use_advanced_model": use_advanced_model
            }
        )
        
        print("\nExtraction result:")
        if isinstance(result, dict):
            print(f"Success: {result.get('success', False)}")
            print(f"Message: {result.get('message', 'No message')}")
            
            if result.get('data'):
                print("\nExtracted data:")
                print(json.dumps(result['data'], indent=2))
        else:
            print(result)
    finally:
        await close_session(session, read, write)


async def run_advanced_extract(urls, objective, entity=None):
    """Run the advanced_extract_from_urls tool."""
    session, read, write = await get_session()
    
    try:
        print(f"Advanced extraction from {len(urls)} URLs")
        print(f"Objective: {objective}")
        if entity:
            print(f"Entity: {entity}")
        
        args = {
            "urls": urls,
            "objective": objective
        }
        
        if entity:
            args["entity"] = entity
            
        result = await session.call_tool("advanced_extract_from_urls", arguments=args)
        
        print("\nAdvanced extraction result:")
        if isinstance(result, dict):
            print(f"Success: {result.get('success', False)}")
            print(f"Message: {result.get('message', 'No message')}")
            
            if result.get('data'):
                print("\nExtracted data:")
                print(json.dumps(result['data'], indent=2))
        else:
            print(result)
    finally:
        await close_session(session, read, write)


async def run_demo():
    """Run a demonstration of the client capabilities."""
    session, read, write = await get_session()
    
    try:
        print("Connected to Multi-AI Agent")
        
        # Get extraction capabilities
        print("\nFetching web extraction capabilities...")
        content, _ = await session.read_resource("config://extraction-capabilities")
        print(content)
        
        # Basic scraping demo
        print("\n--- BASIC SCRAPING DEMO ---")
        result = await session.call_tool(
            "scrape_url", 
            arguments={
                "url": "https://modelcontextprotocol.io/",
                "formats": ["markdown"]
            }
        )
        
        if isinstance(result, dict) and "formats" in result and "markdown" in result["formats"]:
            markdown = result["formats"]["markdown"]
            print(f"Scraped {len(markdown)} characters of markdown")
            print("First 200 characters:")
            print(markdown[:200] + "...")
        
        # Smart extraction demo
        print("\n--- SMART EXTRACTION DEMO ---")
        smart_result = await session.call_tool(
            "smart_extract_from_website", 
            arguments={
                "url": "https://modelcontextprotocol.io/",
                "objective": "Summarize what the Model Context Protocol is",
                "use_advanced_model": False
            }
        )
        
        if isinstance(smart_result, dict):
            print(f"Success: {smart_result.get('success', False)}")
            print(f"Message: {smart_result.get('message', 'No message')}")
            
            if smart_result.get('success') and smart_result.get('data'):
                print("\nExtracted information:")
                print(json.dumps(smart_result['data'], indent=2)[:500] + "...")
    
    finally:
        await close_session(session, read, write)


async def main():
    """Run the client."""
    if len(sys.argv) < 2:
        # Run the demo
        await run_demo()
        return
        
    command = sys.argv[1].lower()
    
    if command == "generate":
        if len(sys.argv) < 3:
            print("Error: Please provide a prompt.")
            return
        prompt = sys.argv[2]
        service = sys.argv[3] if len(sys.argv) > 3 else None
        model = sys.argv[4] if len(sys.argv) > 4 else None
        await run_generate_text(prompt, service, model)
        
    elif command == "search":
        if len(sys.argv) < 3:
            print("Error: Please provide a search query.")
            return
        query = sys.argv[2]
        await run_search_web(query)
        
    elif command == "scrape":
        if len(sys.argv) < 3:
            print("Error: Please provide a URL.")
            return
        url = sys.argv[2]
        await run_scrape_url(url)
        
    elif command == "extract":
        if len(sys.argv) < 4:
            print("Error: Please provide a URL and an objective.")
            return
        url = sys.argv[2]
        objective = sys.argv[3]
        use_advanced = sys.argv[4].lower() == "true" if len(sys.argv) > 4 else False
        await run_smart_extract(url, objective, use_advanced)
        
    elif command == "advanced-extract":
        if len(sys.argv) < 4:
            print("Error: Please provide URLs and an objective.")
            return
        urls = sys.argv[2].split(",")
        objective = sys.argv[3]
        entity = sys.argv[4] if len(sys.argv) > 4 else None
        await run_advanced_extract(urls, objective, entity)
        
    else:
        print(f"Unknown command: {command}")
        print("Available commands: generate, search, scrape, extract, advanced-extract")


if __name__ == "__main__":
    asyncio.run(main())
