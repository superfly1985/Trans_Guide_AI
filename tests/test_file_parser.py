# -*- coding: utf-8 -*-
"""
文件解析模块测试
"""

import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import (
    parse_txt_file,
    parse_csv_file,
    get_file_type
)


class TestFileParser(unittest.TestCase):
    """测试文件解析功能"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_parse_txt_file(self):
        """测试TXT文件解析"""
        # 创建测试文件
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Hello World\n")
            f.write("Second Line\n")
        
        texts, info = parse_txt_file(test_file)
        
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0]["text"], "Hello World")
        self.assertEqual(texts[1]["text"], "Second Line")
        self.assertEqual(info["encoding"], "utf-8")
    
    def test_parse_csv_file(self):
        """测试CSV文件解析"""
        import csv
        
        # 创建测试文件
        test_file = os.path.join(self.temp_dir, "test.csv")
        with open(test_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Hello", "World"])
            writer.writerow(["Second", "Row"])
        
        texts, info = parse_csv_file(test_file)
        
        self.assertEqual(len(texts), 4)
        self.assertEqual(texts[0]["text"], "Hello")
        self.assertEqual(texts[0]["row"], 0)
        self.assertEqual(texts[0]["col"], 0)
    
    def test_get_file_type(self):
        """测试文件类型识别"""
        self.assertEqual(get_file_type("test.docx"), "word")
        self.assertEqual(get_file_type("test.xlsx"), "excel")
        self.assertEqual(get_file_type("test.pdf"), "pdf")
        self.assertEqual(get_file_type("test.txt"), "txt")
        self.assertEqual(get_file_type("test.csv"), "csv")
        self.assertEqual(get_file_type("test.unknown"), "unknown")


if __name__ == "__main__":
    unittest.main()
