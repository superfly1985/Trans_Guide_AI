# -*- coding: utf-8 -*-
"""
测试 DOC 文件解析器
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.doc_parser import parse_doc_file_simple


def test_doc_parser():
    """测试 DOC 解析器"""
    
    # 创建一个简单的测试 DOC 文件
    # 注意：这里创建一个模拟的 OLE 文件结构
    test_file = "./test_sample.doc"
    
    # 检查是否存在测试文件
    if not os.path.exists(test_file):
        print(f"测试文件不存在: {test_file}")
        print("创建模拟 DOC 文件进行测试...")
        
        # 创建一个模拟的 DOC 文件（OLE 格式）
        # OLE 文件头
        ole_header = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        
        # 添加一些模拟数据
        # 包含一些 UTF-16-LE 编码的文本
        text_data = "Hello World\n你好世界\nThis is a test\n这是一个测试".encode('utf-16-le')
        
        with open(test_file, 'wb') as f:
            f.write(ole_header)
            f.write(b'\x00' * 504)  # 填充到 512 字节
            f.write(text_data)
        
        print(f"创建测试文件: {test_file}")
    
    try:
        blocks, info = parse_doc_file_simple(test_file)
        print(f"\n解析成功!")
        print(f"格式信息: {info}")
        print(f"段落数: {len(blocks)}")
        print("\n解析内容:")
        for block in blocks[:10]:
            print(f"  [{block['index']}] {block['text'][:60]}...")
        
        return True
    except Exception as e:
        print(f"\n解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_doc_parser()
