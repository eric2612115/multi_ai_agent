"""Storage interfaces.

This module defines the abstract storage interfaces that different storage implementations
should implement. These include document storage, vector storage, and caching.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Tuple

class StorageProvider(ABC):
    """Base interface for storage providers."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the storage.
        
        Returns:
            True if connected successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection to the storage."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the storage.
        
        Returns:
            True if connected, False otherwise.
        """
        pass


class DocumentStorage(StorageProvider):
    """Interface for document storage (e.g., MongoDB, PostgreSQL)."""
    
    @abstractmethod
    async def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            
        Returns:
            The document, or None if not found.
        """
        pass
    
    @abstractmethod
    async def save_document(self, collection: str, document: Dict[str, Any]) -> str:
        """Save a document.
        
        Args:
            collection: The collection name.
            document: The document to save.
            
        Returns:
            The document ID.
        """
        pass
    
    @abstractmethod
    async def update_document(self, collection: str, document_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a document.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            update_data: The fields to update.
            
        Returns:
            True if updated successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def delete_document(self, collection: str, document_id: str) -> bool:
        """Delete a document.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            
        Returns:
            True if deleted successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def find_documents(self, collection: str, query: Dict[str, Any], 
                           sort: Optional[Dict[str, int]] = None, limit: Optional[int] = None,
                           skip: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find documents matching a query.
        
        Args:
            collection: The collection name.
            query: The query criteria.
            sort: Optional sort specification.
            limit: Optional result limit.
            skip: Optional number of results to skip.
            
        Returns:
            List of matching documents.
        """
        pass
    
    @abstractmethod
    async def count_documents(self, collection: str, query: Dict[str, Any]) -> int:
        """Count documents matching a query.
        
        Args:
            collection: The collection name.
            query: The query criteria.
            
        Returns:
            The document count.
        """
        pass


class VectorStorage(StorageProvider):
    """Interface for vector storage providers (e.g., MongoDB Atlas Vector Search, Pinecone)."""
    
    @abstractmethod
    async def create_vector_index(self, collection: str, field: str, dimensions: int, 
                                similarity_metric: str = "cosine") -> bool:
        """Create a vector index.
        
        Args:
            collection: The collection name.
            field: The field name containing vectors.
            dimensions: The dimensionality of vectors.
            similarity_metric: The similarity metric to use.
            
        Returns:
            True if created successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def drop_vector_index(self, collection: str, index_name: Optional[str] = None) -> bool:
        """Drop a vector index.
        
        Args:
            collection: The collection name.
            index_name: Optional index name.
            
        Returns:
            True if dropped successfully, False otherwise.
        """
        pass
    
    @abstractmethod
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
        """
        pass
    
    @abstractmethod
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
        """
        pass


class CacheStorage(StorageProvider):
    """Interface for cache storage providers (e.g., Redis, Memcached)."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key.
        
        Args:
            key: The key.
            
        Returns:
            The value, or None if not found.
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, expiry: Optional[int] = None) -> bool:
        """Set a value.
        
        Args:
            key: The key.
            value: The value to set.
            expiry: Optional expiry time in seconds.
            
        Returns:
            True if set successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value.
        
        Args:
            key: The key.
            
        Returns:
            True if deleted successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key.
            
        Returns:
            True if the key exists, False otherwise.
        """
        pass
    
    @abstractmethod
    async def expire(self, key: str, seconds: int) -> bool:
        """Set an expiry time on a key.
        
        Args:
            key: The key.
            seconds: The expiry time in seconds.
            
        Returns:
            True if expiry set successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a value.
        
        Args:
            key: The key.
            amount: The amount to increment by (default: 1).
            
        Returns:
            The new value, or None if the operation failed.
        """
        pass
    
    @abstractmethod
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a value.
        
        Args:
            key: The key.
            amount: The amount to decrement by (default: 1).
            
        Returns:
            The new value, or None if the operation failed.
        """
        pass


class MessageQueue(StorageProvider):
    """Interface for message queue providers (e.g., Redis, RabbitMQ)."""
    
    @abstractmethod
    async def publish(self, channel: str, message: Any) -> bool:
        """Publish a message to a channel.
        
        Args:
            channel: The channel name.
            message: The message to publish.
            
        Returns:
            True if published successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel.
        
        Args:
            channel: The channel name.
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.
        
        Args:
            channel: The channel name.
        """
        pass
    
    @abstractmethod
    async def get_message(self, timeout: Optional[float] = None) -> Optional[Tuple[str, Any]]:
        """Get a message from subscribed channels.
        
        Args:
            timeout: Optional timeout in seconds.
            
        Returns:
            A tuple of (channel, message), or None if no message is available.
        """
        pass
    
    @abstractmethod
    async def push(self, queue: str, item: Any) -> bool:
        """Push an item to a queue.
        
        Args:
            queue: The queue name.
            item: The item to push.
            
        Returns:
            True if pushed successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    async def pop(self, queue: str, timeout: Optional[float] = None) -> Optional[Any]:
        """Pop an item from a queue.
        
        Args:
            queue: The queue name.
            timeout: Optional timeout in seconds.
            
        Returns:
            The popped item, or None if no item is available.
        """
        pass
