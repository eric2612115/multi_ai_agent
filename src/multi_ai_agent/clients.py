"""Client wrappers for various AI services."""
import os
import time
import random
from typing import Dict, List, Optional, Union, Any, Callable

from dotenv import load_dotenv, find_dotenv
# SDKs
from google import genai
from google.genai import types as genai_types
from anthropic import Anthropic
from anthropic._exceptions import OverloadedError, RateLimitError
from firecrawl import FirecrawlApp

from multi_ai_agent.services.web_extraction import WebExtractionService

class GeminiClient:
    """Wrapper for Google Gemini SDK."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini client.
        
        Args:
            api_key: The API key for Gemini. If not provided, it will be loaded from
                the GEMINI_API_KEY environment variable.
        """
        load_dotenv(find_dotenv())
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"  # Default model
        self.genai = genai  # Export genai module for type access
        print("Gemini client initialized")
    
    def generate_text(self, prompt: str, max_tokens: int = 1024, model: Optional[str] = None) -> str:
        """Generate text using Gemini.
        
        Args:
            prompt: The prompt to generate text from.
            max_tokens: The maximum number of tokens to generate.
            model: Optional model name to override the default.
            
        Returns:
            The generated text.
        """
        model_name = model or self.model
        
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
            ),
        )
        return response.text
    
    def search_web(self, query: str) -> str:
        """Search the web using Gemini's search grounding.
        
        Args:
            query: The search query.
            
        Returns:
            The search results.
        """
        google_search_tool = genai_types.Tool(
            google_search=genai_types.GoogleSearch()
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=query,
            config=genai_types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
            )
        )
        
        return response.text
    
    def set_model(self, model_name: str) -> None:
        """Set the Gemini model to use.
        
        Args:
            model_name: The name of the model to use.
        """
        self.model = model_name


