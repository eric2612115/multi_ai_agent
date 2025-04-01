"""
Web extraction service combining Firecrawl and Gemini capabilities.
This module provides different levels of web extraction capabilities:
- Basic: Simple web scraping using Firecrawl
- Standard: Smart web extraction using Firecrawl + Gemini standard models
- Advanced: Powerful extraction using Firecrawl + Gemini Pro models
"""
import json
import re
import time
from typing import Dict, List, Optional, Any, Tuple, Union
import requests
from requests.exceptions import RequestException

# MIME type detection
def detect_mime_type(url: str, timeout: int = 8) -> Optional[str]:
    """
    Attempt a HEAD request to detect the Content-Type.
    
    Args:
        url: The URL to check
        timeout: Request timeout in seconds
        
    Returns:
        'pdf', 'image' or None if undetermined
    """
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        ctype = resp.headers.get('Content-Type', '').lower()
        exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif']

        if 'pdf' in ctype:
            return 'pdf'
        elif ctype.startswith('image/') and any(url.lower().endswith(ext) for ext in exts):
            return 'image'
        return None
    except RequestException:
        return None


def extract_urls_from_markdown(markdown_text: str) -> List[str]:
    """
    Extract URLs from markdown content.
    
    Args:
        markdown_text: Markdown text to extract URLs from
        
    Returns:
        List of unique URLs found in the markdown
    """
    pattern = r'(https?://[^\s\'")]+)'
    found = re.findall(pattern, markdown_text)
    return list(set(found))  # Remove duplicates


def pdf_size_in_mb(data: bytes) -> float:
    """
    Calculate the size of PDF data in megabytes.
    
    Args:
        data: PDF data in bytes
        
    Returns:
        Size in MB
    """
    return len(data) / (1024 * 1024)


