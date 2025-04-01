"""Command-line interface for testing the Multi-AI Agent."""
import sys
import subprocess
import argparse
from dotenv import load_dotenv

def main():
    """Run the CLI."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Multi-AI Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Start server command
    start_parser = subparsers.add_parser("start", help="Start the MCP server")
    
    # Test commands
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument(
        "--service", 
        choices=["gemini", "claude", "firecrawl", "extraction", "all"],
        default="all",
        help="Which service to test"
    )
    
    # Generate text command
    gen_parser = subparsers.add_parser("generate", help="Generate text")
    gen_parser.add_argument("prompt", help="Text prompt")
    gen_parser.add_argument(
        "--service", 
        choices=["gemini", "claude"],
        default=None,
        help="Which service to use"
    )
    gen_parser.add_argument(
        "--model",
        default=None,
        help="Specific model to use"
    )
    
    # Scrape URL command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape a URL")
    scrape_parser.add_argument("url", help="URL to scrape")
    
    # Search web command
    search_parser = subparsers.add_parser("search", help="Search the web")
    search_parser.add_argument("query", help="Search query")
    
    # Smart extract command
    extract_parser = subparsers.add_parser("extract", help="Extract information from a website")
    extract_parser.add_argument("url", help="Website URL")
    extract_parser.add_argument("objective", help="What information to extract")
    extract_parser.add_argument(
        "--advanced",
        action="store_true",
        help="Use advanced models for better results"
    )
    
    # Advanced extract command
    adv_extract_parser = subparsers.add_parser("advanced-extract", help="Advanced extraction from specific URLs")
    adv_extract_parser.add_argument("urls", help="Comma-separated list of URLs")
    adv_extract_parser.add_argument("objective", help="What information to extract")
    adv_extract_parser.add_argument(
        "--entity",
        default=None,
        help="Entity name for context (e.g., company name)"
    )
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run a demonstration of capabilities")
    
    args = parser.parse_args()
    
    if args.command == "start":
        # Start the server
        subprocess.run(["mcp", "dev", "src/multi_ai_agent/main.py"])
    
    elif args.command == "test":
        # Run tests
        if args.service == "all":
            subprocess.run(["pytest", "tests/"])
        elif args.service == "extraction":
            subprocess.run(["pytest", "tests/test_web_extraction.py"])
        else:
            subprocess.run(["pytest", f"tests/test_{args.service}.py"])
    
    elif args.command == "generate":
        # Generate text using the Python client
        import asyncio
        from multi_ai_agent.client_example import run_generate_text
        
        asyncio.run(run_generate_text(args.prompt, args.service, args.model))
    
    elif args.command == "scrape":
        # Scrape a URL
        import asyncio
        from multi_ai_agent.client_example import run_scrape_url
        
        asyncio.run(run_scrape_url(args.url))
    
    elif args.command == "search":
        # Search the web
        import asyncio
        from multi_ai_agent.client_example import run_search_web
        
        asyncio.run(run_search_web(args.query))
    
    elif args.command == "extract":
        # Extract information from a website
        import asyncio
        from multi_ai_agent.client_example import run_smart_extract
        
        asyncio.run(run_smart_extract(args.url, args.objective, args.advanced))
    
    elif args.command == "advanced-extract":
        # Advanced extraction from specific URLs
        import asyncio
        from multi_ai_agent.client_example import run_advanced_extract
        
        urls = args.urls.split(",")
        asyncio.run(run_advanced_extract(urls, args.objective, args.entity))
    
    elif args.command == "demo":
        # Run the demonstration
        import asyncio
        from multi_ai_agent.client_example import run_demo
        
        asyncio.run(run_demo())
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
