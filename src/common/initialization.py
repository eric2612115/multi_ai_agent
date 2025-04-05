"""User initialization utilities.

This module provides functionality for initializing new users.
"""
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId

from forest.models import Node, Edge, KnowledgeExtractionResult
from forest.graph import KnowledgeGraphManager
from storage.mongodb import MongoDBProvider

# Setup logging
logger = logging.getLogger(__name__)

async def initialize_new_user(user_id: str, lazy_init: bool = True) -> bool:
    """Initialize a new user with sample data.
    
    Args:
        user_id: The user ID.
        lazy_init: If True, only check for existing data but don't create sample data until first interaction.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        logger.info(f"Initializing new user: {user_id}")
        
        # Create storage provider
        storage = MongoDBProvider()
        
        # Connect to storage
        connected = await storage.is_connected()
        if not connected:
            await storage.connect()
            
        # Check if user already has data
        existing_nodes = None
        try:
            existing_nodes = await storage.find_documents(
                collection="nodes",
                query={"user_id": user_id},
                limit=1
            )

            # Some database drivers don't allow truth testing on cursor results
            # So check length explicitly
            has_nodes = existing_nodes is not None and len(existing_nodes) > 0
            
            if has_nodes:
                logger.info(f"User {user_id} already has data, skipping initialization")
                return True
                
            # If using lazy initialization, don't create sample data yet
            if lazy_init:
                logger.info(f"Lazy initialization for user {user_id} - will create data on first interaction")
                return True
                
        except Exception as e:
            logger.error(f"Error checking for existing user data: {str(e)}")
            
        # Create graph manager
        graph_manager = KnowledgeGraphManager(storage_provider=storage)
        
        # Create root topic node
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        topic_cluster_id = str(uuid.uuid4())
        
        # Create a welcome node
        welcome_extraction = KnowledgeExtractionResult(
            message_id=message_id,
            summary="Welcome to Knowledge Forest",
            text="Knowledge Forest is a visual knowledge management tool that helps you organize and explore information.",
            entities=[
                {"text": "Knowledge Forest", "type": "concept"},
                {"text": "visualization", "type": "keyword"},
                {"text": "knowledge management", "type": "concept"}
            ],
            relationships=[],
            embedding=[0.1] * 768,  # Simple placeholder embedding
            timestamp=datetime.utcnow().isoformat()
        )
        
        welcome_node_id = await graph_manager._create_root_node(
            extraction_result=welcome_extraction,
            topic_cluster_id=topic_cluster_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id
        )
        
        # Create child nodes
        child_topics = [
            {
                "summary": "AI Agent System Introduction",
                "text": "Multi-AI agent systems use multiple AI models working together to provide more powerful features and a more natural interaction experience.",
                "entities": [
                    {"text": "AI agent", "type": "concept"},
                    {"text": "multi-model collaboration", "type": "concept"}
                ]
            },
            {
                "summary": "Knowledge Extraction Feature",
                "text": "The system can automatically extract knowledge from conversations and documents, organizing it into meaningful structures.",
                "entities": [
                    {"text": "knowledge extraction", "type": "concept"},
                    {"text": "automation", "type": "keyword"}
                ]
            },
            {
                "summary": "Knowledge Graph Visualization",
                "text": "Visually display relationships between concepts through a graphical interface, helping you understand complex topics.",
                "entities": [
                    {"text": "visualization", "type": "concept"},
                    {"text": "knowledge graph", "type": "concept"}
                ]
            }
        ]
        
        # Create child nodes
        child_ids = []
        for i, topic in enumerate(child_topics):
            child_extraction = KnowledgeExtractionResult(
                message_id=message_id,
                summary=topic["summary"],
                text=topic["text"],
                entities=topic["entities"],
                relationships=[],
                embedding=[0.2 + (i * 0.1)] * 768,  # Simple placeholder embeddings
                timestamp=datetime.utcnow().isoformat()
            )
            
            child_id = await graph_manager._create_child_node(
                extraction_result=child_extraction,
                parent_node_id=welcome_node_id,
                relationship_type="has_topic",
                topic_cluster_id=topic_cluster_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )
            
            child_ids.append(child_id)
            
            # Create edge between parent and child
            await graph_manager._create_edge(
                source_node_id=welcome_node_id,
                target_node_id=child_id,
                relationship_type="has_topic",
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id
            )
        
        # Create cross-relationships between child nodes
        if len(child_ids) >= 2:
            # Connect first and second child
            await graph_manager._create_edge(
                source_node_id=child_ids[0],
                target_node_id=child_ids[1],
                relationship_type="relates_to",
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                strength=0.7
            )
            
            # Connect second and third child (if exists)
            if len(child_ids) >= 3:
                await graph_manager._create_edge(
                    source_node_id=child_ids[1],
                    target_node_id=child_ids[2],
                    relationship_type="relates_to",
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    strength=0.7
                )
        
        logger.info(f"Successfully initialized new user: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize user {user_id}: {str(e)}")
        return False

async def create_default_user() -> str:
    """Create a default user for development and testing.
    
    Returns:
        The user ID.
    """
    try:
        # Use a fixed user ID for development
        user_id = "user123"
        
        # Initialize the user
        success = await initialize_new_user(user_id)
        
        if success:
            logger.info(f"Created default user: {user_id}")
        else:
            logger.warning(f"Failed to create default user: {user_id}")
        
        return user_id
        
    except Exception as e:
        logger.error(f"Error creating default user: {str(e)}")
        return "user123"  # Return a fixed ID
