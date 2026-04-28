# -*- coding: utf-8 -*-
"""
数据导入模块测试
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_importer import (
    clean_text,
    is_valid_text,
    align_bilingual_data,
    deduplicate_pairs,
    filter_pairs
)


class TestDataImporter(unittest.TestCase):
    """测试数据导入功能"""
    
    def test_clean_text(self):
        """测试文本清洗"""
        text = "  Hello   World  \n\n"
        result = clean_text(text)
        self.assertEqual(result, "Hello World")
    
    def test_is_valid_text(self):
        """测试文本有效性检查"""
        self.assertTrue(is_valid_text("Hello World"))
        self.assertFalse(is_valid_text(""))
        self.assertFalse(is_valid_text("ab"))  # 太短
    
    def test_align_bilingual_data_line(self):
        """测试逐行对齐"""
        original = ["Hello", "World"]
        translation = ["你好", "世界"]
        pairs = align_bilingual_data(original, translation, "line")
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0], ("Hello", "你好"))
    
    def test_deduplicate_pairs(self):
        """测试去重"""
        pairs = [
            ("Hello", "你好"),
            ("Hello", "您好"),  # 重复，应保留后面的
            ("World", "世界")
        ]
        result = deduplicate_pairs(pairs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["Hello"], "您好")
    
    def test_filter_pairs(self):
        """测试过滤句段对"""
        pairs = [
            ("Hi", "嗨"),  # 太短，应被过滤
            ("Hello World", "你好世界"),
            ("a" * 6000, "b" * 6000)  # 太长，应被过滤
        ]
        result = filter_pairs(pairs, min_length=3, max_length=5000)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
