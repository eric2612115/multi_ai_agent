"""Enhanced retrieval service for Knowledge Forest.

This service implements RAG (Retrieval Augmented Generation) capabilities
to help the AI agent's cognitive processes by providing relevant context
from the knowledge forest when performing reasoning tasks.
"""
import logging
from typing import List, Dict, Any, Optional, Union, Tuple

from src.storage.vector_search import VectorSearch, MongoDBVectorProvider
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.ai.factory import get_embedding_model
from src.common.service_base import ServiceBase

settings = get_settings()
logger = logging.getLogger(__name__)

class RetrievalService(ServiceBase):
    """Service for context retrieval from the knowledge forest."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                vector_provider: Optional[MongoDBVectorProvider] = None):
        """Initialize the retrieval service.
        
        Args:
            storage_provider: Optional storage provider
            vector_provider: Optional vector storage provider
        """
        super().__init__()
        self.storage = storage_provider or MongoDBProvider()
        self.vector_provider = vector_provider or MongoDBVectorProvider()
        self.vector_search = None
        self.embedding_model = None
        
    async def initialize(self):
        """Initialize service connections."""
        if not await self.storage.is_connected():
            await self.storage.connect()
            
        self.vector_search = await VectorSearch.create(self.vector_provider)
        self.embedding_model = get_embedding_model()
        
    async def retrieve_relevant_context(self, 
                                     user_id: str, 
                                     query_text: str, 
                                     k: int = 10, 
                                     min_similarity: float = 0.65,
                                     include_source_texts: bool = True,
                                     topic_cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve context relevant to a query from the knowledge forest.
        
        Args:
            user_id: The user ID
            query_text: Text describing the current task or focus
            k: Maximum number of context items to retrieve
            min_similarity: Minimum similarity threshold
            include_source_texts: Include source texts in results
            topic_cluster_id: Optional topic cluster ID to restrict search
            
        Returns:
            List of relevant context items with metadata
        """
        if not self.embedding_model or not self.vector_search:
            await self.initialize()
            
        # Generate embedding for query text
        query_embedding = await self.embedding_model.generate_embedding(query_text)
        
        # Search for similar nodes
        similar_nodes = await self.vector_search.search_nodes(
            user_id=user_id,
            query_embedding=query_embedding,
            limit=k,
            min_similarity=min_similarity,
            topic_cluster_id=topic_cluster_id
        )
        
        # Process results
        context_items = []
        for node in similar_nodes:
            item = {
                "node_id": node["_id"],
                "similarity_score": node.get("searchScore", 0),
                "type": node.get("type", "unknown"),
                "abstraction_level": node.get("abstraction_level", 0),
                "topic_id": node.get("topic_cluster_id", "unknown")
            }
            
            if include_source_texts:
                item["label"] = node.get("label", "")
                item["summary"] = node.get("summary", "")
                # Don't include the full content or entities to avoid context overload
            
            context_items.append(item)
            
        return context_items
    
    async def retrieve_structured_context(self,
                                      user_id: str,
                                      node_id: str,
                                      max_hops: int = 2,
                                      max_nodes: int = 20) -> Dict[str, Any]:
        """Retrieve structured context by traversing the graph from a starting node.
        
        Args:
            user_id: The user ID
            node_id: The starting node ID
            max_hops: Maximum number of hops to traverse
            max_nodes: Maximum number of nodes to include
            
        Returns:
            Structured context with nodes and edges
        """
        if not await self.storage.is_connected():
            await self.storage.connect()
            
        # Start with the seed node
        seed_node = await self.storage.get_document("nodes", node_id)
        if not seed_node:
            return {"nodes": [], "edges": []}
            
        # Ensure it belongs to the user
        if seed_node.get("user_id") != user_id:
            return {"nodes": [], "edges": []}
            
        # Initialize result containers
        visited_nodes = {node_id: seed_node}
        edges_map = {}
        frontier = [(node_id, 0)]  # (node_id, hop_distance)
        current_hop = 0
        
        # Breadth-first search up to max_hops
        while frontier and len(visited_nodes) < max_nodes:
            current_id, current_hop = frontier.pop(0)
            
            # Stop if we've reached max_hops
            if current_hop >= max_hops:
                continue
                
            # Find all edges connected to this node
            edges = await self.storage.find_documents(
                "edges",
                {
                    "user_id": user_id,
                    "$or": [
                        {"source_node_id": current_id},
                        {"target_node_id": current_id}
                    ]
                }
            )
            
            # Process each edge
            for edge in edges:
                edge_id = edge["_id"]
                
                # Skip if we've seen this edge
                if edge_id in edges_map:
                    continue
                    
                # Add edge to results
                edges_map[edge_id] = edge
                
                # Determine the other end of the edge
                other_id = edge["target_node_id"] if edge["source_node_id"] == current_id else edge["source_node_id"]
                
                # Skip if we've already visited this node
                if other_id in visited_nodes:
                    continue
                    
                # Retrieve the other node
                other_node = await self.storage.get_document("nodes", other_id)
                if not other_node:
                    continue
                    
                # Add node to results
                visited_nodes[other_id] = other_node
                
                # Add to frontier for next hop
                frontier.append((other_id, current_hop + 1))
                
                # Break if we've reached max_nodes
                if len(visited_nodes) >= max_nodes:
                    break
        
        # Prepare final result
        result = {
            "nodes": list(visited_nodes.values()),
            "edges": list(edges_map.values())
        }
        
        return result
    
    async def evaluate_knowledge_quality(self, 
                                      user_id: str,
                                      nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate the quality of a set of knowledge nodes.
        
        Args:
            user_id: The user ID
            nodes: List of nodes to evaluate
            
        Returns:
            Quality assessment results
        """
        # Skip if no nodes
        if not nodes:
            return {
                "average_quality": 0.0,
                "issues": [],
                "recommendations": []
            }
            
        # Evaluate node quality based on multiple factors
        quality_scores = []
        issues = []
        
        for node in nodes:
            # Base quality factors
            has_label = bool(node.get("label"))
            has_summary = len(node.get("summary", "")) > 20
            has_entities = len(node.get("entities", [])) > 0
            verification = node.get("verification_status") == "verified"
            certainty = node.get("certainty_score", 0.5)
            
            # Calculate node quality
            node_quality = 0.0
            node_quality += 0.1 if has_label else 0.0
            node_quality += 0.3 if has_summary else 0.0
            node_quality += 0.2 if has_entities else 0.0
            node_quality += 0.2 if verification else 0.0
            node_quality += 0.2 * certainty
            
            quality_scores.append(node_quality)
            
            # Identify issues
            if not has_label or not has_summary:
                issues.append({
                    "node_id": node["_id"],
                    "type": "incomplete_metadata",
                    "description": "Node is missing a label or proper summary"
                })
                
            if certainty < 0.4:
                issues.append({
                    "node_id": node["_id"],
                    "type": "low_certainty",
                    "description": "Node has low certainty score"
                })
        
        # Calculate average quality
        average_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        # Generate recommendations
        recommendations = []
        
        if average_quality < 0.6:
            recommendations.append({
                "type": "content_verification",
                "description": "Verify and improve the metadata of low-quality nodes",
                "priority": "high"
            })
            
        # Check for contradictions (simplified)
        if len(nodes) > 3:  # Only check if we have enough nodes
            recommendations.append({
                "type": "consistency_check",
                "description": "Check for logical consistency between related nodes",
                "priority": "medium"
            })
        
        return {
            "average_quality": average_quality,
            "issues": issues,
            "recommendations": recommendations
        }
    
    async def retrieve_and_format_context_for_llm(self,
                                              user_id: str,
                                              query_text: str,
                                              k: int = 7,
                                              min_similarity: float = 0.65) -> str:
        """Retrieve context and format it for inclusion in an LLM prompt.
        
        Args:
            user_id: The user ID
            query_text: Text describing the current task or focus
            k: Maximum number of context items to retrieve
            min_similarity: Minimum similarity threshold
            
        Returns:
            Formatted context string ready for inclusion in an LLM prompt
        """
        context_items = await self.retrieve_relevant_context(
            user_id=user_id,
            query_text=query_text,
            k=k,
            min_similarity=min_similarity,
            include_source_texts=True
        )
        
        if not context_items:
            return "No relevant context found in the knowledge forest."
        
        # Format context for inclusion in prompt
        formatted_context = "RELEVANT KNOWLEDGE FROM FOREST:\n\n"
        
        for i, item in enumerate(context_items, 1):
            formatted_context += f"{i}. Node: {item.get('label', 'Untitled')}\n"
            formatted_context += f"   Summary: {item.get('summary', 'No summary')}\n"
            formatted_context += f"   Type: {item.get('type', 'Unknown')} | Relevance: {item.get('similarity_score', 0):.2f}\n\n"
        
        return formatted_context