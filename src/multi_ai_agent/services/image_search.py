"""
圖片搜索和下載服務
提供網絡圖片搜索、處理和下載功能
"""
import os
import re
import time
import json
import random
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
import shutil

class ImageSearchService:
    """圖片搜索和下載服務"""
    
    def __init__(
        self, 
        download_folder: str = "downloads/images",
        search_api_key: Optional[str] = None,
        logger=None
    ):
        """
        初始化圖片搜索服務
        
        Args:
            download_folder: 圖片下載儲存的資料夾路徑
            search_api_key: 可選的搜索 API 金鑰 (SerpAPI 等)
            logger: 記錄器函數
        """
        self.download_folder = Path(download_folder)
        self.search_api_key = search_api_key
        self.log = logger or print
        
        # 確保下載資料夾存在
        os.makedirs(self.download_folder, exist_ok=True)
    
    def search_and_download_image(
        self, 
        query: str, 
        max_results: int = 1, 
        safe_search: bool = True
    ) -> List[str]:
        """
        搜索並下載符合查詢的圖片
        
        Args:
            query: 搜索關鍵詞
            max_results: 最大下載數量
            safe_search: 是否啟用安全搜索
            
        Returns:
            下載圖片的路徑列表
        """
        self.log(f"搜索圖片: {query}")
        
        # 下載的圖片路徑列表
        downloaded_images = []
        
        try:
            # 如果有 SerpAPI 金鑰，使用 SerpAPI 搜索
            if self.search_api_key:
                image_urls = self._search_images_with_serpapi(query, max_results, safe_search)
            else:
                # 備用方案：使用基本 HTTP 請求搜索
                image_urls = self._search_images_basic(query, max_results, safe_search)
            
            # 下載找到的圖片
            for i, url in enumerate(image_urls):
                if i >= max_results:
                    break
                    
                try:
                    image_path = self._download_image(url, f"{query}_{i}")
                    if image_path:
                        downloaded_images.append(image_path)
                        self.log(f"✓ 成功下載圖片: {image_path}")
                except Exception as e:
                    self.log(f"✗ 無法下載圖片 {url}: {str(e)}")
            
            return downloaded_images
            
        except Exception as e:
            self.log(f"圖片搜索出錯: {str(e)}")
            return downloaded_images
    
    def download_image_from_url(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """
        從 URL 下載圖片
        
        Args:
            url: 圖片 URL
            filename: 可選的檔案名稱 (不含副檔名)
            
        Returns:
            下載的圖片路徑或 None (如果下載失敗)
        """
        try:
            return self._download_image(url, filename)
        except Exception as e:
            self.log(f"下載圖片失敗 {url}: {str(e)}")
            return None
    
    def _search_images_with_serpapi(
        self, 
        query: str, 
        max_results: int = 5,
        safe_search: bool = True
    ) -> List[str]:
        """
        使用 SerpAPI 搜索圖片
        
        Args:
            query: 搜索關鍵詞
            max_results: 最大結果數
            safe_search: 是否啟用安全搜索
            
        Returns:
            圖片 URL 列表
        """
        try:
            import serpapi
            
            params = {
                "engine": "google_images",
                "q": query,
                "google_domain": "google.com",
                "ijn": "0",
                "api_key": self.search_api_key,
                "safe": "active" if safe_search else "off"
            }
            
            try:
                search = serpapi.search(params)
                results = search.get("images_results", [])
                
                # 提取圖片 URL
                image_urls = [result.get("original") or result.get("thumbnail") for result in results[:max_results]]
                return [url for url in image_urls if url]  # 過濾掉 None 值
                
            except Exception as e:
                self.log(f"SerpAPI 搜索出錯: {str(e)}")
                # 備用方案
                return self._search_images_basic(query, max_results, safe_search)
        except ImportError:
            self.log("未安裝 serpapi 模組，使用基本圖片搜索方法")
            return self._search_images_basic(query, max_results, safe_search)
    
    def _search_images_basic(
        self, 
        query: str, 
        max_results: int = 5,
        safe_search: bool = True
    ) -> List[str]:
        """
        基本圖片搜索方法 (無需 API 金鑰)
        
        Args:
            query: 搜索關鍵詞
            max_results: 最大結果數
            safe_search: 是否啟用安全搜索
            
        Returns:
            圖片 URL 列表
        """
        # 嘗試通過 Bing Images
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        safe = "&safesearch=strict" if safe_search else ""
        search_url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}{safe}&form=HDRSC2&first=1"
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 簡單解析 HTML 來尋找圖片 URL
            content = response.text
            image_urls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', content)
            
            # 確保結果不超過要求的數量
            return image_urls[:max_results]
            
        except Exception as e:
            self.log(f"基本圖片搜索出錯: {str(e)}")
            # 返回一個示例圖片作為備用
            return ["https://picsum.photos/800/600"]
    
    def _download_image(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """
        下載圖片並儲存到指定路徑
        
        Args:
            url: 圖片 URL
            filename: 圖片檔名 (不含副檔名)
            
        Returns:
            下載的圖片路徑或 None (如果下載失敗)
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # 發送請求下載圖片
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            response.raise_for_status()
            
            # 從 Content-Type 推測檔案類型
            content_type = response.headers.get('Content-Type', '')
            extension = self._get_extension_from_content_type(content_type)
            
            # 如果無法從 Content-Type 推測，嘗試從 URL 取得
            if not extension and '.' in url.split('?')[0].split('/')[-1]:
                extension = url.split('?')[0].split('/')[-1].split('.')[-1]
                
            # 如果仍然無法確定，使用預設值
            if not extension or extension not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                extension = 'jpg'
            
            # 生成檔名
            if not filename:
                timestamp = int(time.time())
                random_num = random.randint(1000, 9999)
                filename = f"image_{timestamp}_{random_num}"
            
            # 確保檔名安全 (移除不安全字符)
            safe_filename = re.sub(r'[^\w\-_.]', '_', filename)
            output_path = self.download_folder / f"{safe_filename}.{extension}"
            
            # 下載圖片
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            return str(output_path)
            
        except Exception as e:
            self.log(f"下載圖片出錯 ({url}): {str(e)}")
            return None
    
    def _get_extension_from_content_type(self, content_type: str) -> Optional[str]:
        """從 Content-Type 推測檔案副檔名"""
        content_type = content_type.lower()
        
        if 'jpeg' in content_type or 'jpg' in content_type:
            return 'jpg'
        elif 'png' in content_type:
            return 'png'
        elif 'gif' in content_type:
            return 'gif'
        elif 'webp' in content_type:
            return 'webp'
        elif 'bmp' in content_type:
            return 'bmp'
        elif 'svg' in content_type:
            return 'svg'
        
        return None
