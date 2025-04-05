"""Abstraction generation system for the knowledge forest.

This module provides functionality for generating higher-level abstractions
from clusters of related knowledge nodes.
"""
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple, Callable

from forest.models import (
    Node, AbstractionLevel, NodeStatus, AbstractionCluster,
    StringId, RelationshipType
)
from storage.mongodb import MongoDBProvider
from forest.graph import KnowledgeGraphManager
from ai.base import TextGenerationModel
from ai.factory import get_text_generation_model
from common.config import get_settings
from common.exceptions import AbstractionError

settings = get_settings()
logger = logging.getLogger(__name__)


class AbstractionGenerator:
    """Generator for knowledge abstractions."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the abstraction generator.
        
        Args:
            storage_provider: Optional storage provider
            graph_manager: Optional knowledge graph manager
            text_model: Optional text generation model
        """
        self.storage = storage_provider
        self.graph_manager = graph_manager
        self.text_model = text_model
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize graph manager if not provided
        if self.graph_manager is None:
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
            
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
    
    #--------------------------------------------------------------------------
    # Public abstraction generation methods
    #--------------------------------------------------------------------------
    
    async def generate_abstractions(self,
                                 user_id: str,
                                 target_level: AbstractionLevel = AbstractionLevel.PRINCIPLE,
                                 topic_id: Optional[str] = None,
                                 max_abstractions: int = 5) -> List[Dict[str, Any]]:
        """Generate abstractions from existing nodes.
        
        Args:
            user_id: The user ID
            target_level: Target abstraction level
            topic_id: Optional topic ID to focus on
            max_abstractions: Maximum number of abstractions to generate
            
        Returns:
            List of generated abstraction nodes
            
        Raises:
            AbstractionError: If abstraction generation fails
        """
        try:
            # Find clusters suitable for abstraction
            clusters = await self._find_abstraction_clusters(
                user_id=user_id,
                target_level=target_level,
                topic_id=topic_id
            )
            
            # Sort clusters by coherence score (descending)
            clusters.sort(key=lambda x: x.coherence_score, reverse=True)
            
            # Limit the number of clusters to process
            clusters = clusters[:max_abstractions]
            
            # Generate abstractions from clusters
            abstractions = []
            
            for cluster in clusters:
                abstraction = await self._create_abstraction_from_cluster(user_id, cluster)
                
                if abstraction:
                    abstractions.append(abstraction)
                    
            return abstractions
            
        except Exception as e:
            logger.error(f"Failed to generate abstractions: {str(e)}")
            raise AbstractionError(f"Failed to generate abstractions: {str(e)}")
    
    async def generate_topic_abstraction(self,
                                      user_id: str,
                                      topic_id: str) -> Optional[Dict[str, Any]]:
        """Generate a high-level abstraction for an entire topic.
        
        Args:
            user_id: The user ID
            topic_id: Topic ID to abstract
            
        Returns:
            Generated abstraction node or None
            
        Raises:
            AbstractionError: If abstraction generation fails
        """
        try:
            # Get the topic node
            topic_node = await self.storage.get_document("nodes", topic_id)
            
            if not topic_node:
                raise AbstractionError(f"Topic node not found: {topic_id}")
                
            # Get all active nodes in this topic
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": NodeStatus.ACTIVE,
                    "topic_cluster_id": topic_id
                },
                projection={
                    "_id": 1,
                    "label": 1,
                    "summary": 1,
                    "abstraction_level": 1
                }
            )
            
            if len(nodes) < settings.abstraction.min_cluster_size:
                logger.info(f"Not enough nodes in topic {topic_id} for abstraction (found {len(nodes)})")
                return None
                
            # Extract key concepts from the topic
            key_concepts = []
            for node in nodes:
                if node.get("abstraction_level", 2) == AbstractionLevel.CONCEPT:
                    key_concepts.append(node.get("label", ""))
                    
            # Limit to most important concepts
            key_concepts = key_concepts[:10]
            
            # Generate abstraction content
            abstraction_label, abstraction_summary = await self._generate_topic_abstraction_content(
                topic_name=topic_node.get("label", "Unknown Topic"),
                key_concepts=key_concepts
            )
            
            # Create abstraction node
            abstraction_node = {
                "user_id": user_id,
                "label": abstraction_label,
                "type": "abstraction",
                "summary": abstraction_summary,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": AbstractionLevel.PARADIGM,  # Highest level
                "abstraction_source_ids": [node["_id"] for node in nodes],
                "abstraction_method": "topic_abstraction",
                "topic_cluster_id": topic_id,
                "importance_score": 0.8,  # High importance for topic abstractions
                "certainty_score": 0.7,
                "metadata": {
                    "source": "abstraction_generator",
                    "tags": ["topic_abstraction", "paradigm"],
                    "config": {
                        "auto_prune": False,  # Don't auto-prune paradigm abstractions
                        "importance_decay_rate": 0.002  # Very slow decay
                    }
                }
            }
            
            # Save to database
            abstraction_id = await self.storage.save_document("nodes", abstraction_node)
            
            # Add ID to the node
            abstraction_node["_id"] = abstraction_id
            
            # Create relationships to key nodes
            for node in nodes:
                if node.get("abstraction_level", 2) >= AbstractionLevel.PRINCIPLE:
                    # Only link to higher-level nodes
                    edge = {
                        "user_id": user_id,
                        "source_node_id": node["_id"],
                        "target_node_id": abstraction_id,
                        "relationship_type": RelationshipType.ABSTRACTED_BY,
                        "strength": 0.8,
                        "created_at": datetime.utcnow(),
                        "is_active": True,
                        "source": "abstraction_generator",
                        "certainty_score": 0.7
                    }
                    
                    await self.storage.save_document("edges", edge)
                    
            return abstraction_node
            
        except Exception as e:
            logger.error(f"Failed to generate topic abstraction: {str(e)}")
            raise AbstractionError(f"Failed to generate topic abstraction: {str(e)}")

    #--------------------------------------------------------------------------
    # Cluster identification and management
    #--------------------------------------------------------------------------
    
    async def _find_abstraction_clusters(self,
                                      user_id: str,
                                      target_level: AbstractionLevel,
                                      topic_id: Optional[str] = None) -> List[AbstractionCluster]:
        """Find clusters of nodes that can be abstracted.
        
        Args:
            user_id: The user ID
            target_level: Target abstraction level
            topic_id: Optional topic ID to focus on
            
        Returns:
            List of abstraction clusters
        """
        # Determine source level(s) to look for
        source_levels = []
        
        if target_level == AbstractionLevel.RULE:
            source_levels = [AbstractionLevel.CONCEPT, AbstractionLevel.INSTANCE]
        elif target_level == AbstractionLevel.PRINCIPLE:
            source_levels = [AbstractionLevel.RULE, AbstractionLevel.CONCEPT]
        elif target_level == AbstractionLevel.PARADIGM:
            source_levels = [AbstractionLevel.PRINCIPLE, AbstractionLevel.RULE]
        else:
            # Default behavior
            source_levels = [target_level - 1]
            
        # Filter nodes by level
        query = {
            "user_id": user_id,
            "status": NodeStatus.ACTIVE,
            "abstraction_level": {"$in": source_levels}
        }
        
        # Add topic filter if provided
        if topic_id:
            query["topic_cluster_id"] = topic_id
            
        # Get nodes
        nodes = await self.storage.find_documents(
            "nodes",
            query,
            projection={
                "_id": 1,
                "label": 1,
                "summary": 1,
                "topic_cluster_id": 1,
                "embedding": 1,
                "abstraction_level": 1
            }
        )
        
        # Group nodes by topic
        nodes_by_topic = {}
        for node in nodes:
            topic = node.get("topic_cluster_id")
            if not topic:
                continue
                
            if topic not in nodes_by_topic:
                nodes_by_topic[topic] = []
                
            nodes_by_topic[topic].append(node)
            
        # Generate clusters from each topic group
        clusters = []
        
        for topic, topic_nodes in nodes_by_topic.items():
            # Skip topics with too few nodes
            if len(topic_nodes) < settings.abstraction.min_cluster_size:
                continue
                
            # Generate clusters using embedding-based clustering
            topic_clusters = self._cluster_nodes_by_embedding(
                nodes=topic_nodes,
                target_level=target_level,
                similarity_threshold=settings.abstraction.similarity_threshold
            )
            
            clusters.extend(topic_clusters)
            
        return clusters
    
    def _cluster_nodes_by_embedding(self,
                                 nodes: List[Dict[str, Any]],
                                 target_level: AbstractionLevel,
                                 similarity_threshold: float) -> List[AbstractionCluster]:
        """Cluster nodes based on embedding similarity.
        
        Args:
            nodes: List of nodes to cluster
            target_level: Target abstraction level
            similarity_threshold: Similarity threshold for clustering
            
        Returns:
            List of abstraction clusters
        """
        # Filter nodes with embeddings
        nodes_with_embeddings = [node for node in nodes if node.get("embedding")]
        
        if len(nodes_with_embeddings) < settings.abstraction.min_cluster_size:
            return []
            
        # Simple greedy clustering approach (for optimization, a more sophisticated algorithm would be used)
        clusters = []
        remaining_nodes = nodes_with_embeddings.copy()
        
        while len(remaining_nodes) >= settings.abstraction.min_cluster_size:
            # Take the first node as a seed
            seed_node = remaining_nodes[0]
            cluster_nodes = [seed_node]
            cluster_node_ids = [seed_node["_id"]]
            remaining_nodes.remove(seed_node)
            
            # Find similar nodes
            for node in remaining_nodes[:]:  # Copy to allow removal during iteration
                # Calculate similarity to seed node
                similarity = self._calculate_embedding_similarity(
                    seed_node.get("embedding", []),
                    node.get("embedding", [])
                )
                
                if similarity >= similarity_threshold:
                    cluster_nodes.append(node)
                    cluster_node_ids.append(node["_id"])
                    remaining_nodes.remove(node)
                    
                    # Break if we've reached a reasonable cluster size
                    if len(cluster_nodes) >= 10:
                        break
            
            # Only create a cluster if it has enough nodes
            if len(cluster_nodes) >= settings.abstraction.min_cluster_size:
                # Calculate centroid
                centroid = self._calculate_centroid([node.get("embedding", []) for node in cluster_nodes])
                
                # Generate a suggested label and summary
                suggested_label, suggested_summary = self._generate_cluster_label_summary(cluster_nodes)
                
                # Create the cluster
                cluster = AbstractionCluster(
                    source_node_ids=cluster_node_ids,
                    centroid_vector=centroid,
                    coherence_score=self._calculate_cluster_coherence(cluster_nodes, centroid),
                    common_topic_id=seed_node.get("topic_cluster_id"),
                    suggested_label=suggested_label,
                    suggested_summary=suggested_summary,
                    abstraction_level=target_level
                )
                
                clusters.append(cluster)
        
        return clusters
    
    def _calculate_embedding_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0-1)
        """
        # Handle empty embeddings
        if not embedding1 or not embedding2:
            return 0.0
            
        # Handle different lengths
        if len(embedding1) != len(embedding2):
            return 0.0
            
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Calculate magnitudes
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        # Handle zero magnitudes
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
            
        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Ensure result is in valid range
        return max(0.0, min(1.0, similarity))
    
    def _calculate_centroid(self, embeddings: List[List[float]]) -> List[float]:
        """Calculate centroid vector of a group of embeddings.
        
        Args:
            embeddings: List of embedding vectors
            
        Returns:
            Centroid vector
        """
        # Handle empty input
        if not embeddings:
            return []
            
        # Handle embeddings of different lengths
        min_dim = min(len(emb) for emb in embeddings)
        
        # Calculate sum of each dimension
        dimension_sums = [0.0] * min_dim
        
        for embedding in embeddings:
            for i in range(min_dim):
                dimension_sums[i] += embedding[i]
                
        # Calculate average
        centroid = [dimension_sum / len(embeddings) for dimension_sum in dimension_sums]
        
        return centroid
    
    def _calculate_cluster_coherence(self, nodes: List[Dict[str, Any]], centroid: List[float]) -> float:
        """Calculate coherence score for a cluster.
        
        Args:
            nodes: List of nodes in the cluster
            centroid: Centroid vector of the cluster
            
        Returns:
            Coherence score (0-1)
        """
        # Calculate average similarity to centroid
        similarities = []
        
        for node in nodes:
            embedding = node.get("embedding", [])
            
            if embedding:
                similarity = self._calculate_embedding_similarity(embedding, centroid)
                similarities.append(similarity)
                
        # Handle empty list
        if not similarities:
            return 0.0
            
        # Calculate average
        return sum(similarities) / len(similarities)
    
    def _generate_cluster_label_summary(self, nodes: List[Dict[str, Any]]) -> Tuple[str, str]:
        """Generate a label and summary for a cluster (synchronous placeholder).
        
        Args:
            nodes: List of nodes in the cluster
            
        Returns:
            Tuple of (label, summary)
        """
        # Placeholder implementation (actual implementation would use AI to generate a proper label)
        node_labels = [node.get("label", "") for node in nodes]
        
        # Take the most common word as a starting point
        word_counts = {}
        for label in node_labels:
            for word in label.split():
                word = word.lower().strip(".,;:!?-")
                if word and len(word) > 3:  # Skip short words
                    word_counts[word] = word_counts.get(word, 0) + 1
                    
        common_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        if common_words:
            label = f"Abstract: {common_words[0][0].title()}"
        else:
            label = "Abstract Concept"
            
        # Create a simple summary
        summary = f"Abstraction of {len(nodes)} related concepts: {', '.join(node_labels[:3])}"
        if len(nodes) > 3:
            summary += f" and {len(nodes) - 3} more"
            
        return label, summary
    
    #--------------------------------------------------------------------------
    # AI-assisted content generation
    #--------------------------------------------------------------------------
    
    async def _generate_abstraction_content(self,
                                        node_labels: List[str],
                                        node_summaries: List[str],
                                        target_level: AbstractionLevel) -> Tuple[str, str]:
        """Generate label and summary for an abstraction using AI.
        
        Args:
            node_labels: List of node labels
            node_summaries: List of node summaries
            target_level: Target abstraction level
            
        Returns:
            Tuple of (label, summary)
        """
        # Prepare the input
        level_names = {
            AbstractionLevel.RULE: "rule or relationship",
            AbstractionLevel.PRINCIPLE: "principle or theory",
            AbstractionLevel.PARADIGM: "paradigm or framework"
        }
        level_name = level_names.get(target_level, "higher-level concept")
        
        # Prepare the prompt
        prompt = f"""I'll provide you with several related concepts and their descriptions. 
        Please identify a {level_name} that these concepts exemplify or are part of.

        Concepts:
        {', '.join(node_labels)}

        Details:
        {'; '.join(node_summaries[:5])}

        Based on these concepts, please provide:
        1. A concise label for the {level_name} (3-5 words)
        2. A brief summary explaining this {level_name} (2-3 sentences)

        Format your response as:
        Label: [your label]
        Summary: [your summary]
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Parse the response
        label = "Abstract Concept"
        summary = "Generated abstraction from related concepts."
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                if line.startswith("Label:"):
                    label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    summary = line.replace("Summary:", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse abstraction response: {str(e)}")
            
        return label, summary
    
    async def _generate_topic_abstraction_content(self,
                                              topic_name: str,
                                              key_concepts: List[str]) -> Tuple[str, str]:
        """Generate label and summary for a topic-level abstraction using AI.
        
        Args:
            topic_name: Topic name
            key_concepts: List of key concept names
            
        Returns:
            Tuple of (label, summary)
        """
        # Prepare the prompt
        prompt = f"""I'll provide you with a topic name and its key concepts. 
        Please identify a high-level paradigm or framework that encapsulates these concepts.

        Topic: {topic_name}

        Key Concepts:
        {', '.join(key_concepts)}

        Based on this information, please provide:
        1. A concise label for the paradigm or framework (3-5 words)
        2. A brief summary explaining this paradigm/framework (2-3 sentences)

        Format your response as:
        Label: [your label]
        Summary: [your summary]
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=500)
        
        # Parse the response
        label = f"{topic_name} Paradigm"
        summary = f"High-level paradigm encompassing key concepts in {topic_name}."
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                if line.startswith("Label:"):
                    label = line.replace("Label:", "").strip()
                elif line.startswith("Summary:"):
                    summary = line.replace("Summary:", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse topic abstraction response: {str(e)}")
            
        return label, summary
    
    #--------------------------------------------------------------------------
    # Abstraction creation methods
    #--------------------------------------------------------------------------
    
    async def _create_abstraction_from_cluster(self,
                                           user_id: str,
                                           cluster: AbstractionCluster) -> Optional[Dict[str, Any]]:
        """Create an abstraction node from a cluster.
        
        Args:
            user_id: The user ID
            cluster: The abstraction cluster
            
        Returns:
            Created abstraction node or None
        """
        try:
            # Get nodes from cluster for more detailed information
            node_details = []
            for node_id in cluster.source_node_ids:
                node = await self.storage.get_document("nodes", node_id)
                if node:
                    node_details.append(node)
            
            # Get node labels and summaries for content generation
            node_labels = [node.get("label", "") for node in node_details if node.get("label")]
            node_summaries = [node.get("summary", "") for node in node_details if node.get("summary")]
            
            # Generate content if not provided in cluster
            label = cluster.suggested_label
            summary = cluster.suggested_summary
            
            # If label or summary is missing, generate them
            if not label or not summary:
                generated_label, generated_summary = await self._generate_abstraction_content(
                    node_labels=node_labels,
                    node_summaries=node_summaries,
                    target_level=cluster.abstraction_level
                )
                
                label = label or generated_label
                summary = summary or generated_summary
            
            # Create the abstraction node
            abstraction_node = {
                "user_id": user_id,
                "label": label,
                "type": "abstraction",
                "summary": summary,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": NodeStatus.ACTIVE,
                "abstraction_level": cluster.abstraction_level,
                "abstraction_source_ids": cluster.source_node_ids,
                "abstraction_method": "cluster_based",
                "topic_cluster_id": cluster.common_topic_id,
                "importance_score": 0.7,  # Start with moderately high importance
                "certainty_score": 0.6,  # Moderate certainty
                "metadata": {
                    "source": "abstraction_generator",
                    "tags": ["abstraction", f"level_{cluster.abstraction_level}"],
                    "config": {
                        "auto_prune": False,  # Don't auto-prune abstractions
                        "importance_decay_rate": 0.005  # Slower decay for abstractions
                    }
                }
            }
            
            # Save to database
            abstraction_id = await self.storage.save_document("nodes", abstraction_node)
            
            # Add ID to the node
            abstraction_node["_id"] = abstraction_id
            
            # Create edges connecting source nodes to this abstraction
            for source_id in cluster.source_node_ids:
                edge = {
                    "user_id": user_id,
                    "source_node_id": source_id,
                    "target_node_id": abstraction_id,
                    "relationship_type": RelationshipType.ABSTRACTED_BY,
                    "strength": 0.8,
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "source": "abstraction_generator",
                    "certainty_score": 0.7
                }
                
                await self.storage.save_document("edges", edge)
                
            return abstraction_node
            
        except Exception as e:
            logger.error(f"Failed to create abstraction from cluster: {str(e)}")
            return None
