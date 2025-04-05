"""Utility functions for the knowledge forest.

This module provides utility functions that are used across different components
of the knowledge forest system, such as vector operations, text processing, etc.
"""
import logging
import math
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VectorUtils:
    """Vector-related utility functions."""
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score (0-1)
        """
        # Handle empty vectors
        if not vec1 or not vec2:
            return 0.0
            
        # Handle different lengths
        if len(vec1) != len(vec2):
            return 0.0
            
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # Handle zero magnitudes
        if magnitude1 < 1e-10 or magnitude2 < 1e-10:
            return 0.0
            
        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Ensure result is in valid range
        return max(0.0, min(1.0, similarity))
    
    @staticmethod
    def l2_distance(vec1: List[float], vec2: List[float]) -> float:
        """Calculate Euclidean (L2) distance between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Distance value
        """
        # Handle empty vectors
        if not vec1 or not vec2:
            return float('inf')
            
        # Handle different lengths
        if len(vec1) != len(vec2):
            return float('inf')
            
        # Calculate L2 distance
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))
    
    @staticmethod
    def normalize_vector(vec: List[float]) -> List[float]:
        """Normalize a vector to unit length.
        
        Args:
            vec: Input vector
            
        Returns:
            Normalized vector
        """
        # Handle empty vector
        if not vec:
            return []
            
        # Calculate magnitude
        magnitude = math.sqrt(sum(v * v for v in vec))
        
        # Handle zero magnitude
        if magnitude < 1e-10:
            return [0.0] * len(vec)
            
        # Normalize
        return [v / magnitude for v in vec]


class DateTimeUtils:
    """Date and time utility functions."""
    
    @staticmethod
    def days_since(date: datetime) -> float:
        """Calculate days since a given date.
        
        Args:
            date: The reference date
            
        Returns:
            Number of days since the date
        """
        return (datetime.utcnow() - date).total_seconds() / (24 * 3600)
    
    @staticmethod
    def format_timedelta(delta: timedelta) -> str:
        """Format a timedelta in a human-readable way.
        
        Args:
            delta: The time delta
            
        Returns:
            Human-readable string
        """
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            
        if not parts:
            return "just now"
            
        return ", ".join(parts)


class DictUtils:
    """Dictionary utility functions."""
    
    @staticmethod
    def merge_dicts(dict1: Dict[Any, Any], dict2: Dict[Any, Any], 
                   overwrite: bool = True) -> Dict[Any, Any]:
        """Merge two dictionaries.
        
        Args:
            dict1: First dictionary
            dict2: Second dictionary
            overwrite: Whether to overwrite values in dict1 with values from dict2
            
        Returns:
            Merged dictionary
        """
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = DictUtils.merge_dicts(result[key], value, overwrite)
            elif key not in result or overwrite:
                # Add or overwrite value
                result[key] = value
                
        return result
    
    @staticmethod
    def flatten_dict(d: Dict[Any, Any], parent_key: str = '', 
                    separator: str = '.') -> Dict[str, Any]:
        """Flatten a nested dictionary.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested dictionaries
            separator: Separator for keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{separator}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(DictUtils.flatten_dict(v, new_key, separator).items())
            else:
                items.append((new_key, v))
                
        return dict(items)


class TextUtils:
    """Text processing utility functions."""
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = '...') -> str:
        """Truncate text to a maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add to truncated text
            
        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text
            
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 5, 
                        min_length: int = 3) -> List[str]:
        """Extract potential keywords from text.
        
        This is a simple implementation that just extracts words based on
        frequency and length. For production use, consider using a proper
        keyword extraction library.
        
        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            min_length: Minimum keyword length
            
        Returns:
            List of keywords
        """
        # Simple implementation - just count word frequency
        words = text.lower().split()
        
        # Filter short words and common stop words
        stop_words = {'the', 'and', 'to', 'of', 'a', 'in', 'that', 'is', 'for', 'it', 'as', 'with', 'on', 'by'}
        filtered_words = [word for word in words if len(word) >= min_length and word not in stop_words]
        
        # Count frequencies
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1
            
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Return top keywords
        return [word for word, count in sorted_words[:max_keywords]]
