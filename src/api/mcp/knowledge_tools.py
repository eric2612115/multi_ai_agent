"""MCP tools for knowledge forest.

This module provides MCP tools for knowledge forest operations.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Type
from pydantic import BaseModel, Field
import json
import asyncio
from datetime import datetime
import uuid

from forest.tasks import KnowledgeForestTaskHandler
from forest.extraction_service import KnowledgeExtractionService
from services.event_bus import EventBus

# Setup logging
logger = logging.getLogger(__name__)

# MCP Tool Models
class KnowledgeExtractTool(BaseModel):
    """Tool for extracting knowledge from content."""
    
    tool_name: str = "extract_knowledge"
    
    class Parameters(BaseModel):
        """Parameters for knowledge extraction."""
        
        content: str = Field(..., description="The content to extract knowledge from")
        user_id: str = Field(..., description="The user ID")
        conversation_id: Optional[str] = Field(None, description="The conversation ID")
        message_id: Optional[str] = Field(None, description="The message ID")
        metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")
        
        model_config = {
            'extra': 'forbid'
        }
    
    class Response(BaseModel):
        """Response for knowledge extraction."""
        
        task_id: str = Field(..., description="The task ID for tracking the extraction process")
        status: str = Field(..., description="The status of the extraction")
        message: str = Field(..., description="A message about the extraction")
        
        model_config = {
            'extra': 'forbid'
        }

class KnowledgeSearchTool(BaseModel):
    """Tool for searching the knowledge graph."""
    
    tool_name: str = "search_knowledge"
    
    class Parameters(BaseModel):
        """Parameters for knowledge search."""
        
        query: str = Field(..., description="The search query")
        user_id: str = Field(..., description="The user ID")
        limit: int = Field(5, description="Maximum number of results to return")
        topic_cluster_id: Optional[str] = Field(None, description="Specific topic cluster to search in")
        
        model_config = {
            'extra': 'forbid'
        }
    
    class Response(BaseModel):
        """Response for knowledge search."""
        
        results: List[Dict[str, Any]] = Field(..., description="The search results")
        query: str = Field(..., description="The search query")
        count: int = Field(..., description="Number of results found")
        
        model_config = {
            'extra': 'forbid'
        }

class KnowledgeGraphTool(BaseModel):
    """Tool for retrieving knowledge graph for visualization."""
    
    tool_name: str = "get_knowledge_graph"
    
    class Parameters(BaseModel):
        """Parameters for knowledge graph retrieval."""
        
        user_id: str = Field(..., description="The user ID")
        topic_cluster_id: Optional[str] = Field(None, description="The topic cluster ID to focus on")
        max_depth: int = Field(3, description="Maximum depth of nodes to include")
        include_cross_links: bool = Field(True, description="Include cross-links between topics")
        
        model_config = {
            'extra': 'forbid'
        }
    
    class Response(BaseModel):
        """Response for knowledge graph retrieval."""
        
        nodes: List[Dict[str, Any]] = Field(..., description="The nodes in the graph")
        edges: List[Dict[str, Any]] = Field(..., description="The edges in the graph")
        topic_cluster_id: Optional[str] = Field(None, description="The topic cluster ID that was requested")
        node_count: int = Field(..., description="Number of nodes in the graph")
        edge_count: int = Field(..., description="Number of edges in the graph")
        
        model_config = {
            'extra': 'forbid'
        }

# MCP Tool Implementations
class KnowledgeToolsService:
    """Service for MCP knowledge tools."""
    
    def __init__(self, 
                task_handler: Optional[KnowledgeForestTaskHandler] = None,
                extraction_service: Optional[KnowledgeExtractionService] = None,
                event_bus: Optional[EventBus] = None):
        """Initialize the knowledge tools service.
        
        Args:
            task_handler: Optional task handler.
            extraction_service: Optional extraction service.
            event_bus: Optional event bus.
        """
        self.task_handler = task_handler
        self.extraction_service = extraction_service
        self.event_bus = event_bus
        
        # Lazy initialize services if not provided
        if self.task_handler is None:
            self.task_handler = KnowledgeForestTaskHandler()
            
        if self.extraction_service is None:
            self.extraction_service = KnowledgeExtractionService()
            
        if self.event_bus is None:
            self.event_bus = EventBus()
    
    async def extract_knowledge(self, parameters: KnowledgeExtractTool.Parameters) -> KnowledgeExtractTool.Response:
        """Extract knowledge from content.
        
        Args:
            parameters: The extraction parameters.
            
        Returns:
            The extraction response.
        """
        try:
            # Ensure parameters are valid
            if not parameters.content.strip():
                return KnowledgeExtractTool.Response(
                    task_id="none",
                    status="error",
                    message="Content is empty"
                )
                
            # Generate IDs if not provided
            conversation_id = parameters.conversation_id or str(uuid.uuid4())
            message_id = parameters.message_id or str(uuid.uuid4())
            
            # Prepare message data
            message_data = {
                "content": parameters.content,
                "user_id": parameters.user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "metadata": parameters.metadata,
                "source": "mcp_tool"  # Mark the source as MCP tool
            }
            
            # Process the message
            task_id = await self.task_handler.process_message(message_data)
            
            return KnowledgeExtractTool.Response(
                task_id=task_id,
                status="processing",
                message="Knowledge extraction task has been started"
            )
            
        except Exception as e:
            logger.error(f"Failed to extract knowledge: {str(e)}")
            
            return KnowledgeExtractTool.Response(
                task_id="error",
                status="error",
                message=f"Failed to extract knowledge: {str(e)}"
            )
    
    async def search_knowledge(self, parameters: KnowledgeSearchTool.Parameters) -> KnowledgeSearchTool.Response:
        """Search the knowledge graph.
        
        Args:
            parameters: The search parameters.
            
        Returns:
            The search response.
        """
        try:
            # Ensure parameters are valid
            if not parameters.query.strip():
                return KnowledgeSearchTool.Response(
                    results=[],
                    query=parameters.query,
                    count=0
                )
                
            # TODO: Implement knowledge search
            # This would typically use the vector search capability
            # For now, return an empty result
            
            return KnowledgeSearchTool.Response(
                results=[],
                query=parameters.query,
                count=0
            )
            
        except Exception as e:
            logger.error(f"Failed to search knowledge: {str(e)}")
            
            return KnowledgeSearchTool.Response(
                results=[],
                query=parameters.query,
                count=0
            )
    
    async def get_knowledge_graph(self, parameters: KnowledgeGraphTool.Parameters) -> KnowledgeGraphTool.Response:
        """Get the knowledge graph.
        
        Args:
            parameters: The graph parameters.
            
        Returns:
            The graph response.
        """
        try:
            # Get the graph from the graph manager
            graph = await self.task_handler.graph_manager.get_graph(
                user_id=parameters.user_id,
                topic_cluster_id=parameters.topic_cluster_id,
                max_depth=parameters.max_depth,
                include_cross_links=parameters.include_cross_links
            )
            
            # Return the graph
            return KnowledgeGraphTool.Response(
                nodes=graph.get("nodes", []),
                edges=graph.get("edges", []),
                topic_cluster_id=parameters.topic_cluster_id,
                node_count=len(graph.get("nodes", [])),
                edge_count=len(graph.get("edges", []))
            )
            
        except Exception as e:
            logger.error(f"Failed to get knowledge graph: {str(e)}")
            
            return KnowledgeGraphTool.Response(
                nodes=[],
                edges=[],
                topic_cluster_id=parameters.topic_cluster_id,
                node_count=0,
                edge_count=0
            )

# Tool registry
def register_knowledge_tools():
    """Register knowledge tools with the MCP.
    
    This function should be called during application startup to register
    the knowledge tools with the MCP system.
    """
    try:
        # Create the service instance
        service = KnowledgeToolsService()
        
        # Define the tools with proper error handling
        tools = []
        
        # Safely extract the tool information
        try:
            extract_tool = {
                "name": "extract_knowledge",
                "description": "Extract knowledge from content and add it to the user's knowledge graph",
                "parameters": json.loads(json.dumps(KnowledgeExtractTool.Parameters.model_json_schema())),
                "handler": service.extract_knowledge
            }
            tools.append(extract_tool)
        except Exception as e:
            logger.warning(f"Failed to add extract_knowledge tool: {str(e)}")
            
        try:
            search_tool = {
                "name": "search_knowledge",
                "description": "Search the user's knowledge graph for relevant information",
                "parameters": json.loads(json.dumps(KnowledgeSearchTool.Parameters.model_json_schema())),
                "handler": service.search_knowledge
            }
            tools.append(search_tool)
        except Exception as e:
            logger.warning(f"Failed to add search_knowledge tool: {str(e)}")
            
        try:
            graph_tool = {
                "name": "get_knowledge_graph",
                "description": "Get the user's knowledge graph for a specific topic or all topics",
                "parameters": json.loads(json.dumps(KnowledgeGraphTool.Parameters.model_json_schema())),
                "handler": service.get_knowledge_graph
            }
            tools.append(graph_tool)
        except Exception as e:
            logger.warning(f"Failed to add get_knowledge_graph tool: {str(e)}")
        
        # Register with MCP
        # This part would typically integrate with your MCP system
        # For now, just log that these would be registered
        logger.info(f"Would register {len(tools)} knowledge tools with MCP")
        
        # Make a deep copy of the tools to avoid reference issues
        # and cleanup any problematic fields
        clean_tools = []
        
        for tool in tools:
            try:
                # Create a clean copy with only serializable data
                clean_tool = {
                    "name": str(tool["name"]),
                    "description": str(tool["description"]),
                    # Keep the parameters as already sanitized
                    "parameters": tool["parameters"],
                    # Keep the handler reference
                    "handler": tool["handler"]
                }
                clean_tools.append(clean_tool)
            except Exception as e:
                logger.warning(f"Failed to clean tool {tool.get('name', 'unknown')}: {str(e)}")
        
        return clean_tools
        
    except Exception as e:
        logger.error(f"Failed to register knowledge tools: {str(e)}")
        # Return empty list as fallback
        return []
