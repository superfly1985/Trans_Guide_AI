# -*- coding: utf-8 -*-
"""
LLM客户端模块
支持本地模型和云端API
"""

import os
from typing import Dict, Optional, Generator
from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """LLM客户端基类"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式生成文本"""
        pass


class LocalLLMClient(BaseLLMClient):
    """本地LLM客户端"""
    
    def __init__(
        self,
        model_path: str,
        context_length: int = 4096,
        temperature: float = 0.3,
        gpu_layers: int = 0,
        max_tokens: int = 2048
    ):
        """
        初始化本地LLM客户端
        
        Args:
            model_path: 模型文件路径
            context_length: 上下文长度
            temperature: 温度参数
            gpu_layers: GPU层数
            max_tokens: 最大生成token数
        """
        self.model_path = model_path
        self.context_length = context_length
        self.temperature = temperature
        self.gpu_layers = gpu_layers
        self.max_tokens = max_tokens
        self._llm = None
        
        self._load_model()
    
    def _load_model(self):
        """加载本地模型"""
        try:
            from llama_cpp import Llama
            
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
            
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.context_length,
                n_gpu_layers=self.gpu_layers,
                verbose=False
            )
        except ImportError:
            raise ImportError("请安装 llama-cpp-python: pip install llama-cpp-python")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本
        """
        if not self._llm:
            raise RuntimeError("模型未加载")
        
        response = self._llm(
            prompt,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            stop=kwargs.get("stop", None)
        )
        
        return response["choices"][0]["text"].strip()
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            
        Yields:
            生成的文本片段
        """
        if not self._llm:
            raise RuntimeError("模型未加载")
        
        stream = self._llm(
            prompt,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            stop=kwargs.get("stop", None),
            stream=True
        )
        
        for chunk in stream:
            text = chunk["choices"][0].get("text", "")
            if text:
                yield text


class APILLMClient(BaseLLMClient):
    """云端API LLM客户端"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        group_id: str = ""
    ):
        """
        初始化API LLM客户端
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
            group_id: MiniMax的Group ID
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.group_id = group_id
        self._client = None
        
        self._init_client()
    
    def _init_client(self):
        """初始化API客户端 - 使用环境变量方式（MiniMax官方推荐）"""
        import os
        
        # 设置环境变量
        os.environ["OPENAI_BASE_URL"] = self.base_url
        os.environ["OPENAI_API_KEY"] = self.api_key
        
        try:
            from openai import OpenAI
            self._client = OpenAI()
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本 - 完全按照MiniMax官方示例
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本
        """
        if not self._client:
            raise RuntimeError("API客户端未初始化")
        
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e).lower()
            # 检查是否是额度用尽的错误
            if any(keyword in error_str for keyword in ['quota', 'limit', 'rate limit', 'too many requests', '429', 'insufficient', 'exceeded']):
                raise ConnectionError("API额度已用尽，请等待5小时后重试")
            raise ConnectionError(f"API调用失败: {e}")
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式生成文本 - 完全按照MiniMax官方示例
        
        Args:
            prompt: 提示词
            
        Yields:
            生成的文本片段
        """
        if not self._client:
            raise RuntimeError("API客户端未初始化")
        
        try:
            stream = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=True,
                extra_body={"reasoning_split": True}
            )
            
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            raise ConnectionError(f"API调用失败: {e}")


class LLMClient:
    """统一的LLM客户端，自动从配置文件加载"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化LLM客户端
        
        Args:
            config_path: 配置文件路径
        """
        import json
        import os
        
        # 查找配置文件
        if not os.path.exists(config_path):
            # 尝试在项目根目录查找
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, config_path)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        llm_config = config.get("llm", {})
        api_config = config.get("api", {})  # 读取API配置
        llm_type = llm_config.get("type", "api")
        
        # 创建对应的客户端
        if llm_type == "local":
            self._client = LocalLLMClient(
                model_path=llm_config.get("local_model_path", "./models/model.gguf"),
                context_length=llm_config.get("context_length", 4096),
                temperature=llm_config.get("temperature", 0.3),
                gpu_layers=llm_config.get("gpu_layers", 0),
                max_tokens=llm_config.get("max_tokens", 2048)
            )
        elif llm_type == "api":
            # 从 api_config 读取API相关配置，从 llm_config 读取通用配置
            self._client = APILLMClient(
                base_url=api_config.get("base_url", ""),
                api_key=api_config.get("api_key", ""),
                model_name=api_config.get("model_name", ""),
                temperature=llm_config.get("temperature", 0.3),
                max_tokens=llm_config.get("max_tokens", 2048),
                group_id=api_config.get("group_id", "")
            )
        else:
            raise ValueError(f"不支持的LLM类型: {llm_type}")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        return self._client.generate(prompt, **kwargs)
    
    def generate_stream(self, prompt: str, **kwargs):
        """流式生成文本"""
        return self._client.generate_stream(prompt, **kwargs)
    
    def is_available(self) -> bool:
        """检查LLM是否可用"""
        # 简化检查：只要有配置就认为可用
        # 实际调用时如果失败会抛出异常
        try:
            # 检查底层客户端是否初始化
            if self._client is None:
                return False
            
            # 对于本地模型，检查是否能快速响应
            if hasattr(self._client, 'is_available'):
                return self._client.is_available()
            
            # 默认认为可用，让实际调用时处理错误
            return True
        except Exception as e:
            print(f"LLM 不可用: {e}")
            return False


def create_llm_client(config: Dict) -> BaseLLMClient:
    """
    根据配置创建LLM客户端
    
    Args:
        config: 配置字典
        
    Returns:
        LLM客户端实例
    """
    llm_type = config.get("type", "local")
    
    if llm_type == "local":
        return LocalLLMClient(
            model_path=config.get("local_model_path", "./models/model.gguf"),
            context_length=config.get("context_length", 4096),
            temperature=config.get("temperature", 0.3),
            gpu_layers=config.get("gpu_layers", 0),
            max_tokens=config.get("max_tokens", 2048)
        )
    elif llm_type == "api":
        return APILLMClient(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            model_name=config.get("model_name", ""),
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 2048),
            group_id=config.get("group_id", "")
        )
    else:
        raise ValueError(f"不支持的LLM类型: {llm_type}")
