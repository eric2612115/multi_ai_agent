#!/usr/bin/env python
"""
Quick start script for the Multi-AI Agent.

This script provides a convenient way to start the MCP server.
"""
import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_environment():
    """Check that the environment is properly set up."""
    # Check for API keys
    missing_keys = []
    required_keys = [
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "FIRECRAWL_API_KEY",
    ]
    
    for key in required_keys:
        if not os.environ.get(key):
            missing_keys.append(key)
    
    if missing_keys:
        print(f"Error: The following environment variables are missing: {', '.join(missing_keys)}")
        print("Please set these in your .env file or environment.")
        return False
    
    return True

def main():
    """Run the server."""
    if not check_environment():
        sys.exit(1)
    
    print("Starting Multi-AI Agent server...")
    print("Press Ctrl+C to stop the server.")
    
    # Run the MCP server in development mode
    try:
        subprocess.run(
            ["mcp", "dev", "src/multi_ai_agent/main.py"],
            check=True
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except subprocess.CalledProcessError as e:
        print(f"\nError running server: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: 'mcp' command not found. Is the MCP SDK installed?")
        print("Try: pip install mcp[cli]")
        sys.exit(1)

if __name__ == "__main__":
    main()
