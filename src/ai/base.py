"""AI 模型接口。

这个模块定义了 AI 模型的抽象接口，以实现关注点分离和接口隔离原则。
每一个接口代表一种特定的 AI 能力，允许模型实现它们需要的接口。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any, Protocol


class AIModel(ABC):
    """AI 模型基础接口。
    
    这个接口定义了所有 AI 模型共享的基本功能。
    """
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """获取当前使用的模型名称。
        
        Returns:
            模型名称。
        """
        pass
    
    @abstractmethod
    def set_model(self, model_name: str) -> None:
        """设置要使用的模型。
        
        Args:
            model_name: 模型名称。
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查 AI 服务是否可用。
        
        Returns:
            如果服务当前可用，则为 True。
        """
        pass


class TextGenerationModel(AIModel):
    """文本生成模型接口。"""
    
    @abstractmethod
    async def generate_text(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        """生成文本。
        
        Args:
            prompt: 提示文本。
            max_tokens: 生成的最大 token 数量。
            **kwargs: 额外的参数。
            
        Returns:
            生成的文本。
        """
        pass
    
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 1024, **kwargs) -> str:
        """使用对话格式生成响应。
        
        Args:
            messages: 消息列表，每个消息包含 'role' 和 'content'。
            max_tokens: 生成的最大 token 数量。
            **kwargs: 额外的参数。
            
        Returns:
            生成的响应文本。
        """
        pass
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """计算文本中的 token 数量。
        
        Args:
            text: 要计算的文本。
            
        Returns:
            token 数量。
        """
        pass
    
    async def function_call(self, messages: List[Dict[str, str]], functions: List[Dict[str, Any]], 
                          function_call: Optional[Union[str, Dict[str, str]]] = None, **kwargs) -> Dict[str, Any]:
        """调用函数（Function Calling）。
        
        Args:
            messages: 消息列表。
            functions: 函数定义列表。
            function_call: 可选的函数调用指定。
            **kwargs: 额外的参数。
            
        Returns:
            包含函数调用详情的字典。
            
        Raises:
            NotImplementedError: 如果模型不支持函数调用。
        """
        raise NotImplementedError("此模型不支持函数调用")


class EmbeddingModel(AIModel):
    """嵌入向量模型接口。"""
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """生成文本的嵌入向量。
        
        Args:
            text: 要嵌入的文本。
            
        Returns:
            浮点数列表，表示文本的嵌入向量。
        """
        pass
    
    @abstractmethod
    async def batch_generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本的嵌入向量。
        
        Args:
            texts: 要嵌入的文本列表。
            
        Returns:
            嵌入向量列表。
        """
        pass
    
    @property
    @abstractmethod
    def embedding_dimensions(self) -> int:
        """获取嵌入向量的维度。
        
        Returns:
            嵌入向量的维度。
        """
        pass


class SearchModel(AIModel):
    """搜索模型接口。"""
    
    @abstractmethod
    async def search_web(self, query: str, **kwargs) -> Dict[str, Any]:
        """使用网络搜索获取信息。
        
        Args:
            query: 搜索查询。
            **kwargs: 额外的搜索参数。
            
        Returns:
            搜索结果。
        """
        pass


class WebExtractionModel(AIModel):
    """网页提取模型接口。"""
    
    @abstractmethod
    async def extract_content(self, url: str, objective: str, **kwargs) -> Dict[str, Any]:
        """从网页提取特定内容。
        
        Args:
            url: 网页 URL。
            objective: 提取目标，描述要提取什么信息。
            **kwargs: 额外的参数。
            
        Returns:
            包含提取内容的字典。
        """
        pass
    
    @abstractmethod
    async def analyze_image(self, image_data: bytes, prompt: str) -> str:
        """分析图像内容。
        
        Args:
            image_data: 图像数据。
            prompt: 分析提示。
            
        Returns:
            图像分析结果文本。
        """
        pass


class MultiModalModel(AIModel):
    """多模态模型接口。"""
    
    @abstractmethod
    async def process_image_and_text(self, image_data: bytes, text_prompt: str, **kwargs) -> str:
        """处理图像和文本。
        
        Args:
            image_data: 图像数据。
            text_prompt: 文本提示。
            **kwargs: 额外的参数。
            
        Returns:
            处理结果。
        """
        pass
