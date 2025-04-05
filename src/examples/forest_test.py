#!/usr/bin/env python
"""
Knowledge Forest Example

This script demonstrates how to use the knowledge forest components
to extract, organize, and retrieve knowledge from text.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from bson import ObjectId

# Add the src_new directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the necessary modules
from forest import (
    get_knowledge_extractor,
    get_graph_manager,
)

from storage import (
    get_document_storage,
)

from ai.factory import get_text_generation_model, get_embedding_model


async def setup_test_user():
    """Set up a test user ID."""
    # For demonstration, use a fixed ObjectId
    return ObjectId("000000000000000000000001")


async def test_knowledge_extraction():
    """Test knowledge extraction."""
    print("\n=== Testing Knowledge Extraction ===")
    
    # Create a test message
    message = {
        "_id": str(ObjectId()),
        "text": """
        Artificial intelligence (AI) is intelligence demonstrated by machines, 
        as opposed to human or animal intelligence. AI research has been defined 
        as the field of study of intelligent agents, which refers to any system 
        that perceives its environment and takes actions that maximize its chance 
        of achieving its goals. The term "artificial intelligence" was coined in 1955.
        """,
        "role": "user"
    }
    
    try:
        # Get the extractor
        extractor = get_knowledge_extractor()
        
        print(f"Extracting knowledge from message: {message['_id']}")
        result = await extractor.extract_knowledge(message)
        
        # Print the results
        print(f"Generated summary: {result.summary}")
        print(f"Extracted {len(result.entities)} entities:")
        for i, entity in enumerate(result.entities[:5]):  # Show first 5
            print(f"  {i+1}. {entity['text']} (Type: {entity['type']})")
            
        if len(result.entities) > 5:
            print(f"  ... and {len(result.entities) - 5} more")
            
        print(f"Extracted {len(result.relationships)} relationships:")
        for i, rel in enumerate(result.relationships[:3]):  # Show first 3
            print(f"  {i+1}. {rel['source']} -> {rel['target']} ({rel['type']})")
            
        if len(result.relationships) > 3:
            print(f"  ... and {len(result.relationships) - 3} more")
            
        # Check embedding
        print(f"Embedding dimensions: {len(result.embedding)}")
        
        return result
        
    except Exception as e:
        print(f"Error during knowledge extraction: {str(e)}")
        return None


async def test_graph_operations(user_id, extraction_result=None):
    """Test graph operations."""
    print("\n=== Testing Graph Operations ===")
    
    try:
        # Get the graph manager
        db = get_document_storage()
        await db.connect()
        
        graph_manager = get_graph_manager(db_provider=db)
        
        # Create a test topic cluster ID
        topic_cluster_id = str(uuid.uuid4())
        print(f"Created topic cluster ID: {topic_cluster_id}")
        
        # Create a root node
        root_node_id = await graph_manager.create_node(
            user_id=user_id,
            label="Artificial Intelligence",
            node_type="topic",
            summary="Intelligence demonstrated by machines",
            embedding=extraction_result.embedding if extraction_result else None,
            parent_node_id=None,  # Root node
            topic_cluster_id=topic_cluster_id
        )
        
        print(f"Created root node: {root_node_id}")
        
        # If we have extraction results, create nodes for entities
        if extraction_result and extraction_result.entities:
            print("Creating nodes for extracted entities:")
            
            node_ids = []
            for entity in extraction_result.entities[:5]:  # Create first 5 entities
                entity_node_id = await graph_manager.create_node(
                    user_id=user_id,
                    label=entity["text"],
                    node_type=entity["type"],
                    summary=None,  # No summary for entity nodes
                    embedding=None,  # No separate embedding
                    parent_node_id=root_node_id,
                    topic_cluster_id=topic_cluster_id
                )
                
                node_ids.append(entity_node_id)
                print(f"  Created entity node: {entity_node_id} - {entity['text']}")
                
                # Create edge from root to entity
                edge_id = await graph_manager.create_edge(
                    user_id=user_id,
                    source_node_id=root_node_id,
                    target_node_id=entity_node_id,
                    relationship_type="contains",
                    strength=0.9
                )
                
                print(f"  Created edge: {edge_id} - root -> {entity['text']}")
            
            # Create edges between entities based on extracted relationships
            if extraction_result.relationships:
                print("Creating edges for extracted relationships:")
                
                for rel in extraction_result.relationships[:3]:  # Create first 3 relationships
                    source_text = rel["source"]
                    target_text = rel["target"]
                    
                    # Find corresponding entity nodes (simplified)
                    source_node_id = None
                    target_node_id = None
                    
                    for i, entity in enumerate(extraction_result.entities[:5]):
                        if entity["text"].lower() == source_text.lower() and i < len(node_ids):
                            source_node_id = node_ids[i]
                        if entity["text"].lower() == target_text.lower() and i < len(node_ids):
                            target_node_id = node_ids[i]
                    
                    if source_node_id and target_node_id:
                        edge_id = await graph_manager.create_edge(
                            user_id=user_id,
                            source_node_id=source_node_id,
                            target_node_id=target_node_id,
                            relationship_type=rel["type"],
                            strength=rel.get("strength", 0.8),
                            context_summary=rel.get("context", None)
                        )
                        
                        print(f"  Created edge: {edge_id} - {source_text} -> {target_text}")
        
        # Get the root node
        root_node = await graph_manager.get_node(root_node_id)
        print(f"\nRetrieved root node: {root_node['label']}")
        
        # Get children of the root node
        children = await graph_manager.get_node_children(root_node_id, user_id)
        print(f"Root node has {len(children)} children")
        
        # Get edges connected to the root node
        edges = await graph_manager.get_node_edges(root_node_id, user_id)
        print(f"Root node has {len(edges)} edges")
        
        # Clean up
        await db.close()
        
        return {
            "topic_cluster_id": topic_cluster_id,
            "root_node_id": root_node_id,
            "node_ids": node_ids if extraction_result else []
        }
        
    except Exception as e:
        print(f"Error during graph operations: {str(e)}")
        return None


async def main():
    """Run all tests."""
    print("Knowledge Forest Example")
    print("=======================")
    
    # Load environment variables
    load_dotenv()
    
    # Setup a test user
    user_id = await setup_test_user()
    print(f"Using test user ID: {user_id}")
    
    # Run the extraction test
    extraction_result = await test_knowledge_extraction()
    
    # Run the graph operations test
    graph_result = await test_graph_operations(user_id, extraction_result)
    
    print("\nExample completed!")


if __name__ == "__main__":
    asyncio.run(main())
