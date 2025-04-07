"""Firecrawl AI model implementation.

This module implements the Firecrawl model interfaces, providing web extraction, 
search, and content analysis capabilities.
"""
import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Union, Any, Callable

from firecrawl import FirecrawlApp

from src.ai.base import WebExtractionModel, SearchModel
from src.ai.factory import register_ai_model
from src.common.config import get_settings
from src.common.exceptions import AIServiceUnavailableError, AIRequestError

settings = get_settings()
logger = logging.getLogger(__name__)

class FirecrawlModel(WebExtractionModel, SearchModel):
    """Firecrawl model implementation for web extraction and search."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Firecrawl model.
        
        Args:
            api_key: Optional API key. If not provided, it will be loaded from settings.
        """
        self.api_key = api_key or settings.ai.firecrawl_api_key
        self._model_name = "firecrawl"
        
        if not self.api_key:
            raise ValueError("Firecrawl API key not provided and not found in settings")
            
        # Initialize the client
        self.client = FirecrawlApp(api_key=self.api_key)
        
        # Keep track of extraction service
        self._extraction_service = None
        self._extraction_helpers = {
            "gemini": None,
            "claude": None
        }
    
    @property
    def model_name(self) -> str:
        """Get the current model name.
        
        Returns:
            The name of the model.
        """
        return self._model_name
    
    def set_model(self, model_name: str) -> None:
        """Set the model to use.
        
        Args:
            model_name: The name of the model to use.
        """
        # Firecrawl doesn't have different models, so this is a no-op
        pass
    
    def is_available(self) -> bool:
        """Check if the Firecrawl service is available.
        
        Returns:
            True if the service is available.
        """
        try:
            # Simple ping to the API
            response = self.client.health_check()
            return response and isinstance(response, dict) and response.get("status") == "ok"
        except Exception:
            return False
    
    def set_extraction_helpers(self, gemini=None, claude=None):
        """Set AI helpers for enhanced extraction capabilities.
        
        Args:
            gemini: Optional Gemini model for extraction enhancement.
            claude: Optional Claude model for extraction enhancement.
        """
        self._extraction_helpers["gemini"] = gemini
        self._extraction_helpers["claude"] = claude
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for text.
        
        This is implemented to fulfill the AIModel interface, but is not
        a native capability of Firecrawl. It uses a configured helper model.
        
        Args:
            text: The text to embed.
            
        Returns:
            Vector embedding as a list of floats.
            
        Raises:
            NotImplementedError: If no helper model with embedding capability is available.
        """
        # Try to use helper models if available
        if self._extraction_helpers["gemini"] and hasattr(self._extraction_helpers["gemini"], "generate_embedding"):
            return await self._extraction_helpers["gemini"].generate_embedding(text)
        
        raise NotImplementedError("Firecrawl does not natively support embeddings. Please set a helper model.")
    
    async def extract_content(self, url: str, objective: str, **kwargs) -> Dict[str, Any]:
        """Extract content from a URL based on an objective.
        
        Args:
            url: The URL to extract from.
            objective: The extraction objective.
            **kwargs: Additional parameters.
                - formats: List of formats to extract (e.g., ["markdown", "html"]).
                - use_advanced_model: Whether to use advanced AI models for extraction.
                - timeout: Timeout in seconds.
            
        Returns:
            The extracted content.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        try:
            # Use smart extraction if objective is provided
            if objective:
                use_advanced_model = kwargs.get("use_advanced_model", False)
                
                # Get formats (if explicitly specified)
                formats = kwargs.get("formats", ["markdown"])
                
                # Basic scrape if no helpers are available
                if not any(self._extraction_helpers.values()):
                    logger.info("No AI helpers available, falling back to basic scraping")
                    response = await asyncio.to_thread(
                        self.client.scrape_url,
                        url=url,
                        params={"formats": formats}
                    )
                    return response
                
                # Use Gemini helper if available
                if self._extraction_helpers["gemini"]:
                    # Prepare prompt for extraction
                    prompt = f"""
                    Extract information from the webpage at {url} according to this objective:
                    {objective}
                    
                    Provide the extracted information in a structured JSON format with relevant fields.
                    """
                    
                    # First scrape the content
                    response = await asyncio.to_thread(
                        self.client.scrape_url,
                        url=url,
                        params={"formats": formats}
                    )
                    
                    # Extract markdown content
                    markdown_content = response.get("markdown", "")
                    
                    # If content is too large, truncate
                    if len(markdown_content) > 12000:  # Approximate token limit
                        markdown_content = markdown_content[:12000] + "...\n[Content truncated due to length]"
                    
                    # Enhance prompt with content
                    enhanced_prompt = f"{prompt}\n\nWebpage content:\n{markdown_content}"
                    
                    # Use Gemini to extract structured information
                    if use_advanced_model and hasattr(self._extraction_helpers["gemini"], "set_model"):
                        # Store original model
                        original_model = self._extraction_helpers["gemini"].model_name
                        # Set to advanced model if available
                        try:
                            self._extraction_helpers["gemini"].set_model("gemini-pro")
                        except:
                            pass
                        
                    try:
                        result = await self._extraction_helpers["gemini"].generate_text(enhanced_prompt, max_tokens=4096)
                    finally:
                        # Restore original model if changed
                        if use_advanced_model and hasattr(self._extraction_helpers["gemini"], "set_model"):
                            try:
                                self._extraction_helpers["gemini"].set_model(original_model)
                            except:
                                pass
                    
                    # Try to extract JSON from the response
                    try:
                        if "```json" in result:
                            json_str = result.split("```json")[1].split("```")[0].strip()
                            extracted_data = json.loads(json_str)
                        elif "```" in result:
                            json_str = result.split("```")[1].strip()
                            extracted_data = json.loads(json_str)
                        else:
                            extracted_data = json.loads(result)
                            
                        return {
                            "extracted_data": extracted_data,
                            "raw_content": response
                        }
                    except:
                        # If JSON parsing fails, return structured result
                        return {
                            "extracted_text": result,
                            "raw_content": response
                        }
                
                # Fall back to basic scraping if everything else fails
                return await asyncio.to_thread(
                    self.client.scrape_url,
                    url=url,
                    params={"formats": formats}
                )
                
            else:
                # Simple scraping without objective
                formats = kwargs.get("formats", ["markdown"])
                response = await asyncio.to_thread(
                    self.client.scrape_url,
                    url=url,
                    params={"formats": formats}
                )
                return response
                
        except Exception as e:
            if "unavailable" in str(e).lower() or "503" in str(e):
                raise AIServiceUnavailableError(f"Firecrawl service unavailable: {str(e)}")
            else:
                raise AIRequestError(f"Firecrawl extraction error: {str(e)}")
    
    async def search_web(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search the web using Firecrawl.
        
        Args:
            query: The search query.
            **kwargs: Additional search parameters.
                - limit: Maximum number of results (default: 10).
                - scrape: Whether to scrape the search results (default: False).
            
        Returns:
            Search results.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        try:
            # Get parameters
            limit = kwargs.get("limit", 10)
            scrape = kwargs.get("scrape", False)
            
            # Use search endpoint
            params = {
                "limit": limit,
                "query": query
            }
            
            if scrape:
                params["scrape"] = True
                formats = kwargs.get("formats", ["markdown"])
                params["formats"] = formats
            
            # Execute search
            response = await asyncio.to_thread(
                self.client.search,
                params=params
            )
            
            return response
                
        except Exception as e:
            if "unavailable" in str(e).lower() or "503" in str(e):
                raise AIServiceUnavailableError(f"Firecrawl service unavailable: {str(e)}")
            else:
                raise AIRequestError(f"Firecrawl search error: {str(e)}")
    
    async def analyze_image(self, image_data: bytes, prompt: str) -> str:
        """Analyze image content.
        
        This is not a native capability of Firecrawl, but it can delegate to a helper model.
        
        Args:
            image_data: The image data as bytes.
            prompt: The analysis prompt.
            
        Returns:
            The analysis results.
            
        Raises:
            NotImplementedError: If no helper model with image analysis capability is available.
        """
        # Try to use helper models if available
        if self._extraction_helpers["gemini"] and hasattr(self._extraction_helpers["gemini"], "analyze_image"):
            return await self._extraction_helpers["gemini"].analyze_image(image_data, prompt)
        
        raise NotImplementedError("Firecrawl does not natively support image analysis. Please set a helper model.")
    
    async def map_website(self, url: str, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Map a website to discover its structure and URLs.
        
        Args:
            url: The URL to map.
            search: Optional search term to filter results.
            **kwargs: Additional parameters.
                - include_subdomains: Whether to include subdomains.
                - limit: Maximum number of URLs.
            
        Returns:
            The site map.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        try:
            # Build parameters
            params = {}
            if search:
                params["search"] = search
            
            include_subdomains = kwargs.get("include_subdomains", False)
            if include_subdomains:
                params["includeSubdomains"] = True
                
            limit = kwargs.get("limit", 100)
            if limit:
                params["limit"] = limit
            
            # Execute map operation
            response = await asyncio.to_thread(
                self.client.map_url,
                url=url,
                params=params
            )
            
            return response
                
        except Exception as e:
            if "unavailable" in str(e).lower() or "503" in str(e):
                raise AIServiceUnavailableError(f"Firecrawl service unavailable: {str(e)}")
            else:
                raise AIRequestError(f"Firecrawl map error: {str(e)}")
    
    async def crawl_website(self, url: str, **kwargs) -> Dict[str, Any]:
        """Start a website crawl with more advanced options.
        
        Args:
            url: The URL to crawl.
            **kwargs: Additional parameters.
                - max_depth: Maximum link depth.
                - limit: Maximum number of pages.
                - include_paths: Only crawl these paths.
                - exclude_paths: Exclude these paths.
            
        Returns:
            Crawl job information.
            
        Raises:
            AIServiceUnavailableError: If the service is unavailable.
            AIRequestError: If there's an error processing the request.
        """
        try:
            # Build parameters
            params = {
                "url": url
            }
            
            # Add optional parameters
            for param in ["maxDepth", "limit", "includePaths", "excludePaths"]:
                snake_case = param[0].lower() + param[1:]
                if snake_case in kwargs:
                    params[param] = kwargs[snake_case]
            
            # Execute crawl
            response = await asyncio.to_thread(
                self.client.crawl,
                params=params
            )
            
            return response
                
        except Exception as e:
            if "unavailable" in str(e).lower() or "503" in str(e):
                raise AIServiceUnavailableError(f"Firecrawl service unavailable: {str(e)}")
            else:
                raise AIRequestError(f"Firecrawl crawl error: {str(e)}")

# Register the model with the factory
register_ai_model("firecrawl", FirecrawlModel)
