"""Tests for the MCP server."""
import os
import subprocess
import time
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_server_starts():
    """Test that the MCP server starts without errors."""
    # Skip if no API keys
    if not all([
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("ANTHROPIC_API_KEY"), 
        os.environ.get("FIRECRAWL_API_KEY")
    ]):
        pytest.skip("One or more API keys not set")
    
    # Start the server in a subprocess
    server_process = subprocess.Popen(
        ["mcp", "dev", "src/multi_ai_agent/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give the server time to start
    time.sleep(2)
    
    # Check if the server is running
    assert server_process.poll() is None, "Server failed to start"
    
    # Terminate the server
    server_process.terminate()
    server_process.wait(timeout=5)
