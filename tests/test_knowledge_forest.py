"""
Test script for Knowledge Forest functionality.
"""
import asyncio
import os
import sys
import json
from datetime import datetime
from bson import ObjectId, json_util

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from core.config import get_settings
from core.storage.mongodb import MongoDBProvider, MongoDBVectorProvider
from core.ai.interfaces import AIModelFactory
from knowledge_forest.services.extraction import KnowledgeExtractionService
from knowledge_forest.services.placement import KnowledgePlacementService
from knowledge_forest.services.graph_manager import KnowledgeGraphManager
from knowledge_forest.services.processor import KnowledgeProcessorService

settings = get_settings()

async def test_knowledge_extraction():
    """Test knowledge extraction."""
    print("=== Testing Knowledge Extraction ===")
    
    # Initialize AI model
    ai_model = AIModelFactory.create_model(settings.ai.default_service)
    
    # Initialize extraction service
    extraction_service = KnowledgeExtractionService(ai_model)
    
    # Test text
    test_text = """
    The Knowledge Forest system is an AI-powered tool that helps users organize and explore knowledge.
    It extracts key concepts and relationships from conversations, creating a graph-based representation.
    Users can visualize their knowledge as a 3D forest, with topics as trees and concepts as branches.
    The system uses vector embeddings to find similar nodes and cross-links between topics.
    """
    
    # Create a mock message
    message = {
        "text": test_text,
        "_id": "test_message_id"
    }
    
    # Extract knowledge
    analysis = await extraction_service.analyze_message(message)
    
    # Print results
    print(f"Summary: {analysis['summary']}")
    print("\nEntities:")
    for entity in analysis["entities"]:
        print(f"- {entity['text']} (Type: {entity['type']})")
    
    print("\nRelationships:")
    for rel in analysis["relationships"]:
        print(f"- {rel['source']} {rel['type']} {rel['target']} (Strength: {rel['strength']})")
    
    return analysis

async def test_knowledge_graph():
    """Test knowledge graph creation."""
    print("\n=== Testing Knowledge Graph Creation ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    vector_provider = MongoDBVectorProvider()
    await vector_provider.connect()
    
    ai_model = AIModelFactory.create_model(settings.ai.default_service)
    
    graph_manager = KnowledgeGraphManager(db_provider)
    
    # Create a test user ID if not exists
    test_user_id = "000000000000000000000001"
    
    # Create a new topic node
    topic_id = await graph_manager.create_node(
        user_id=test_user_id,
        label="Knowledge Forest",
        node_type="topic",
        summary="A system for organizing and exploring knowledge extracted from conversations.",
        embedding=None,  # No embedding for this test
        parent_node_id=None,
        topic_cluster_id="test_topic_1"
    )
    
    print(f"Created topic node: {topic_id}")
    
    # Create some child nodes
    child_nodes = []
    for i, label in enumerate(["Vector Embeddings", "3D Visualization", "Knowledge Graph"]):
        node_id = await graph_manager.create_node(
            user_id=test_user_id,
            label=label,
            node_type="concept",
            summary=f"A concept related to {label}",
            embedding=None,
            parent_node_id=topic_id,
            topic_cluster_id="test_topic_1"
        )
        child_nodes.append(node_id)
        print(f"Created child node {i+1}: {node_id}")
    
    # Create some edges
    for i, source_id in enumerate(child_nodes):
        target_id = child_nodes[(i + 1) % len(child_nodes)]
        edge_id = await graph_manager.create_edge(
            user_id=test_user_id,
            source_node_id=source_id,
            target_node_id=target_id,
            relationship_type="relates_to",
            strength=0.8
        )
        print(f"Created edge: {edge_id}")
    
    # Get the graph
    topic_nodes = await graph_manager.get_topic_nodes("test_topic_1", test_user_id)
    print(f"\nFound {len(topic_nodes)} nodes in the topic")
    
    # Clean up (optional)
    # Uncomment to remove test data
    # for node in topic_nodes:
    #     await db_provider.delete_document("nodes", str(node["_id"]))
    # await db_provider.delete_document("nodes", topic_id)
    
    return topic_nodes

async def test_full_pipeline():
    """Test the full knowledge processing pipeline."""
    print("\n=== Testing Full Knowledge Pipeline ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    vector_provider = MongoDBVectorProvider()
    await vector_provider.connect()
    
    ai_model = AIModelFactory.create_model(settings.ai.default_service)
    
    processor = KnowledgeProcessorService(ai_model, db_provider, vector_provider)
    
    # Test user and conversation
    test_user_id = "000000000000000000000001"
    test_conversation_id = "000000000000000000000002"
    
    # Test message
    message = {
        "_id": "test_message_" + str(ObjectId()),
        "text": """
        The Multi-AI Agent system is being enhanced with Knowledge Forest capabilities.
        This integration allows users to automatically extract knowledge from their conversations.
        The system creates a graph representation with nodes for concepts and edges for relationships.
        Users can explore their knowledge in a 3D visualization, finding connections between topics.
        """,
        "role": "user"
    }
    
    # Process the message
    result = await processor.process_message(
        message=message,
        conversation_id=test_conversation_id,
        user_id=test_user_id
    )
    
    # Print results
    print("Processing results:")
    print(f"- Created {len(result['updates']['nodes_created'])} nodes")
    print(f"- Updated {len(result['updates']['nodes_updated'])} nodes")
    print(f"- Created {len(result['updates']['edges_created'])} edges")
    
    # Get the created nodes
    graph_manager = KnowledgeGraphManager(db_provider)
    if result['updates']['nodes_created']:
        root_node_id = result['updates']['nodes_created'][0]
        root_node = await graph_manager.get_node(root_node_id)
        
        if root_node:
            print(f"\nRoot node: {root_node['label']}")
            print(f"Summary: {root_node.get('summary', 'No summary')}")
            
            # Get children
            children = await graph_manager.get_node_children(root_node_id, test_user_id)
            print(f"\nChildren ({len(children)}):")
            for child in children:
                print(f"- {child['label']} (Type: {child['type']})")
    
    return result

async def main():
    """Run all tests."""
    try:
        # Test extraction
        analysis = await test_knowledge_extraction()
        
        # Test graph creation
        nodes = await test_knowledge_graph()
        
        # Test full pipeline
        result = await test_full_pipeline()
        
        print("\n=== All tests completed successfully ===")
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Close connections
        if 'vector_provider' in locals():
            await vector_provider.close()

if __name__ == "__main__":
    asyncio.run(main())
