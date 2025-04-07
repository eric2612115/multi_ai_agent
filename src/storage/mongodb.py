"""MongoDB storage implementation.

This module implements the DocumentStorage and VectorStorage interfaces using MongoDB
and MongoDB Atlas Vector Search.
"""
import os
import json
import logging
import uuid
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from bson import ObjectId, json_util
from bson.errors import InvalidId

from src.storage.base import DocumentStorage, VectorStorage
from src.common.config import get_settings
from src.common.exceptions import StorageConnectionError, StorageQueryError

settings = get_settings()
logger = logging.getLogger(__name__)

class MongoDBProvider(DocumentStorage):
    """MongoDB implementation of the DocumentStorage interface."""
    
    def __init__(self, connection_uri: Optional[str] = None, database_name: Optional[str] = None):
        """Initialize the MongoDB provider.
        
        Args:
            connection_uri: Optional connection URI. If not provided, it will be loaded from settings.
            database_name: Optional database name. If not provided, it will be loaded from settings.
        """
        self.connection_uri = connection_uri or settings.db.mongodb_uri
        self.database_name = database_name or settings.db.mongodb_db
        self.client = None
        self.db = None
        # Store configuration but don't rely on it for feature detection
        self.vector_search_index = settings.db.vector_search_index
        # The actual vector search availability will be auto-detected on first use
        self._vector_search_available = None
    
    async def connect(self) -> bool:
        """Connect to MongoDB.
        
        Returns:
            True if connected successfully.
            
        Raises:
            StorageConnectionError: If connection failed.
        """
        try:
            self.client = AsyncIOMotorClient(self.connection_uri, serverSelectionTimeoutMS=5000)
            # Test the connection
            await self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.debug(f"Connected to MongoDB database: {self.database_name}")
            return True
        except ServerSelectionTimeoutError as e:
            raise StorageConnectionError(f"Failed to connect to MongoDB: {str(e)}")
        except Exception as e:
            raise StorageConnectionError(f"Unexpected error connecting to MongoDB: {str(e)}")
    
    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
    
    async def is_connected(self) -> bool:
        """Check if connected to MongoDB.
        
        Returns:
            True if connected.
        """
        if self.client is None or self.db is None:
            return False
        
        try:
            # Test the connection
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False
    
    async def _ensure_connected(self) -> None:
        """Ensure that we are connected to MongoDB.
        
        Raises:
            StorageConnectionError: If connection failed.
        """
        is_connected = await self.is_connected()
        if not is_connected:
            if self.client is None:
                await self.connect()
            else:
                raise StorageConnectionError("Lost connection to MongoDB")
    
    async def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            
        Returns:
            The document, or None if not found.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert string ID to ObjectId
            obj_id = self._parse_id(document_id)
            
            # Query the document
            document = await self.db[collection].find_one({"_id": obj_id})
            
            return document
        except InvalidId:
            # If the ID is not a valid ObjectId, try to find by string ID
            try:
                document = await self.db[collection].find_one({"_id": document_id})
                return document
            except Exception as e:
                raise StorageQueryError(f"Failed to get document by string ID: {str(e)}")
        except Exception as e:
            raise StorageQueryError(f"Failed to get document: {str(e)}")
    
    async def save_document(self, collection: str, document: Dict[str, Any]) -> str:
        """Save a document.
        
        Args:
            collection: The collection name.
            document: The document to save.
            
        Returns:
            The document ID.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Generate a UUID string if no _id is provided
            if "_id" not in document:
                document["_id"] = str(uuid.uuid4())
            else:
                # Ensure _id is a string for consistency
                document["_id"] = str(document["_id"])
                
            # Save the document
            await self.db[collection].replace_one(
                {"_id": document["_id"]},
                document,
                upsert=True
            )
            
            return document["_id"]
        
        except Exception as e:
            raise StorageQueryError(f"Failed to save document: {str(e)}")
    async def update_document(self, collection: str, document_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a document.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            update_data: The fields to update.
            
        Returns:
            True if updated successfully, False otherwise.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert string ID to ObjectId
            obj_id = self._parse_id(document_id)
            
            # Check if update_data already contains operators like $set, $push, $addToSet
            if any(key.startswith('$') for key in update_data.keys()):
                # Use update data as is since it already contains operators
                result = await self.db[collection].update_one(
                    {"_id": obj_id},
                    update_data
                )
            else:
                # Use $set to update only specified fields
                result = await self.db[collection].update_one(
                    {"_id": obj_id},
                    {"$set": update_data}
                )
            
            # Return True if any documents were modified
            return result.modified_count > 0
        except InvalidId:
            # If the ID is not a valid ObjectId, try to update by string ID
            try:
                # Check if update_data already contains operators like $set, $push, $addToSet
                if any(key.startswith('$') for key in update_data.keys()):
                    # Use update data as is since it already contains operators
                    result = await self.db[collection].update_one(
                        {"_id": document_id},
                        update_data
                    )
                else:
                    # Use $set to update only specified fields
                    result = await self.db[collection].update_one(
                        {"_id": document_id},
                        {"$set": update_data}
                    )
                return result.modified_count > 0
            except Exception as e:
                raise StorageQueryError(f"Failed to update document by string ID: {str(e)}")
        except Exception as e:
            raise StorageQueryError(f"Failed to update document: {str(e)}")
    
    async def delete_document(self, collection: str, document_id: str) -> bool:
        """Delete a document.
        
        Args:
            collection: The collection name.
            document_id: The document ID.
            
        Returns:
            True if deleted successfully, False otherwise.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert string ID to ObjectId
            obj_id = self._parse_id(document_id)
            
            # Delete the document
            result = await self.db[collection].delete_one({"_id": obj_id})
            
            # Return True if any documents were deleted
            return result.deleted_count > 0
        except InvalidId:
            # If the ID is not a valid ObjectId, try to delete by string ID
            try:
                result = await self.db[collection].delete_one({"_id": document_id})
                return result.deleted_count > 0
            except Exception as e:
                raise StorageQueryError(f"Failed to delete document by string ID: {str(e)}")
        except Exception as e:
            raise StorageQueryError(f"Failed to delete document: {str(e)}")
    
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
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert any string IDs to ObjectIds
            query = self._convert_id_in_query(query)
            
            # Create cursor
            cursor = self.db[collection].find(query)
            
            # Apply sort if provided
            if sort:
                cursor = cursor.sort(list(sort.items()))
            
            # Apply skip if provided
            if skip is not None:
                cursor = cursor.skip(skip)
            
            # Apply limit if provided
            if limit is not None:
                cursor = cursor.limit(limit)
            
            # Convert cursor to list
            documents = await cursor.to_list(length=None)
            
            return documents
        except Exception as e:
            raise StorageQueryError(f"Failed to find documents: {str(e)}")
    
    async def count_documents(self, collection: str, query: Dict[str, Any]) -> int:
        """Count documents matching a query.
        
        Args:
            collection: The collection name.
            query: The query criteria.
            
        Returns:
            The document count.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert any string IDs to ObjectIds
            query = self._convert_id_in_query(query)
            
            # Count documents
            count = await self.db[collection].count_documents(query)
            
            return count
        except Exception as e:
            raise StorageQueryError(f"Failed to count documents: {str(e)}")
    
    async def create_index(self, collection: str, keys: Dict[str, int], unique: bool = False, name: Optional[str] = None) -> str:
        """Create an index.
        
        Args:
            collection: The collection name.
            keys: The keys to index, with direction values (1 or -1).
            unique: Whether the index should be unique.
            name: Optional index name.
            
        Returns:
            The index name.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Convert sort directions to MongoDB constants
            indexed_keys = []
            for key, direction in keys.items():
                if direction == 1:
                    indexed_keys.append((key, ASCENDING))
                elif direction == -1:
                    indexed_keys.append((key, DESCENDING))
                else:
                    raise ValueError(f"Invalid index direction: {direction}. Use 1 for ascending or -1 for descending.")
            
            # Create the index
            index_name = await self.db[collection].create_index(
                indexed_keys,
                unique=unique,
                name=name
            )
            
            return index_name
        except Exception as e:
            raise StorageQueryError(f"Failed to create index: {str(e)}")
    
    async def drop_index(self, collection: str, index_name: str) -> bool:
        """Drop an index.
        
        Args:
            collection: The collection name.
            index_name: The index name.
            
        Returns:
            True if dropped successfully, False otherwise.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Drop the index
            await self.db[collection].drop_index(index_name)
            
            return True
        except Exception as e:
            raise StorageQueryError(f"Failed to drop index: {str(e)}")
    
    def _parse_id(self, id_str: str) -> Union[str, ObjectId]:
        """Parse an ID string.
        
        Args:
            id_str: The ID string.
            
        Returns:
            Either the original string (preferred) or ObjectId if necessary.
        """
        # Always return string ID rather than ObjectId for better compatibility
        return id_str
    
    def _convert_id_in_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Process query dict to ensure ID compatibility.
        
        Args:
            query: The query dictionary.
            
        Returns:
            Processed query with compatible ID formats.
        """
        # Return the query as is to use string IDs throughout the system
        # This improves compatibility between frontend and backend
        return query
        
    async def get_current_time(self) -> str:
        """Get the current server time from MongoDB.
        
        Returns:
            The current server time as an ISO-formatted string.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Get the current server time from MongoDB
            server_status = await self.client.admin.command("serverStatus")
            if "localTime" in server_status:
                return server_status["localTime"].isoformat()
            
            # Fallback to Python datetime if MongoDB doesn't provide it
            from datetime import datetime
            return datetime.utcnow().isoformat()
        except Exception as e:
            from datetime import datetime
            return datetime.utcnow().isoformat()
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Dictionary with database statistics.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Get database statistics
            stats = await self.db.command("dbStats")
            return stats
        except Exception as e:
            raise StorageQueryError(f"Failed to get database statistics: {str(e)}")
    
    async def list_collections(self) -> List[str]:
        """List all collections in the database.
        
        Returns:
            List of collection names.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # List collections
            collections = await self.db.list_collection_names()
            return collections
        except Exception as e:
            raise StorageQueryError(f"Failed to list collections: {str(e)}")
    
    async def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get statistics for a specific collection.
        
        Args:
            collection: The collection name.
            
        Returns:
            Dictionary with collection statistics.
            
        Raises:
            StorageConnectionError: If connection failed.
            StorageQueryError: If query failed.
        """
        await self._ensure_connected()
        
        try:
            # Get collection statistics
            stats = await self.db.command("collStats", collection)
            return stats
        except Exception as e:
            raise StorageQueryError(f"Failed to get collection statistics: {str(e)}")
    
    async def search_vectors(self, collection: str, vector: List[float], filter: Optional[Dict[str, Any]] = None,
                          top_k: int = 10, min_similarity: Optional[float] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors (compatibility method).
        
        This method is provided for compatibility with the VectorStorage interface.
        It will attempt to use MongoDB Atlas Vector Search if available, and fall back
        to a basic filter-based approach if Atlas Vector Search is not available.
        
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
        
        # Prepare the filter with type conversion
        if filter:
            filter = self._convert_id_in_query(filter)
        else:
            filter = {}
        
        # Auto-detect vector search capability if not already determined
        vector_search_available = getattr(self, '_vector_search_available', None)
        
        if vector_search_available is None:
            # Try to detect if MongoDB Atlas Vector Search is available
            try:
                # Probe for Atlas search capability by checking for $vectorSearch
                capability_test = await self.db.command({
                    "listSearchIndexes": collection,
                    "limit": 1
                })
                self._vector_search_available = True
                logger.info("MongoDB Atlas Vector Search detected and available.")
            except Exception as e:
                # If this fails, MongoDB Atlas Vector Search is likely not available
                self._vector_search_available = False
                logger.warning(f"MongoDB Atlas Vector Search not available or not configured: {str(e)}")
                
        # Use Atlas Vector Search if available
        if self._vector_search_available:
            try:
                # Use proper MongoDB Atlas Vector Search
                vector_search_index = getattr(self, 'vector_search_index', 'nodes_vector_index')
                
                # Create the aggregation pipeline
                pipeline = [
                    {
                        "$search": {
                            "index": vector_search_index,
                            "vectorSearch": {
                                "path": "embedding",  # Field containing the vector
                                "queryVector": vector,
                                "numCandidates": max(top_k * 10, 100),  # Candidates to consider
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
        
        # Fallback: simple filter-based approach
        logger.info("Using fallback filter-based approach for vector 'search'")
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
        """Search for similar vectors in batch (compatibility method).
        
        This method is provided for compatibility with the VectorStorage interface.
        It uses the search_vectors method which automatically detects if vector search
        is available, and falls back to simple filtering if not.
        
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
        await self._ensure_connected()
        
        # Perform searches one by one
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