class WebExtractionService:
    """Service for extracting information from websites with different capabilities levels."""
    
    def __init__(
        self, 
        firecrawl_client,
        gemini_client=None,
        claude_client=None,
        max_pdf_size_mb: float = 15.0,
        logger=None
    ):
        """
        Initialize the web extraction service.
        
        Args:
            firecrawl_client: Firecrawl client instance
            gemini_client: Optional Gemini client for enhanced capabilities
            claude_client: Optional Claude client for enhanced capabilities
            max_pdf_size_mb: Maximum PDF size to process in MB
            logger: Optional logger function for status updates
        """
        self.firecrawl = firecrawl_client
        self.gemini = gemini_client
        self.claude = claude_client
        self.max_pdf_size_mb = max_pdf_size_mb
        self.log = logger or print
        
    def basic_scrape(self, url: str, formats: List[str] = None) -> Dict[str, Any]:
        """
        Basic scraping using Firecrawl only.
        
        Args:
            url: URL to scrape
            formats: List of formats to return (e.g., ['markdown', 'html'])
            
        Returns:
            Dictionary containing the scraped content
        """
        if formats is None:
            formats = ['markdown']
            
        self.log(f"Scraping URL: {url}")
        return self.firecrawl.scrape_url(url, params={'formats': formats})
        
    def basic_map_website(self, url: str, search: Optional[str] = None) -> List[str]:
        """
        Map a website structure using Firecrawl.
        
        Args:
            url: URL to map
            search: Optional search term to filter results
            
        Returns:
            List of URLs found on the website
        """
        params = {}
        if search:
            params["search"] = search
            
        self.log(f"Mapping website: {url}")
        result = self.firecrawl.map_url(url, params=params)
        
        # Extract links from the result
        if isinstance(result, dict):
            links = result.get('urls', []) or result.get('links', [])
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
                links = parsed.get('urls', []) or parsed.get('links', [])
            except json.JSONDecodeError:
                links = []
        else:
            links = result if isinstance(result, list) else []
            
        return links
        
    def smart_extract_from_site(
        self, 
        url: str, 
        objective: str, 
        standard_model: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Smart extraction with search parameter generation and content analysis.
        
        Args:
            url: URL of the website to analyze
            objective: User's information objective
            standard_model: Whether to use standard models (True) or Pro models (False)
            
        Returns:
            Extracted information as a dictionary or None if extraction failed
        """
        if not self.gemini:
            self.log("Smart extraction requires Gemini. Using basic extraction instead.")
            return {"content": self.basic_scrape(url)}
        
        # Choose appropriate model
        model_name = "gemini-2.0-flash" if standard_model else "gemini-2.5-pro-exp-03-25"
        
        # Step 1: Generate search parameter from objective
        self.log(f"Analyzing objective: {objective}")
        map_prompt = f"""
        Based on the objective of: {objective}, provide a 1-2 word search parameter that will help find the information.
        Respond with ONLY 1-2 words, no other text or formatting.
        """
        
        search_param_response = self.gemini.generate_text(
            prompt=map_prompt,
            model=model_name
        )
        search_param = search_param_response.strip()
        self.log(f"Generated search parameter: {search_param}")
        
        # Step 2: Map the website with the search parameter
        links = self.basic_map_website(url, search=search_param)
        if not links:
            self.log("No relevant pages found.")
            return None
            
        # Step 3: Rank the links by relevance
        rank_prompt = f"""RESPOND ONLY WITH JSON. 
        Analyze these URLs and rank the top 3 most relevant ones for finding information about: {objective}

        Return ONLY a JSON array in this exact format - no other text or explanation:
        [
            {{
                "url": "http://example.com",
                "relevance_score": 95,
                "reason": "Main about page with company information"
            }},
            {{
                "url": "http://example2.com",
                "relevance_score": 85,
                "reason": "Team page with details"
            }},
            {{
                "url": "http://example3.com",
                "relevance_score": 75,
                "reason": "Blog post about company"
            }}
        ]

        URLs to analyze:
        {json.dumps(links[:20], indent=2)}"""
        
        ranking_response = self.gemini.generate_text(
            prompt=rank_prompt,
            model=model_name
        )
        
        try:
            # Extract JSON from response
            response_text = ranking_response.strip()
            if '[' in response_text and ']' in response_text:
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                json_str = response_text[start_idx:end_idx]
                ranked_results = json.loads(json_str)
                top_links = [result["url"] for result in ranked_results]
            else:
                # Fallback to top 3 links from the map result
                self.log("Could not parse ranking result. Using top links from site map.")
                top_links = links[:3]
        except json.JSONDecodeError:
            self.log("Error parsing ranked results. Using top links from site map.")
            top_links = links[:3]
        except Exception as e:
            self.log(f"Unexpected error ranking links: {str(e)}")
            top_links = links[:3]
            
        # Step 4: Analyze the top pages
        for link in top_links[:3]:  # Limit to top 3
            self.log(f"Analyzing page: {link}")
            
            # Scrape the page
            scrape_result = self.basic_scrape(link)
            page_markdown = scrape_result.get('markdown', '')
            if not page_markdown:
                self.log(f"No content found on page: {link}")
                continue
                
            # Process any PDFs or images if using Pro model
            if not standard_model:
                found_urls = extract_urls_from_markdown(page_markdown)
                pdf_image_content = ""
                
                for sub_url in found_urls:
                    mime_type = detect_mime_type(sub_url)
                    
                    if mime_type == 'pdf':
                        self.log(f"Processing PDF: {sub_url}")
                        pdf_content = self._extract_pdf_content(sub_url, objective)
                        if pdf_content:
                            pdf_image_content += f"\n\n---\n[PDF from {sub_url}]:\n{pdf_content}"
                            
                    elif mime_type == 'image':
                        self.log(f"Processing image: {sub_url}")
                        image_content = self._extract_image_content(sub_url)
                        if image_content:
                            pdf_image_content += f"\n\n---\n[Image from {sub_url}]:\n{image_content}"
                
                # Add the extracted content to the page markdown
                if pdf_image_content:
                    page_markdown += f"\n\n---\n**Additional Extracted Content:**\n{pdf_image_content}"
            
            # Analysis prompt for the content
            check_prompt = f"""
            Analyze this content to find: {objective}
            If found, return ONLY a JSON object with information related to the objective. If not found, respond EXACTLY with: Objective not met
            
            Content to analyze:
            {page_markdown}
            
            Remember:
            - Return valid JSON if information is found
            - Return EXACTLY "Objective not met" if not found
            - No other text or explanations
            """
            
            analysis_response = self.gemini.generate_text(
                prompt=check_prompt,
                model=model_name
            )
            
            result_text = analysis_response.strip()
            
            if result_text != "Objective not met":
                self.log("Found relevant information.")
                try:
                    if '{' in result_text and '}' in result_text:
                        start_idx = result_text.find('{')
                        end_idx = result_text.rfind('}') + 1
                        json_str = result_text[start_idx:end_idx]
                        extracted_data = json.loads(json_str)
                        
                        # Add metadata
                        return {
                            "source_url": link,
                            "objective": objective,
                            "data": extracted_data
                        }
                except json.JSONDecodeError:
                    self.log("Error parsing extraction result.")
            
            self.log("Objective not met on this page. Trying next page...")
        
        self.log("Could not fulfill the objective with available content.")
        return None
    
    def advanced_extract_with_api(
        self, 
        urls: List[str], 
        prompt: str, 
        entity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Use Firecrawl's extract API for advanced extraction.
        
        Args:
            urls: List of URLs to extract from
            prompt: Extraction prompt/objective
            entity: Optional entity name (e.g., company name)
            
        Returns:
            Extracted structured data or None if extraction failed
        """
        if not urls:
            self.log("No URLs provided for extraction.")
            return None
            
        self.log(f"Extracting data from {len(urls)} URLs using Firecrawl extract API.")
        
        # Build the API request
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.firecrawl.client.api_key}'
        }
        
        # Add entity to prompt if provided
        complete_prompt = f"{prompt} for {entity}" if entity else prompt
        
        payload = {
            "urls": urls,
            "prompt": complete_prompt,
            "enableWebSearch": True  # Enable web search for better results
        }
        
        try:
            # Make the API request
            self.log("Sending extract request to Firecrawl API...")
            response = requests.post(
                "https://api.firecrawl.dev/v1/extract",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            data = response.json()
            
            if not data.get('success'):
                self.log(f"API error: {data.get('error', 'Unknown error')}")
                return None
            
            extraction_id = data.get('id')
            if not extraction_id:
                self.log("No extraction ID in response.")
                return None
                
            # Poll for results
            return self._poll_extraction_result(extraction_id)
            
        except requests.exceptions.RequestException as e:
            self.log(f"Request error: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.log(f"JSON parsing error: {str(e)}")
            return None
        except Exception as e:
            self.log(f"Unexpected error: {str(e)}")
            return None
    
    def _poll_extraction_result(
        self, 
        extraction_id: str, 
        interval: int = 10, 
        max_attempts: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Poll the Firecrawl API for extraction results.
        
        Args:
            extraction_id: The extraction job ID
            interval: Polling interval in seconds
            max_attempts: Maximum number of polling attempts
            
        Returns:
            The extracted data or None if polling failed
        """
        url = f"https://api.firecrawl.dev/v1/extract/{extraction_id}"
        headers = {
            'Authorization': f'Bearer {self.firecrawl.client.api_key}'
        }
        
        self.log("Waiting for extraction to complete...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get('success') and data.get('data'):
                    self.log("Extraction completed successfully.")
                    return data['data']
                elif data.get('success') and not data.get('data'):
                    if attempt % 6 == 0:  # Log every minute
                        self.log(f"Still processing... (attempt {attempt}/{max_attempts})")
                    time.sleep(interval)
                else:
                    self.log(f"API Error: {data.get('error', 'Unknown error')}")
                    return None
                    
            except Exception as e:
                self.log(f"Error polling for results: {str(e)}")
                return None
                
        self.log("Maximum polling attempts reached. Extraction timed out.")
        return None
    
    def _extract_pdf_content(self, pdf_url: str, objective: str) -> Optional[str]:
        """
        Extract content from PDF using Gemini.
        
        Args:
            pdf_url: URL of the PDF
            objective: User's information objective
            
        Returns:
            Extracted text from the PDF or None if extraction failed
        """
        if not self.gemini:
            return None
            
        try:
            # Download the PDF
            pdf_data = requests.get(pdf_url, timeout=15).content
            size_mb = pdf_size_in_mb(pdf_data)
            
            if size_mb > self.max_pdf_size_mb:
                self.log(f"PDF too large ({size_mb:.1f} MB). Skipping.")
                return None
                
            # Process with Gemini
            pdf_prompt = f"""
            The objective is: {objective}.
            From this PDF, extract only the text that helps address this objective.
            If it contains no relevant info, return an empty string.
            """
            
            # Different handling based on the client implementation
            try:
                response = self.gemini.client.models.generate_content(
                    model="gemini-2.5-pro-exp-03-25",
                    contents=[
                        self.gemini.client.genai.types.Part.from_bytes(
                            data=pdf_data, mime_type="application/pdf"),
                        pdf_prompt
                    ]
                )
                return response.text.strip()
            except AttributeError:
                self.log("PDF processing requires direct access to Gemini client.")
                return None
                
        except Exception as e:
            self.log(f"Error processing PDF: {str(e)}")
            return None
    
    def _extract_image_content(self, image_url: str) -> Optional[str]:
        """
        Extract content from image using Gemini.
        
        Args:
            image_url: URL of the image
            
        Returns:
            Description of the image or None if extraction failed
        """
        if not self.gemini:
            return None
            
        try:
            # Download the image
            image_data = requests.get(image_url, timeout=15).content
            
            # Process with Gemini
            try:
                response = self.gemini.client.models.generate_content(
                    model="gemini-2.5-pro-exp-03-25",
                    contents=[
                        "Describe the contents of this image in a short paragraph.",
                        self.gemini.client.genai.types.Part.from_bytes(
                            data=image_data, mime_type="image/jpeg")
                    ]
                )
                return f"**Image Summary**:\n{response.text.strip()}"
            except AttributeError:
                self.log("Image processing requires direct access to Gemini client.")
                return None
                
        except Exception as e:
            self.log(f"Error processing image: {str(e)}")
            return None
