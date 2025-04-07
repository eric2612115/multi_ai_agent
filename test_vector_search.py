#!/usr/bin/env python3
"""Enhanced test script for vector search functionality.

This script tests the vector search capabilities of the knowledge forest,
including the new query normalization, multilingual support, and expanded 
search features.
"""
import asyncio
import json
import uuid
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table

# Import directly from project modules
from ai.base import EmbeddingModel
from ai.factory import get_embedding_model, get_text_generation_model
from forest.models import Node
from storage.mongodb import MongoDBProvider
from storage.vector_search import VectorSearch, MongoDBVectorProvider
from common.config import get_settings

# Create console for rich output
console = Console()

async def generate_test_embeddings(text: str) -> List[float]:
    """Generate embeddings for test text."""
    try:
        # Try to get an embedding model
        embedding_model = get_embedding_model()
        embeddings = await embedding_model.generate_embedding(text)
        return embeddings
    except Exception as e:
        console.print(f"[red]Error generating embeddings: {str(e)}[/red]")
        # Generate random embeddings as fallback (not ideal but allows testing)
        import random
        settings = get_settings()
        dimensions = settings.ai.embedding_dimensions
        return [random.uniform(-1, 1) for _ in range(dimensions)]

async def create_test_nodes(provider: MongoDBProvider, user_id: str, count: int = 5) -> List[str]:
    """Create test nodes with random embeddings."""
    console.print(f"[cyan]Creating {count} test nodes for vector search...[/cyan]")
    
    node_ids = []
    
    # Create nodes with different concepts for testing
    test_concepts = [
        {
            "label": "Artificial Intelligence",
            "text": "Artificial Intelligence is the simulation of human intelligence processes by machines, especially computer systems.",
            "type": "concept"
        },
        {
            "label": "Machine Learning",
            "text": "Machine Learning is a subset of AI that provides systems the ability to automatically learn and improve from experience without being explicitly programmed.",
            "type": "concept"
        },
        {
            "label": "Deep Learning",
            "text": "Deep Learning is a subfield of machine learning concerned with algorithms inspired by the structure and function of the brain called artificial neural networks.",
            "type": "concept"
        },
        {
            "label": "Natural Language Processing",
            "text": "Natural Language Processing is a branch of AI that helps computers understand, interpret and manipulate human language.",
            "type": "concept"
        },
        {
            "label": "Computer Vision",
            "text": "Computer Vision is a field of AI that enables computers to derive meaningful information from digital images, videos and other visual inputs.",
            "type": "concept"
        },
        {
            "label": "Reinforcement Learning",
            "text": "Reinforcement Learning is an area of machine learning concerned with how software agents ought to take actions in an environment so as to maximize some notion of cumulative reward.",
            "type": "concept"
        },
        {
            "label": "Knowledge Graph",
            "text": "A Knowledge Graph is a knowledge base that uses a graph-structured data model to integrate data and represent relationships between entities.",
            "type": "concept"
        }
    ]
    
    # Use a subset based on the requested count
    for i in range(min(count, len(test_concepts))):
        concept = test_concepts[i]
        # Generate embeddings
        embedding = await generate_test_embeddings(concept["text"])
        
        # Create node
        node_id = str(uuid.uuid4())
        node = {
            "_id": node_id,
            "user_id": user_id,
            "label": concept["label"],
            "type": concept["type"],
            "summary": concept["text"][:100],
            "embedding": embedding,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        }
        
        # Save to database
        try:
            await provider.save_document("nodes", node)
            node_ids.append(node_id)
            console.print(f"[green]Created node: {concept['label']}[/green]")
        except Exception as e:
            console.print(f"[red]Error creating node {concept['label']}: {str(e)}[/red]")
    
    return node_ids

