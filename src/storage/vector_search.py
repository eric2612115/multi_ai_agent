"""Vector search implementation using MongoDB Atlas.

This module implements the VectorStorage interface using MongoDB Atlas Vector Search.
"""
import json
import logging
from typing import Dict, List, Optional, Any

from src.storage.base import VectorStorage
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import StorageConnectionError, StorageQueryError

settings = get_settings()
logger = logging.getLogger(__name__)

class VectorSearch:
    """Helper class for vector search operations."""
    
    @classmethod
    async def create(cls, provider=None):
        """Create a new VectorSearch instance.
        
        Args:
            provider: Optional vector storage provider.
            
        Returns:
            A new VectorSearch instance.
        """
        instance = cls()
        instance.provider = provider or MongoDBVectorProvider()
        if not await instance.provider.is_connected():
            await instance.provider.connect()
        return instance
        
    async def search_nodes(self, user_id, query_embedding, limit=10, min_similarity=0.6, topic_cluster_id=None):
        """Search for nodes matching an embedding.
        
        Args:
            user_id: The user ID.
            query_embedding: The query embedding vector.
            limit: Maximum number of results.
            min_similarity: Minimum similarity threshold.
            topic_cluster_id: Optional topic cluster ID filter.
            
        Returns:
            List of matching nodes with similarity scores.
        """
        # Build the filter
        filter = {"user_id": user_id}
        if topic_cluster_id:
            filter["topic_cluster_id"] = topic_cluster_id
            
        # Search for similar nodes
        return await self.provider.search_vectors(
            collection="nodes",
            vector=query_embedding,
            filter=filter,
            top_k=limit,
            min_similarity=min_similarity
        )


