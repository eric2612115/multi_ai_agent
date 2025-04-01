# Extending the Multi-AI Agent

This guide explains how to extend the Multi-AI Agent with new functionality.

## Adding a New AI Service

To add support for a new AI service:

1. **Add the SDK to Dependencies**

   Update `pyproject.toml` to include the new SDK:
   ```toml
   dependencies = [
       # existing dependencies
       "new-ai-sdk>=1.0.0",
   ]
   ```

2. **Create a Wrapper Client**

   Add a new class in `src/multi_ai_agent/clients.py`:
   ```python
   class NewAIClient:
       """Wrapper for New AI SDK."""
       
       def __init__(self, api_key: Optional[str] = None):
           """Initialize the New AI client."""
           self.api_key = api_key or os.environ.get("NEWAI_API_KEY")
           if not self.api_key:
               raise ValueError("NEWAI_API_KEY environment variable not set")
           
           self.client = newai.Client(api_key=self.api_key)
       
       def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
           """Generate text using the New AI service."""
           # Implement using the new SDK
           response = self.client.generate(prompt, max_tokens=max_tokens)
           return response.text
   ```

3. **Update the App Context**

   Modify the `AppContext` class and `app_lifespan` function in `main.py`:
   ```python
   @dataclass
   class AppContext:
       """Application context shared between tools."""
       gemini: GeminiClient
       claude: ClaudeClient
       firecrawl: FirecrawlClient
       newai: NewAIClient  # Add new client
       config: Dict[str, Any]

   @asynccontextmanager
   async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
       """Manage application lifecycle."""
       # Initialize existing clients
       # ...
       
       # Initialize new client
       newai = NewAIClient()
       
       try:
           yield AppContext(
               gemini=gemini,
               claude=claude,
               firecrawl=firecrawl,
               newai=newai,  # Add new client
               config=config
           )
       finally:
           # Cleanup on shutdown (if needed)
           pass
   ```

4. **Add MCP Tools**

   Add new tools in `main.py` to expose the service's functionality:
   ```python
   @mcp.tool()
   def newai_generate(prompt: str, max_tokens: Optional[int] = None, ctx: Context = None) -> str:
       """Generate text using NewAI service.
       
       Args:
           prompt: The prompt to generate text from.
           max_tokens: The maximum number of tokens to generate.
           ctx: The MCP context.
           
       Returns:
           The generated text.
       """
       app_ctx = ctx.request_context.lifespan_context
       max_tokens = max_tokens or app_ctx.config["max_tokens"]
       
       ctx.info(f"Generating text using NewAI service")
       return app_ctx.newai.generate_text(prompt, max_tokens)
   ```

5. **Add Tests**

   Create tests in `tests/test_newai.py`:
   ```python
   """Tests for the NewAI client."""
   import os
   import pytest
   from dotenv import load_dotenv

   from multi_ai_agent.clients import NewAIClient

   # Load environment variables
   load_dotenv()

   @pytest.fixture
   def newai_client():
       """Create a NewAI client for testing."""
       # Skip if no API key
       if not os.environ.get("NEWAI_API_KEY"):
           pytest.skip("NEWAI_API_KEY environment variable not set")
       
       return NewAIClient()

   def test_generate_text(newai_client):
       """Test text generation."""
       response = newai_client.generate_text(
           "Write a short poem about artificial intelligence.",
           max_tokens=200
       )
       
       assert isinstance(response, str)
       assert len(response) > 0
   ```

6. **Update Documentation**

   Update the service information resource in `main.py`:
   ```python
   @mcp.resource("config://services")
   def get_services() -> str:
       """Get information about the available AI services."""
       return """
       Available AI Services:
       
       # Existing services...
       
       4. NewAI
          - Default settings: ...
          - Capabilities: ...
       """
   ```

## Enhancing Web Extraction Capabilities

The agent's web extraction functionality can be extended in several ways:

### Adding a New Extraction Method

1. **Add Method to WebExtractionService**

   Open `src/multi_ai_agent/services/web_extraction.py` and add a new method:
   ```python
   def specialized_extraction(self, url: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
       """Specialized extraction method for specific types of content.
       
       Args:
           url: The URL to extract from
           parameters: Parameters for the extraction
           
       Returns:
           Extracted data
       """
       # Implementation
       self.log(f"Performing specialized extraction from: {url}")
       
       # Use existing clients as needed
       scrape_result = self.firecrawl.scrape_url(url)
       
       # Process with AI if appropriate
       if self.gemini:
           # AI-enhanced processing
           pass
           
       return processed_result
   ```

2. **Expose Through FirecrawlClient**

   Add a method to the `FirecrawlClient` class in `src/multi_ai_agent/clients.py`:
   ```python
   def specialized_extract(self, url: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
       """Perform specialized extraction.
       
       Args:
           url: URL to extract from
           parameters: Extraction parameters
           
       Returns:
           Extracted data
       """
       if not self._extraction_service:
           self.logger("Web extraction service not initialized.")
           return None
           
       return self._extraction_service.specialized_extraction(url, parameters)
   ```

