"""MCP service entry point.

This module serves as the entry point for the MCP service,
providing access to the knowledge forest tools.
"""
import logging
import asyncio
import json
import sys
from typing import Dict, List, Any, Optional
import argparse
import os

# Import common functionality
from src.common.config import get_settings

# 预先初始化AI模型，确保它们正确加载
import src.ai.gemini
import src.ai.claude

# Import MCP tool registration
from src.api.mcp.knowledge_tools import register_knowledge_tools

# Get settings
settings = get_settings()

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

class MCPService:
    """MCP service for knowledge forest tools."""
    
    def __init__(self):
        """Initialize the MCP service."""
        self.tools = {}
        
    async def start(self):
        """Start the MCP service."""
        logger.info("Starting MCP service")
        
        # Register tools
        tools = register_knowledge_tools()
        
        # Store tools by name
        for tool in tools:
            self.tools[tool["name"]] = tool
            
        logger.info(f"Registered {len(tools)} knowledge tools")
        
    async def stop(self):
        """Stop the MCP service."""
        logger.info("Stopping MCP service")
        
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool.
        
        Args:
            tool_name: The tool name.
            parameters: The tool parameters.
            
        Returns:
            The tool response.
            
        Raises:
            ValueError: If the tool is not found.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
            
        tool = self.tools[tool_name]
        handler = tool["handler"]
        
        # Create a parameters object
        param_class = tool["parameters"]["parameters"]
        params = param_class(**parameters)
        
        # Execute the tool
        result = await handler(params)
        
        # Convert result to dict
        if hasattr(result, "dict"):
            return result.dict()
        else:
            return result
        
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an MCP request.
        
        Args:
            request_data: The request data.
            
        Returns:
            The response data.
        """
        try:
            tool_name = request_data.get("tool")
            parameters = request_data.get("parameters", {})
            
            if not tool_name:
                return {
                    "status": "error",
                    "message": "Missing tool name"
                }
                
            # Execute the tool
            result = await self.execute_tool(tool_name, parameters)
            
            return {
                "status": "success",
                "result": result
            }
            
        except ValueError as e:
            return {
                "status": "error",
                "message": str(e)
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            
            return {
                "status": "error",
                "message": f"Error processing request: {str(e)}"
            }

# Command-line interface
async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP service for knowledge forest tools")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Configure logging based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Create and start the service
    service = MCPService()
    await service.start()
    
    try:
        # Process input from stdin
        logger.info("Ready to process requests")
        
        for line in sys.stdin:
            try:
                # Parse JSON request
                request_data = json.loads(line)
                
                # Process the request
                response = await service.process_request(request_data)
                
                # Write response to stdout
                print(json.dumps(response))
                sys.stdout.flush()
                
            except json.JSONDecodeError:
                print(json.dumps({
                    "status": "error",
                    "message": "Invalid JSON request"
                }))
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logger.info("Received shutdown signal")
        
    finally:
        # Stop the service
        await service.stop()

# Run the application if executed directly
if __name__ == "__main__":
    asyncio.run(main())