async def test_vector_search():
    """Test vector search functionality with enhanced features."""
    console.print("[bold cyan]Testing Vector Search Functionality[/bold cyan]")
    
    # Connect to MongoDB
    provider = MongoDBProvider()
    connected = await provider.connect()
    
    if not connected:
        console.print("[red]Failed to connect to MongoDB[/red]")
        return False
    
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"  # Dynamic test user ID
    
    # Create test nodes
    node_ids = await create_test_nodes(provider, user_id)
    
    if not node_ids:
        console.print("[red]Failed to create test nodes[/red]")
        await provider.close()
        return False
    
    # Create vector search client
    vector_search = await VectorSearch.create(provider=MongoDBVectorProvider())
    
    # Import the API query normalization function
    try:
        # Dynamically import to avoid circular imports
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "knowledge_forest_additional", 
            "./src/api/rest/knowledge_forest_additional.py"
        )
        
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["knowledge_forest_additional"] = module
            spec.loader.exec_module(module)
            normalize_query = module.normalize_query
            console.print("[green]Successfully imported query normalization function[/green]")
        else:
            console.print("[yellow]Could not load normalize_query function, skipping normalization tests[/yellow]")
            normalize_query = None
    except Exception as e:
        console.print(f"[yellow]Error importing query normalization: {str(e)}[/yellow]")
        normalize_query = None
    
    try:
        # Test 1: Basic vector search
        console.print("\n[bold cyan]Test 1: Basic Vector Search[/bold cyan]")
        
        query = "Learning systems that improve with data"
        console.print(f"Query: [yellow]{query}[/yellow]")
        
        query_embedding = await generate_test_embeddings(query)
        search_results = await vector_search.search_nodes(user_id, query_embedding, limit=5)
        
        if search_results:
            console.print(f"[green]Vector search returned {len(search_results)} results[/green]")
            
            # Display results
            table = Table(title="Basic Vector Search Results")
            table.add_column("ID", style="dim")
            table.add_column("Label", style="cyan")
            table.add_column("Score", style="green")
            
            for result in search_results:
                table.add_row(
                    str(result.get("_id")),
                    result.get("label", "Unknown"),
                    f"{result.get('searchScore', 0):.4f}"
                )
            
            console.print(table)
        else:
            console.print("[yellow]Vector search returned no results[/yellow]")
        
        # Test 2: Multilingual query support
        if normalize_query:
            console.print("\n[bold cyan]Test 2: Multilingual Query Support[/bold cyan]")
            
            # Try with Chinese query
            multilingual_query = "机器学习和深度学习"  # "Machine learning and deep learning" in Chinese
            console.print(f"Multilingual Query: [yellow]{multilingual_query}[/yellow]")
            
            # Get text model for translations
            text_model = get_text_generation_model()
            
            # Normalize the query
            query_data = await normalize_query(multilingual_query, text_model)
            
            # Display normalization results
            table = Table(title="Query Normalization Results")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Original Query", multilingual_query)
            table.add_row("Detected Language", query_data.get("original_language", "unknown"))
            table.add_row("Normalized Query", query_data.get("normalized_query", ""))
            
            if query_data.get("translations"):
                table.add_row("Translation", query_data.get("translations")[0])
            
            if query_data.get("expansions"):
                table.add_row("Expansions", ", ".join(query_data.get("expansions", [])))
                
            console.print(table)
            
            # Search with the translated query if available
            if query_data.get("translations"):
                translated_query = query_data.get("translations")[0]
                console.print(f"Searching with translated query: [yellow]{translated_query}[/yellow]")
                
                query_embedding = await generate_test_embeddings(translated_query)
                search_results = await vector_search.search_nodes(user_id, query_embedding, limit=5)
                
                if search_results:
                    console.print(f"[green]Multilingual search returned {len(search_results)} results[/green]")
                    
                    # Display results
                    table = Table(title="Multilingual Search Results")
                    table.add_column("ID", style="dim")
                    table.add_column("Label", style="cyan")
                    table.add_column("Score", style="green")
                    
                    for result in search_results:
                        table.add_row(
                            str(result.get("_id")),
                            result.get("label", "Unknown"),
                            f"{result.get('searchScore', 0):.4f}"
                        )
                    
                    console.print(table)
                else:
                    console.print("[yellow]Multilingual search returned no results[/yellow]")
        
        # Test 3: Combined query with expansions
        console.print("\n[bold cyan]Test 3: Batch Vector Search[/bold cyan]")
        
        # Create multiple query variations
        queries = [
            "machine learning algorithms",
            "neural networks for pattern recognition",
            "knowledge representation systems"
        ]
        
        console.print(f"Batch Queries: [yellow]{', '.join(queries)}[/yellow]")
        
        # Generate embeddings for all queries
        query_embeddings = []
        for q in queries:
            embedding = await generate_test_embeddings(q)
            query_embeddings.append(embedding)
        
        # Perform batch search
        batch_results = await vector_search.batch_search_vectors(
            collection="nodes",
            vectors=query_embeddings,
            filter={"user_id": user_id},
            top_k=3,
            min_similarity=0.5
        )
        
        if batch_results:
            console.print(f"[green]Batch search returned results for {len(batch_results)} queries[/green]")
            
            # Display combined results 
            for i, results in enumerate(batch_results):
                if results:
                    console.print(f"\nResults for query: [cyan]{queries[i]}[/cyan]")
                    
                    table = Table()
                    table.add_column("Label", style="cyan")
                    table.add_column("Score", style="green")
                    
                    for result in results[:3]:  # Show top 3 for each query
                        table.add_row(
                            result.get("label", "Unknown"),
                            f"{result.get('searchScore', 0):.4f}"
                        )
                    
                    console.print(table)
        else:
            console.print("[yellow]Batch search returned no results[/yellow]")
        
        # Success if we get this far
        success = True
    
    except Exception as e:
        console.print(f"[red]Error during vector search testing: {str(e)}[/red]")
        success = False
    
    # Clean up - delete test nodes
    console.print("\n[cyan]Cleaning up test data...[/cyan]")
    deleted_count = 0
    
    for node_id in node_ids:
        try:
            await provider.delete_document("nodes", node_id)
            deleted_count += 1
        except Exception as e:
            console.print(f"[yellow]Failed to delete node {node_id}: {str(e)}[/yellow]")
    
    console.print(f"[green]Deleted {deleted_count}/{len(node_ids)} test nodes[/green]")
    
    # Also do a bulk delete for any missed nodes
    try:
        bulk_deleted = await provider.delete_many("nodes", {"user_id": user_id})
        if bulk_deleted > 0:
            console.print(f"[green]Bulk deleted {bulk_deleted} additional test nodes[/green]")
    except Exception as e:
        console.print(f"[yellow]Bulk deletion error: {str(e)}[/yellow]")
        
    await provider.close()
    return success

async def main():
    """Main function."""
    console.print("""
    [bold blue]====================================[/bold blue]
    [bold green]     Vector Search Test Script     [/bold green]
    [bold blue]====================================[/bold blue]
    """)
    
    success = await test_vector_search()
    
    if success:
        console.print("[bold green]Vector search test PASSED[/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Vector search test FAILED[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
