# -*- coding: utf-8 -*-
"""
术语库模块测试
"""

import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.term_db import TermDatabase


class TestTermDatabase(unittest.TestCase):
    """测试术语数据库"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.db = TermDatabase(self.db_path)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_add_and_get_term(self):
        """测试添加和查询术语"""
        self.db.add_term("screw", "螺钉")
        result = self.db.get_term("screw")
        self.assertEqual(result, "螺钉")
    
    def test_update_term(self):
        """测试修改术语"""
        self.db.add_term("screw", "螺丝")
        self.db.update_term("screw", "螺钉")
        result = self.db.get_term("screw")
        self.assertEqual(result, "螺钉")
    
    def test_delete_term(self):
        """测试删除术语"""
        self.db.add_term("screw", "螺钉")
        self.db.delete_term("screw")
        result = self.db.get_term("screw")
        self.assertIsNone(result)
    
    def test_search_terms_in_text(self):
        """测试在文本中搜索术语"""
        self.db.add_term("torque wrench", "扭力扳手")
        self.db.add_term("screw", "螺钉")
        
        text = "Use the torque wrench to tighten the screw."
        matched = self.db.search_terms_in_text(text)
        
        self.assertIn("torque wrench", matched)
        self.assertIn("screw", matched)
        self.assertEqual(matched["torque wrench"], "扭力扳手")


if __name__ == "__main__":
    unittest.main()
