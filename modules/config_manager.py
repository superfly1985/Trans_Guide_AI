# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import json
import os
from typing import Any, Dict, Optional


class ConfigManager:
    """配置管理器"""
    
    DEFAULT_CONFIG = {
        "llm": {
            "type": "local",
            "local_model_path": "./models/qwen2.5-7b.gguf",
            "context_length": 4096,
            "temperature": 0.3,
            "gpu_layers": 0,
            "max_tokens": 2048
        },
        "api": {
            "base_url": "",
            "api_key": "",
            "model_name": ""
        },
        "translation": {
            "tm_threshold": 0.85,
            "tm_top_k": 3,
            "output_mode": "bilingual",
            "batch_size": 10,
            "source_lang": "en",
            "target_lang": "zh"
        },
        "storage": {
            "db_path": "./data/trans_guide.db",
            "chroma_path": "./data/chroma_db",
            "log_path": "./web/logs/web.log"
        },
        "extraction": {
            "term_batch_size": 20,
            "min_term_length": 2
        }
    }
    
    def __init__(self, config_path: str = "./config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                # 合并默认配置，确保新字段存在
                return self._merge_config(self.DEFAULT_CONFIG, config)
            except Exception as e:
                print(f"加载配置文件失败: {e}，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
        else:
            # 创建默认配置文件
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """递归合并配置"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号分隔的路径
        
        Args:
            key: 配置键，如 "llm.type" 或 "storage.db_path"
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置项
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        return self.save_config()
    
    def save_config(self, config: Dict = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置，为None时保存当前配置
            
        Returns:
            是否保存成功
        """
        try:
            config_to_save = config if config else self._config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