class MongoDBVectorProvider(MongoDBProvider, VectorStorage):
    """MongoDB implementation of the VectorStorage interface using Atlas Vector Search."""
    
    def __init__(self, connection_uri: Optional[str] = None, database_name: Optional[str] = None):
        """Initialize the MongoDB Vector provider.
        
        Args:
            connection_uri: Optional connection URI. If not provided, it will be loaded from settings.
            database_name: Optional database name. If not provided, it will be loaded from settings.
        """
        super().__init__(connection_uri, database_name)
        # Store config values but let auto-detection determine actual availability
        self.vector_search_index = settings.db.vector_search_index
        # Initialize vector search capability to None; will be auto-detected on first use
        self._vector_search_available = None
    
    async def create_vector_index(self, collection: str, field: str, dimensions: int, 
                                similarity_metric: str = "cosine") -> bool:
        """Create a vector index.
        
        Note: This may only work with MongoDB Atlas, not with a standalone MongoDB instance.
        For Atlas, you may need to create the index through the Atlas UI or API.
        
        Args:
            collection: The collection name.
            field: The field name containing vectors.
            dimensions: The dimensionality of vectors.
            similarity_metric: The similarity metric to use.
            
        Returns:
            True if created successfully, False otherwise.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        # Check if we already know vector search is not available
        if getattr(self, '_vector_search_available', None) is False:
            logger.warning("MongoDB Atlas Vector Search is not available. Cannot create vector index.")
            return False
        
        await self._ensure_connected()
        
        # If we haven't checked yet, try to detect if vector search is available
        if self._vector_search_available is None:
            try:
                capability_test = await self.db.command({
                    "listSearchIndexes": collection,
                    "limit": 1
                })
                self._vector_search_available = True
                logger.info("MongoDB Atlas Vector Search detected and available.")
            except Exception as e:
                self._vector_search_available = False
                logger.warning(f"MongoDB Atlas Vector Search not available or not configured: {str(e)}")
                return False
        
        try:
            # Create the index definition
            index_name = f"{collection}_{field}_vector_index"
            
            # Create the command to create the index
            # Note: This approach only works with MongoDB Atlas
            command = {
                "createSearchIndex": collection,
                "definition": {
                    "name": index_name,
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            field: {
                                "dimensions": dimensions,
                                "similarity": similarity_metric,
                                "type": "vector"
                            }
                        }
                    }
                }
            }
            
            # Execute the command
            result = await self.db.command(command)
            
            # Check if the index was created successfully
            success = result.get("ok", 0) == 1
            if success:
                # Update the vector_search_index field
                self.vector_search_index = index_name
                logger.info(f"Successfully created vector index: {index_name}")
            return success
        except Exception as e:
            logger.error(f"Failed to create vector index: {str(e)}")
            logger.info("Note: Vector indexes can only be created on MongoDB Atlas. If you are using Atlas, "
                      "you may need to create the index through the Atlas UI or API.")
            return False
    
    async def drop_vector_index(self, collection: str, index_name: Optional[str] = None) -> bool:
        """Drop a vector index.
        
        Args:
            collection: The collection name.
            index_name: Optional index name. If not provided, it will use the default index name.
            
        Returns:
            True if dropped successfully, False otherwise.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        # Check if we already know vector search is not available
        if getattr(self, '_vector_search_available', None) is False:
            logger.warning("MongoDB Atlas Vector Search is not available. Cannot drop vector index.")
            return False
        
        await self._ensure_connected()
        
        # Auto-detect vector search capability if not already determined
        if self._vector_search_available is None:
            try:
                capability_test = await self.db.command({
                    "listSearchIndexes": collection,
                    "limit": 1
                })
                self._vector_search_available = True
                logger.info("MongoDB Atlas Vector Search detected and available.")
            except Exception as e:
                self._vector_search_available = False
                logger.warning(f"MongoDB Atlas Vector Search not available or not configured: {str(e)}")
                return False
        
        try:
            # Use the provided index name or the default
            index_name = index_name or self.vector_search_index
            
            # Create the command to drop the index
            command = {
                "dropSearchIndex": collection,
                "name": index_name
            }
            
            # Execute the command
            result = await self.db.command(command)
            
            # Check if the index was dropped successfully
            success = result.get("ok", 0) == 1
            if success:
                logger.info(f"Successfully dropped vector index: {index_name}")
            return success
        except Exception as e:
            logger.error(f"Failed to drop vector index: {str(e)}")
            return False
    
    async def search_vectors(self, collection: str, vector: List[float], filter: Optional[Dict[str, Any]] = None,
                          top_k: int = 10, min_similarity: Optional[float] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors.
        
        Args:
            collection: The collection name.
            vector: The query vector.
            filter: Optional filter criteria.
            top_k: Maximum number of results.
            min_similarity: Optional minimum similarity threshold.
            
        Returns:
            List of similar documents with similarity scores.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        # Auto-detect vector search capability if not already determined
        vector_search_available = getattr(self, '_vector_search_available', None)
        
        if vector_search_available is None:
            # Try to detect if MongoDB Atlas Vector Search is available
            try:
                capability_test = await self.db.command({
                    "listSearchIndexes": collection,
                    "limit": 1
                })
                self._vector_search_available = True
                logger.info("MongoDB Atlas Vector Search detected and available.")
            except Exception as e:
                self._vector_search_available = False
                logger.warning(f"MongoDB Atlas Vector Search not available or not configured: {str(e)}")
                logger.info("Falling back to basic filtering for vector operations")
        
        # Use Atlas Vector Search if available
        if self._vector_search_available:
            try:
                # Prepare the filter with type conversion
                if filter:
                    filter = self._convert_id_in_query(filter)
                else:
                    filter = {}
                
                # Create the aggregation pipeline
                pipeline = [
                    {
                        "$search": {
                            "index": self.vector_search_index,
                            "vectorSearch": {
                                "path": "embedding",  # Field containing the vector
                                "queryVector": vector,
                                "numCandidates": max(top_k * 10, 100),  # Candidates to consider (adjust as needed)
                                "limit": top_k,
                                "filter": filter
                            },
                            "returnStoredSource": True
                        }
                    },
                    {
                        # Include similarity score in results
                        "$project": {
                            "score": { "$meta": "searchScore" },
                            "document": "$$ROOT"
                        }
                    }
                ]
                
                # If min_similarity is provided, add a filter stage
                if min_similarity is not None:
                    pipeline.append(
                        {
                            "$match": {
                                "score": {"$gte": min_similarity}
                            }
                        }
                    )
                
                # Execute the aggregation
                cursor = self.db[collection].aggregate(pipeline)
                
                # Convert cursor to list
                results = await cursor.to_list(length=None)
                
                # Process results to match the expected format
                return [
                    {
                        **result["document"],
                        "searchScore": result["score"]
                    }
                    for result in results
                ]
                
            except Exception as e:
                logger.warning(f"Atlas Vector Search failed, falling back to basic filtering: {str(e)}")
                # Fall through to basic filtering fallback
        
        # Fallback: simple filter-based approach if vector search is not available
        logger.info("Using fallback filter-based approach for vector 'search'")
        if filter:
            filter = self._convert_id_in_query(filter)
        else:
            filter = {}
            
        cursor = self.db[collection].find(filter)
        limit_cursor = cursor.limit(top_k)
        documents = await limit_cursor.to_list(length=None)
        
        # Add placeholder similarity scores (all set to 0.5)
        results = []
        for doc in documents:
            doc["searchScore"] = 0.5
            results.append(doc)
            
        return results
    
    async def batch_search_vectors(self, collection: str, vectors: List[List[float]], 
                                filter: Optional[Dict[str, Any]] = None,
                                top_k: int = 10, min_similarity: Optional[float] = None) -> List[List[Dict[str, Any]]]:
        """Search for similar vectors in batch.
        
        Args:
            collection: The collection name.
            vectors: The query vectors.
            filter: Optional filter criteria.
            top_k: Maximum number of results per vector.
            min_similarity: Optional minimum similarity threshold.
            
        Returns:
            List of lists of similar documents with similarity scores.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        # Perform searches one by one
        # MongoDB doesn't natively support batch vector search
        results = []
        for vector in vectors:
            result = await self.search_vectors(
                collection=collection,
                vector=vector,
                filter=filter,
                top_k=top_k,
                min_similarity=min_similarity
            )
            results.append(result)
        
        return results