class ClaudeClient:
    """Wrapper for Anthropic Claude SDK."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Claude client.
        
        Args:
            api_key: The API key for Claude. If not provided, it will be loaded from
                the ANTHROPIC_API_KEY environment variable.
        """
        load_dotenv(find_dotenv())
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-sonnet-20240620"  # Default model
        # 儲存Gemini備用客戶端為None，首次需要時才建立
        self._gemini_fallback = None
    
    def generate_text(self, prompt: str, max_tokens: int = 1024, model: Optional[str] = None, 
                     max_retries: int = 3, initial_backoff: float = 1.0) -> str:
        """Generate text using Claude with retry logic and Gemini fallback.
        
        Args:
            prompt: The prompt to generate text from.
            max_tokens: The maximum number of tokens to generate.
            model: Optional model name to override the default.
            max_retries: Maximum number of retry attempts.
            initial_backoff: Initial backoff time in seconds.
            
        Returns:
            The generated text.
        """
        model_name = model or self.model
        
        # 重試邏輯
        retries = 0
        backoff = initial_backoff
        
        while True:
            try:
                message = self.client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )
                return message.content[0].text
                
            except (OverloadedError, RateLimitError) as e:
                retries += 1
                if retries > max_retries:
                    # 超過最大重試次數，使用Gemini備用方案
                    print(f"Claude API 服務過載且重試{max_retries}次後仍失敗，將切換到Gemini模型...")
                    # 切換到Gemini備用方案
                    return self._fallback_to_gemini(prompt, max_tokens)
                
                # 計算退避時間，添加抖動以避免同步請求
                jitter = random.uniform(0, 0.1 * backoff)
                sleep_time = backoff + jitter
                
                print(f"Claude API 服務過載，將在 {sleep_time:.2f} 秒後重試 (嘗試 {retries}/{max_retries})...")
                time.sleep(sleep_time)
                
                # 指數退避
                backoff *= 2
                
            except Exception as e:
                # 處理其他異常，可以嘗試使用Gemini作為備用方案
                print(f"Claude API 發生非預期錯誤: {str(e)}，將切換到Gemini模型...")
                return self._fallback_to_gemini(prompt, max_tokens)
    
    def _fallback_to_gemini(self, prompt: str, max_tokens: int = 1024) -> str:
        """當Claude不可用時，使用Gemini作為備用選項
        
        Args:
            prompt: 提示文本
            max_tokens: 最大令牌數
            
        Returns:
            生成的文本
        """
        # 懶加載Gemini客戶端
        if self._gemini_fallback is None:
            from multi_ai_agent.clients import GeminiClient
            self._gemini_fallback = GeminiClient()
            # 使用高級Gemini模型作為備用
            self._gemini_fallback.set_model("gemini-2.5-pro-exp-03-25")
            
        try:
            print("使用Gemini模型處理請求...")
            return self._gemini_fallback.generate_text(prompt, max_tokens=max_tokens)
        except Exception as gemini_err:
            # 如果Gemini也失敗，返回錯誤信息
            error_msg = f"無法從Claude或Gemini獲取回應。Claude錯誤: 服務過載, Gemini錯誤: {str(gemini_err)}"
            print(error_msg)
            return f"無法生成回應。服務暫時不可用。請稍後再試。詳細錯誤: {error_msg}"
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text.
        
        Args:
            text: The text to count tokens for.
            
        Returns:
            The token count.
        """
        count = self.client.beta.messages.count_tokens(
            model=self.model,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        return count.input_tokens
    
    def set_model(self, model_name: str) -> None:
        """Set the Claude model to use.
        
        Args:
            model_name: The name of the model to use.
        """
        self.model = model_name


class FirecrawlClient:
    """Wrapper for Firecrawl SDK with enhanced capabilities."""
    
    def __init__(self, api_key: Optional[str] = None, logger: Callable = print):
        """Initialize the Firecrawl client.
        
        Args:
            api_key: The API key for Firecrawl. If not provided, it will be loaded from
                the FIRECRAWL_API_KEY environment variable.
            logger: Function to use for logging status messages.
        """
        load_dotenv(find_dotenv())
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable not set")
        
        self.client = FirecrawlApp(api_key=self.api_key)
        self.logger = logger
        self._extraction_service = None
    
    def set_extraction_service(self, gemini_client=None, claude_client=None):
        """Set up the web extraction service with AI capabilities.
        
        Args:
            gemini_client: Optional Gemini client for enhanced capabilities.
            claude_client: Optional Claude client for enhanced capabilities.
        """
        self._extraction_service = WebExtractionService(
            firecrawl_client=self.client,
            gemini_client=gemini_client,
            claude_client=claude_client,
            logger=self.logger
        )
    
    def scrape_url(self, url: str, formats: List[str] = None) -> Dict[str, Any]:
        """Scrape a URL.
        
        Args:
            url: The URL to scrape.
            formats: The formats to return. Defaults to ['markdown'].
            
        Returns:
            The scraped content.
        """
        if formats is None:
            formats = ['markdown']
        
        self.logger(f"Scraping URL: {url}")
        return self.client.scrape_url(
            url, 
            params={'formats': formats}
        )
    
    def map_url(self, url: str, search: Optional[str] = None) -> Dict[str, Any]:
        """Map a website to get its structure.
        
        Args:
            url: The URL to map.
            search: Optional search term to filter URLs.
            
        Returns:
            The site map.
        """
        params = {}
        if search:
            params["search"] = search
            
        self.logger(f"Mapping website: {url}")
        return self.client.map_url(url, params=params)
    
    def smart_extract(
        self, 
        url: str, 
        objective: str, 
        use_advanced_model: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Smart extraction with objective-based crawling and content analysis.
        
        Args:
            url: URL of the website to analyze.
            objective: User's information objective.
            use_advanced_model: Whether to use advanced (more expensive) models.
            
        Returns:
            Extracted information or None if extraction failed.
        """
        if not self._extraction_service:
            self.logger("Web extraction service not initialized. Using basic scraping.")
            return {"content": self.scrape_url(url)}
            
        return self._extraction_service.smart_extract_from_site(
            url=url,
            objective=objective,
            standard_model=not use_advanced_model
        )
    
    def advanced_extract(
        self, 
        urls: List[str], 
        prompt: str, 
        entity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Advanced extraction using Firecrawl's API.
        
        Args:
            urls: List of URLs to extract from.
            prompt: Extraction prompt/objective.
            entity: Optional entity name (e.g., company name).
            
        Returns:
            Extracted structured data or None if extraction failed.
        """
        if not self._extraction_service:
            self.logger("Web extraction service not initialized.")
            return None
            
        return self._extraction_service.advanced_extract_with_api(
            urls=urls,
            prompt=prompt,
            entity=entity
        )
    
    def search_and_extract(
        self, 
        entity: str, 
        objective: str, 
        search_api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Search for entity and extract information (requires SerpAPI key).
        
        Args:
            entity: Entity to search for (e.g., company name).
            objective: Information objective.
            search_api_key: Optional SerpAPI key (required for this feature).
            
        Returns:
            Extracted information or None if extraction failed.
        """
        if not search_api_key:
            search_api_key = os.environ.get("SERP_API_KEY")
            
        if not search_api_key:
            self.logger("SERP_API_KEY environment variable not set. Cannot perform search.")
            return None
            
        if not self._extraction_service:
            self.logger("Web extraction service not initialized.")
            return None
            
        # This method requires additional imports and implementation
        # For now, return an informative message
        self.logger("Search and extract feature requires additional setup.")
        self.logger("Please use the individual search and extract tools instead.")
        return None