3. **Add MCP Tool**

   Add a new tool in `main.py`:
   ```python
   @mcp.tool()
   def specialized_extraction(url: str, parameter1: str, parameter2: int, ctx: Context = None) -> Dict[str, Any]:
       """Perform specialized extraction for specific content types.
       
       Args:
           url: The URL to extract from
           parameter1: First parameter description
           parameter2: Second parameter description
           ctx: The MCP context
           
       Returns:
           Extracted data
       """
       app_ctx = ctx.request_context.lifespan_context
       
       parameters = {
           "param1": parameter1,
           "param2": parameter2
       }
       
       ctx.info(f"Performing specialized extraction from: {url}")
       return app_ctx.firecrawl.specialized_extract(url, parameters)
   ```

### Working with Additional File Types

To add support for new file types in the extraction process:

1. **Update MIME Type Detection**

   Modify the `detect_mime_type()` function in `web_extraction.py`:
   ```python
   def detect_mime_type(url: str, timeout: int = 8) -> Optional[str]:
       """Detect MIME type from URL."""
       try:
           resp = requests.head(url, timeout=timeout, allow_redirects=True)
           ctype = resp.headers.get('Content-Type', '').lower()
           
           # Add detection for new file types
           if 'pdf' in ctype:
               return 'pdf'
           elif ctype.startswith('image/'):
               return 'image'
           elif 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in ctype:
               return 'xlsx'  # New file type
           elif 'audio/' in ctype:
               return 'audio'  # New file type
           return None
       except RequestException:
           return None
   ```

2. **Add Processing Methods**

   Add methods to handle the new file types:
   ```python
   def _extract_xlsx_content(self, xlsx_url: str) -> Optional[str]:
       """Extract content from Excel files."""
       try:
           # Implementation
           xlsx_data = requests.get(xlsx_url, timeout=15).content
           # Process the Excel file
           return processed_content
       except Exception as e:
           self.log(f"Error processing Excel file: {str(e)}")
           return None
   ```

3. **Update Content Processing**

   Modify the content processing logic in `smart_extract_from_site()` to handle new types:
   ```python
   mime_type = detect_mime_type(sub_url)
   
   if mime_type == 'pdf':
       # Existing PDF handling
   elif mime_type == 'image':
       # Existing image handling
   elif mime_type == 'xlsx':
       # New Excel handling
       excel_content = self._extract_xlsx_content(sub_url)
       if excel_content:
           content_append += f"\n\n---\n[Excel from {sub_url}]:\n{excel_content}"
   elif mime_type == 'audio':
       # New audio handling
       audio_content = self._extract_audio_content(sub_url)
       if audio_content:
           content_append += f"\n\n---\n[Audio from {sub_url}]:\n{audio_content}"
   ```

## Using External Search APIs

To integrate external search APIs for enhanced information gathering:

1. **Add Search Provider**

   Create a new module `src/multi_ai_agent/services/search.py`:
   ```python
   """Search service for Multi-AI Agent."""
   import os
   from typing import List, Dict, Any, Optional

   class SearchService:
       """Service for performing web searches using various providers."""
       
       def __init__(self, serp_api_key: Optional[str] = None):
           """Initialize the search service.
           
           Args:
               serp_api_key: Optional SerpAPI key
           """
           self.serp_api_key = serp_api_key or os.environ.get("SERP_API_KEY")
           
       def search_web(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
           """Search the web using SerpAPI.
           
           Args:
               query: Search query
               num_results: Number of results to return
               
           Returns:
               List of search results
           """
           if not self.serp_api_key:
               raise ValueError("SERP_API_KEY not set")
               
           # Implementation using SerpAPI
           # ...
           
           return results
   ```

2. **Update the App Context**

   Add the search service to the app context in `main.py`:
   ```python
   from multi_ai_agent.services.search import SearchService
   
   @dataclass
   class AppContext:
       """Application context shared between tools."""
       gemini: GeminiClient
       claude: ClaudeClient
       firecrawl: FirecrawlClient
       search_service: SearchService  # Add search service
       config: Dict[str, Any]

   @asynccontextmanager
   async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
       """Manage application lifecycle."""
       # Initialize clients
       # ...
       
       # Initialize search service
       search_service = SearchService()
       
       try:
           yield AppContext(
               # ...
               search_service=search_service,
               config=config
           )
       finally:
           pass
   ```

3. **Add MCP Tool**

   Add a new tool in `main.py`:
   ```python
   @mcp.tool()
   def advanced_search(query: str, num_results: int = 10, ctx: Context = None) -> List[Dict[str, Any]]:
       """Perform advanced web search using external search API.
       
       Args:
           query: Search query
           num_results: Number of results to return
           ctx: The MCP context
           
       Returns:
           List of search results
       """
       app_ctx = ctx.request_context.lifespan_context
       
       try:
           ctx.info(f"Performing advanced search for: {query}")
           return app_ctx.search_service.search_web(query, num_results)
       except ValueError as e:
           return {"error": str(e)}
   ```

## Best Practices

When extending the Multi-AI Agent:

1. **Keep the MCP Interface Clean**
   - Tools should have clear, descriptive names and documentation
   - Use type hints to make the interface self-documenting
   - Group related tools logically

2. **Separate Business Logic**
   - Keep implementation details in the client wrapper classes
   - The MCP tools should focus on parameter validation and routing

3. **Handle Errors Gracefully**
   - Use try/except blocks to catch and report errors
   - Provide meaningful error messages to clients

4. **Test New Components**
   - Write tests for each new client wrapper and tool
   - Test edge cases and error conditions

5. **Resource Management**
   - For expensive APIs (like advanced AI models), implement tiered usage
   - Add configuration options to control resource usage
   - Log usage patterns to help optimize costs
