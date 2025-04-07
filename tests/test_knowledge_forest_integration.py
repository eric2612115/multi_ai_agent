"""
Integration test for Knowledge Forest functionality.
"""
import asyncio
import os
import sys
import json
from datetime import datetime
import uuid
from bson import ObjectId

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from core.config import get_settings
from core.storage.mongodb import MongoDBProvider, MongoDBVectorProvider
from core.ai.interfaces import AIModelFactory
from knowledge_forest.services.extraction import KnowledgeExtractionService
from knowledge_forest.services.placement import KnowledgePlacementService
from knowledge_forest.services.graph_manager import KnowledgeGraphManager
from knowledge_forest.services.processor import KnowledgeProcessorService
from knowledge_forest.services.export_import import KnowledgeExportImportService
from knowledge_forest.services.search import KnowledgeSearchService
from knowledge_forest.services.search_graph import KnowledgeGraphSearch

settings = get_settings()

async def setup_test_data():
    """Create test data in the database."""
    print("=== Setting up test data ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    vector_provider = MongoDBVectorProvider()
    await vector_provider.connect()
    
    ai_model = AIModelFactory.create_model(settings.ai.default_service)
    
    graph_manager = KnowledgeGraphManager(db_provider)
    
    # Create a test user ID if not exists
    test_user_id = "000000000000000000000001"
    
    # Create a topic cluster ID
    topic_cluster_id = str(uuid.uuid4())
    
    # Create a topic node (root)
    topic_id = await graph_manager.create_node(
        user_id=test_user_id,
        label="AI Knowledge Systems",
        node_type="topic",
        summary="Systems that organize and extract knowledge from information sources.",
        embedding=None,  # No embedding for this test
        parent_node_id=None,
        topic_cluster_id=topic_cluster_id
    )
    
    print(f"Created topic node: {topic_id}")
    
    # Create some child nodes
    child_nodes = []
    concepts = [
        "Knowledge Extraction", 
        "Vector Embeddings", 
        "Graph Visualization",
        "Semantic Search",
        "Cross-topic Linking"
    ]
    
    for label in concepts:
        node_id = await graph_manager.create_node(
            user_id=test_user_id,
            label=label,
            node_type="concept",
            summary=f"A concept related to {label} in AI knowledge systems.",
            embedding=None,
            parent_node_id=topic_id,
            topic_cluster_id=topic_cluster_id
        )
        child_nodes.append(node_id)
        print(f"Created concept node: {node_id} - {label}")
    
    # Create some relations between concepts
    for i in range(len(child_nodes)):
        for j in range(i+1, len(child_nodes)):
            # Create a bidirectional relationship
            source_id = child_nodes[i]
            target_id = child_nodes[j]
            
            # Forward relationship
            edge_id = await graph_manager.create_edge(
                user_id=test_user_id,
                source_node_id=source_id,
                target_node_id=target_id,
                relationship_type="relates_to",
                strength=0.8,
                context_summary=f"Relates {concepts[i]} to {concepts[j]}"
            )
            print(f"Created edge: {edge_id} - {concepts[i]} → {concepts[j]}")
            
            # Backward relationship
            edge_id = await graph_manager.create_edge(
                user_id=test_user_id,
                source_node_id=target_id,
                target_node_id=source_id,
                relationship_type="relates_to",
                strength=0.8,
                context_summary=f"Relates {concepts[j]} to {concepts[i]}"
            )
            print(f"Created edge: {edge_id} - {concepts[j]} → {concepts[i]}")
    
    return topic_cluster_id, test_user_id, child_nodes

async def test_export_import(topic_cluster_id, test_user_id):
    """Test export and import functionality."""
    print("\n=== Testing Export/Import ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    export_service = KnowledgeExportImportService(db_provider)
    
    # Export the knowledge graph
    export_data = await export_service.export_knowledge_graph(
        user_id=test_user_id,
        topic_cluster_id=topic_cluster_id,
        format="json"
    )
    
    print(f"Exported knowledge graph with {len(export_data['nodes'])} nodes and {len(export_data['edges'])} edges")
    
    # Get export summary
    summary = await export_service.get_export_summary(
        user_id=test_user_id,
        topic_cluster_id=topic_cluster_id
    )
    
    print(f"Export summary: {summary}")
    
    # Create a new topic cluster ID for the import
    new_topic_id = str(uuid.uuid4())
    
    # Modify the export data for testing import
    for node in export_data["nodes"]:
        if node["topic_cluster_id"] == topic_cluster_id:
            node["topic_cluster_id"] = new_topic_id
    
    # Import the modified data
    import_result = await export_service.import_knowledge_graph(
        user_id=test_user_id,
        import_data=export_data,
        format="json",
        merge_strategy="overwrite"
    )
    
    print(f"Import results: {import_result}")
    
    return new_topic_id

async def test_search(test_user_id):
    """Test search functionality."""
    print("\n=== Testing Search ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    vector_provider = MongoDBVectorProvider()
    await vector_provider.connect()
    
    ai_model = AIModelFactory.create_model(settings.ai.default_service)
    
    search_service = KnowledgeSearchService(db_provider, vector_provider, ai_model)
    
    # Test keyword search
    keyword_results = await search_service.keyword_search(
        user_id=test_user_id,
        keywords=["Knowledge", "Extraction"],
        match_type="any",
        limit=10
    )
    
    print(f"Keyword search results: {len(keyword_results)} nodes found")
    for node in keyword_results:
        print(f"- {node['label']}: {node.get('summary', '')[:50]}...")
    
    # Test filtered search
    filtered_results = await search_service.filtered_search(
        user_id=test_user_id,
        filters={"type": "concept"},
        sort_field="label",
        sort_direction=1,  # Ascending
        limit=10
    )
    
    print(f"\nFiltered search results: {len(filtered_results)} nodes found")
    for node in filtered_results:
        print(f"- {node['label']}: {node.get('summary', '')[:50]}...")
    
    return True

async def test_graph_search(test_user_id, node_ids):
    """Test graph-based search functionality."""
    print("\n=== Testing Graph Search ===")
    
    # Initialize services
    db_provider = MongoDBProvider()
    graph_search = KnowledgeGraphSearch(db_provider)
    
    if not node_ids or len(node_ids) < 2:
        print("Not enough nodes for graph search test")
        return False
    
    # Test related nodes search
    related_nodes = await graph_search.related_nodes_search(
        user_id=test_user_id,
        node_id=node_ids[0],
        max_hops=1,
        limit=10
    )
    
    print(f"Related nodes search results: {len(related_nodes)} nodes found")
    for result in related_nodes:
        print(f"- {result['node']['label']} (relationship: {result['edge']['relationship_type']})")
    
    # Test path between nodes
    paths = await graph_search.path_between_nodes(
        user_id=test_user_id,
        source_node_id=node_ids[0],
        target_node_id=node_ids[-1],
        max_hops=3
    )
    
    print(f"\nPaths between nodes: {len(paths)} paths found")
    for i, path in enumerate(paths):
        print(f"Path {i+1} (length {path['length']}):")
        for node in path['nodes']:
            print(f"- {node['label']}")
    
    # Test common neighbors
    common = await graph_search.find_common_neighbors(
        user_id=test_user_id,
        node_ids=node_ids[:2],  # First two nodes
        max_results=5
    )
    
    print(f"\nCommon neighbors: {len(common)} nodes found")
    for result in common:
        print(f"- {result['node']['label']}")
    
    return True

async def cleanup_test_data(topic_cluster_id, new_topic_id, test_user_id):
    """Clean up test data from the database."""
    print("\n=== Cleaning up test data ===")
    
    db_provider = MongoDBProvider()
    
    # Delete nodes and edges for both topic clusters
    deleted_nodes1 = await db_provider.db.nodes.delete_many({
        "user_id": ObjectId(test_user_id),
        "topic_cluster_id": topic_cluster_id
    })
    
    deleted_nodes2 = await db_provider.db.nodes.delete_many({
        "user_id": ObjectId(test_user_id),
        "topic_cluster_id": new_topic_id
    })
    
    # Get IDs of remaining nodes for this user
    node_docs = await db_provider.db.nodes.find({"user_id": ObjectId(test_user_id)}).to_list(None)
    node_ids = [doc["_id"] for doc in node_docs]
    
    # Delete edges connected to this user's nodes
    deleted_edges = await db_provider.db.edges.delete_many({
        "user_id": ObjectId(test_user_id),
        "$or": [
            {"source_node_id": {"$in": node_ids}},
            {"target_node_id": {"$in": node_ids}}
        ]
    })
    
    # Delete any remaining nodes for this user
    deleted_remaining = await db_provider.db.nodes.delete_many({
        "user_id": ObjectId(test_user_id)
    })
    
    print(f"Deleted {deleted_nodes1.deleted_count + deleted_nodes2.deleted_count + deleted_remaining.deleted_count} nodes")
    print(f"Deleted {deleted_edges.deleted_count} edges")
    
    return True

async def main():
    """Run all tests."""
    try:
        # Setup test data
        topic_cluster_id, test_user_id, child_nodes = await setup_test_data()
        
        # Test export/import
        new_topic_id = await test_export_import(topic_cluster_id, test_user_id)
        
        # Test search
        await test_search(test_user_id)
        
        # Test graph search
        await test_graph_search(test_user_id, child_nodes)
        
        # Clean up test data
        await cleanup_test_data(topic_cluster_id, new_topic_id, test_user_id)
        
        print("\n=== All tests completed successfully ===")
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Close connections
        vector_provider = MongoDBVectorProvider()
        try:
            await vector_provider.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
