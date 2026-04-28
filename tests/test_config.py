# -*- coding: utf-8 -*-
"""
配置管理模块测试
"""

import os
import sys
import unittest
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """测试配置管理器"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.config = ConfigManager(self.config_path)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        os.rmdir(self.temp_dir)
    
    def test_get_default_config(self):
        """测试获取默认配置"""
        llm_type = self.config.get("llm.type")
        self.assertEqual(llm_type, "local")
    
    def test_set_and_get_config(self):
        """测试设置和获取配置"""
        self.config.set("llm.type", "api")
        value = self.config.get("llm.type")
        self.assertEqual(value, "api")
    
    def test_nested_config(self):
        """测试嵌套配置"""
        threshold = self.config.get("translation.tm_threshold")
        self.assertEqual(threshold, 0.85)


if __name__ == "__main__":
    unittest.main()
