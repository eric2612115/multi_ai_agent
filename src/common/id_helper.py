"""ID helper module.

This module provides helpers for ID conversion between MongoDB ObjectId and UUID.
It helps in standardizing the use of UUIDs throughout the application.
"""
import uuid
from typing import Dict, Any, Union, Optional
from bson import ObjectId


def generate_uuid() -> str:
    """Generate a new UUID string.
    
    Returns:
        A new UUID string.
    """
    return str(uuid.uuid4())


def ensure_uuid_str(id_value: Any) -> Optional[str]:
    """Convert any ID value to a UUID string if possible.
    
    Args:
        id_value: ID value to convert (string, UUID, ObjectId, etc.)
        
    Returns:
        UUID string, or None if conversion is not possible.
    """
    if id_value is None:
        return None
        
    if isinstance(id_value, uuid.UUID):
        return str(id_value)
        
    if isinstance(id_value, str):
        # Try to parse as UUID
        try:
            # Validate it's a valid UUID format
            parsed = uuid.UUID(id_value)
            return str(parsed)
        except ValueError:
            # Check if it's an ObjectId string
            if ObjectId.is_valid(id_value):
                # Convert ObjectId to a UUID deterministically
                # This allows backward compatibility with existing ObjectId values
                obj_id_hex = id_value if isinstance(id_value, str) else str(id_value)
                # Use MD5 hash of the ObjectId to create a UUID (Version 3)
                return str(uuid.uuid3(uuid.NAMESPACE_OID, obj_id_hex))
            
            # Not a valid UUID or ObjectId, force to UUID format
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_value))
    
    if isinstance(id_value, ObjectId):
        # Convert ObjectId to UUID deterministically
        return str(uuid.uuid3(uuid.NAMESPACE_OID, str(id_value)))
        
    # For other types, convert to string first then to UUID
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(id_value)))


def convert_ids_to_uuid(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert all ID fields in a document to UUID strings.
    
    Args:
        data: Document data to convert.
        
    Returns:
        Document with converted IDs.
    """
    # Make a copy to avoid modifying the original
    result = data.copy()
    
    # Convert _id field
    if "_id" in result:
        result["id"] = ensure_uuid_str(result.pop("_id"))
    
    # Convert common ID fields
    for field in ["user_id", "conversation_id", "message_id", "parent_node_id", "topic_cluster_id"]:
        if field in result:
            result[field] = ensure_uuid_str(result[field])
    
    # Convert list ID fields
    for field in ["conversation_ids", "message_ids"]:
        if field in result and isinstance(result[field], list):
            result[field] = [ensure_uuid_str(item) for item in result[field]]
    
    # Handle nested objects
    for key, value in list(result.items()):
        if isinstance(value, dict):
            result[key] = convert_ids_to_uuid(value)
        elif isinstance(value, list):
            result[key] = [
                convert_ids_to_uuid(item) if isinstance(item, dict) else item 
                for item in value
            ]
    
    return result
