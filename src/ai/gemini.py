"""Gemini AI 模型實現。

這個模塊提供了使用 Google Gemini AI 服務的模型實現。
"""
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union

from src.ai.base import TextGenerationModel, EmbeddingModel
from src.ai.factory import register_ai_model

# 嘗試導入 google.generativeai
try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except ImportError:
    genai = None
    genai_types = None
    HAS_GENAI = False
    logging.getLogger(__name__).warning("未安裝Google Generative AI SDK，某些功能將不可用")

# 日誌
logger = logging.getLogger(__name__)

class GeminiAI(TextGenerationModel, EmbeddingModel):
    """Google Gemini AI 模型實現。"""
    
    def __init__(self, 
                api_key: Optional[str] = None, 
                model: str = "gemini-2.0-flash-thinking-exp-01-21",
                temperature: float = 0.7, 
                max_tokens: int = 4000,
                **kwargs):
        """初始化 Gemini AI 模型。
        
        Args:
            api_key: Google AI API 密鑰。如果為空，將嘗試從環境變量獲取。
            model: 模型名稱。
            temperature: 溫度參數。
            max_tokens: 最大生成令牌數。
            **kwargs: 其他參數。
        """
        self._model_name = model
        
        # 設置API密鑰
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("AI_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("未設置 Google API Key，將無法使用 Gemini 服務")
        
        # 模型配置
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._embedding_dimensions = 768  # 默認值
        
        # 重試設置
        self.max_retries = kwargs.get("max_retries", 3)
        self.base_delay = kwargs.get("base_delay", 1)
        self.max_delay = kwargs.get("max_delay", 10)
        
        # Gemini 客戶端
        self.client = None
        
        # 初始化標志
        self.is_initialized = False
        
        # 嘗試初始化
        self._initialize()
    
    @property
    def model_name(self) -> str:
        """獲取當前使用的模型名稱。
        
        Returns:
            模型名稱。
        """
        return self._model_name
    
    def set_model(self, model_name: str) -> None:
        """設置要使用的模型。
        
        Args:
            model_name: 模型名稱。
        """
        self._model_name = model_name
        logger.info(f"已設置 Gemini 模型為 {model_name}")
    
    def is_available(self) -> bool:
        """檢查 AI 服務是否可用。
        
        Returns:
            如果服務當前可用，則為 True。
        """
        return self.is_initialized
    
    def _initialize(self) -> bool:
        """初始化 Gemini 客戶端。
        
        Returns:
            初始化是否成功。
        """
        try:
            if not self.api_key or not HAS_GENAI:
                logger.warning("Gemini AI 未初始化：缺少API密鑰或未安裝SDK")
                return False
            
            # 使用新版 SDK 初始化客戶端
            self.client = genai.Client(api_key=self.api_key)
            
            # 測試客戶端是否可用
            try:
                models = self.client.models.list()
                available_models = [model.name for model in models]
                # logger.info(f"可用模型: {available_models}")
                
                # 檢查指定的模型是否可用
                if self._model_name not in available_models and not self._model_name.startswith('gemini-'):
                    # 嘗試找到匹配的模型名稱
                    for avail_model in available_models:
                        if self._model_name in avail_model:
                            self._model_name = avail_model
                            logger.info(f"使用匹配模型: {self._model_name}")
                            break
            except Exception as e:
                logger.warning(f"無法列出模型: {e}")
            
            self.is_initialized = True
            logger.info(f"Gemini AI 已初始化，使用模型 {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"初始化 Gemini AI 時出錯: {e}")
            self.is_initialized = False
            return False
    
    def retry_with_exponential_backoff(self, func, max_retries=None, base_delay=None, max_delay=None):
        """使用指數退避重試函數。
        
        Args:
            func: 要重試的函數。
            max_retries: 最大重試次數。
            base_delay: 基礎延遲秒數。
            max_delay: 最大延遲秒數。
            
        Returns:
            函數調用結果。
            
        Raises:
            最後一次函數調用引發的異常。
        """
        max_retries = max_retries or self.max_retries
        base_delay = base_delay or self.base_delay
        max_delay = max_delay or self.max_delay
        
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt == max_retries - 1:
                    raise
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"嘗試 {attempt + 1} 失敗，錯誤: {e}，{delay} 秒後重試...")
                time.sleep(delay)
        raise last_exception  # 不應該到達這裡
    
    async def generate_text(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        """生成文本。
        
        Args:
            prompt: 提示文本。
            max_tokens: 最大生成令牌數。
            **kwargs: 其他參數。
            
        Returns:
            生成的文本。
            
        Raises:
            RuntimeError: 如果生成過程中出錯。
        """
        if not self.is_initialized and not self._initialize():
            raise RuntimeError("Gemini AI 未初始化")
        
        try:
            # 構建生成配置
            temperature = kwargs.get("temperature", self.temperature)
            max_tokens = kwargs.get("max_tokens", self.max_tokens) or max_tokens
            system_prompt = kwargs.get("system_prompt")
            
            # 生成配置
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            
            # 生成文本
            def _call_api():
                config = None
                if system_prompt:
                    # 使用系統提示
                    config = genai_types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                        system_instruction=system_prompt
                    )
                    return self.client.models.generate_content(
                        model=self._model_name,
                        contents=prompt,
                        config=config
                    )
                else:
                    # 不使用系統提示
                    return self.client.models.generate_content(
                        model=self._model_name,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(
                            temperature=temperature,
                            max_output_tokens=max_tokens
                        )
                    )
            
            response = self.retry_with_exponential_backoff(_call_api)
            
            # 提取並返回文本響應
            return response.text
            
        except Exception as e:
            error_msg = f"使用 Gemini 生成文本時出錯: {str(e)}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg)
    
    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 1024, **kwargs) -> str:
        """使用對話格式生成響應。
        
        Args:
            messages: 消息列表，每個消息包含 'role' 和 'content'。
            max_tokens: 最大生成令牌數。
            **kwargs: 其他參數。
            
        Returns:
            生成的響應文本。
        """
        if not self.is_initialized and not self._initialize():
            raise RuntimeError("Gemini AI 未初始化")
        
        try:
            # 構建生成配置
            temperature = kwargs.get("temperature", self.temperature)
            max_tokens = kwargs.get("max_tokens", self.max_tokens) or max_tokens
            system_instruction = None
            
            # 格式化消息列表
            formatted_contents = []
            for msg in messages:
                if msg["role"] == "system":
                    # 將系統消息設置為系統指令
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    # 用戶消息
                    formatted_contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=msg["content"])]
                        )
                    )
                elif msg["role"] == "assistant":
                    # 助手消息
                    formatted_contents.append(
                        genai_types.Content(
                            role="model",
                            parts=[genai_types.Part.from_text(text=msg["content"])]
                        )
                    )
            
            # 如果沒有消息，返回錯誤
            if not formatted_contents:
                raise ValueError("沒有有效的消息")
            
            # 生成文本
            def _call_api():
                config = genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
                
                if system_instruction:
                    config.system_instruction = system_instruction
                
                return self.client.models.generate_content(
                    model=self._model_name,
                    contents=formatted_contents,
                    config=config
                )
            
            response = self.retry_with_exponential_backoff(_call_api)
            
            # 提取並返回文本響應
            return response.text
            
        except Exception as e:
            error_msg = f"使用 Gemini 生成聊天回复時出錯: {str(e)}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg)
    
    async def count_tokens(self, text: str) -> int:
        """計算文本中的 token 數量。
        
        Args:
            text: 要計算的文本。
            
        Returns:
            token 數量。
        """
        if not self.is_initialized and not self._initialize():
            raise RuntimeError("Gemini AI 未初始化")
        
        try:
            # 使用 API 計算 token
            response = self.client.models.count_tokens(
                model=self._model_name,
                contents=text
            )
            return response.total_tokens
        except Exception as e:
            logger.warning(f"計算 token 時出錯: {e}")
            # 使用近似估計：每 4 個字符大約 1 個 token
            return len(text) // 4

    async def generate_embedding(self, text: str) -> List[float]:
        """生成文本的嵌入向量。
        
        Args:
            text: 要嵌入的文本。
            
        Returns:
            浮點數列表，表示文本的嵌入向量。
        """
        if not self.is_initialized and not self._initialize():
            raise RuntimeError("Gemini AI 未初始化")
        
        try:
            # 嘗試使用嵌入模型生成嵌入
            response = self.client.models.embed_content(
                model="text-embedding-004",  # 使用專門的嵌入模型
                contents=text
            )
            # API 返回結構可能不同，嘗試多種方式獲取嵌入向量
            if hasattr(response, 'embedding'):
                if hasattr(response.embedding, 'values'):
                    return response.embedding.values
                return response.embedding
            elif hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                if hasattr(response.embeddings[0], 'values'):
                    return response.embeddings[0].values
                return response.embeddings[0]
            else:
                # 如果無法獲取嵌入向量，記錄詳細信息並返回零向量
                logger.error(f"無法從響應中獲取嵌入向量: {response}")
                return [0.0] * self._embedding_dimensions
        except Exception as e:
            logger.warning(f"生成嵌入向量時出錯: {e}")
            # 返回一個零向量作為後備
            return [0.0] * self._embedding_dimensions

    async def batch_generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本的嵌入向量。
        
        Args:
            texts: 要嵌入的文本列表。
            
        Returns:
            嵌入向量列表。
        """
        if not self.is_initialized and not self._initialize():
            raise RuntimeError("Gemini AI 未初始化")
        
        try:
            # 嘗試使用嵌入模型生成批量嵌入
            response = self.client.models.embed_content(
                model="text-embedding-004",  # 使用專門的嵌入模型
                contents=texts
            )
            
            # 提取嵌入向量
            embeddings = []
            
            # 檢查應答的結構
            if hasattr(response, 'embeddings'):
                for embedding in response.embeddings:
                    if hasattr(embedding, 'values'):
                        embeddings.append(embedding.values)
                    else:
                        embeddings.append(embedding)
            elif hasattr(response, 'embedding'):
                # 單一嵌入向量情況
                if hasattr(response.embedding, 'values'):
                    embeddings.append(response.embedding.values)
                else:
                    embeddings.append(response.embedding)
            
            # 如果沒有成功提取嵌入向量，則記錄錯誤
            if not embeddings:
                logger.error(f"無法從批量嵌入應答中提取嵌入向量: {response}")
                return [[0.0] * self._embedding_dimensions for _ in texts]
            
            # 回填到預期的長度
            while len(embeddings) < len(texts):
                embeddings.append([0.0] * self._embedding_dimensions)
            
            return embeddings
        except Exception as e:
            logger.warning(f"批量生成嵌入向量時出錯: {e}")
            # 為每個文本生成零向量
            return [[0.0] * self._embedding_dimensions for _ in texts]

    @property
    def embedding_dimensions(self) -> int:
        """獲取嵌入向量的維度。
        
        Returns:
            嵌入向量的維度。
        """
        return self._embedding_dimensions


# 註冊 Gemini AI 模型
register_ai_model("gemini", GeminiAI)
logger.info("已註冊 Gemini AI 模型")
