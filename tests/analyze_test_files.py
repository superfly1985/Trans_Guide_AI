# -*- coding: utf-8 -*-
"""
分析测试文件结构和内容
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import parse_word_file, parse_pdf_file, get_file_type


def analyze_docx(file_path):
    """分析Word文件"""
    print(f"\n{'='*60}")
    print(f"分析Word文件: {file_path}")
    print('='*60)
    
    try:
        texts, info = parse_word_file(file_path)
        
        print(f"\n文档信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        print(f"\n前10个文本块:")
        for i, text_block in enumerate(texts[:10]):
            print(f"\n  [{i}] Type: {text_block.get('type')}")
            print(f"      Text: {text_block.get('text', '')[:100]}...")
            print(f"      Index: {text_block.get('index')}")
            if 'style' in text_block:
                print(f"      Style: {text_block.get('style')}")
        
        return texts, info
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def analyze_pdf(file_path):
    """分析PDF文件"""
    print(f"\n{'='*60}")
    print(f"分析PDF文件: {file_path}")
    print('='*60)
    
    try:
        texts, info = parse_pdf_file(file_path)
        
        print(f"\n文档信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        print(f"\n前10个文本块:")
        for i, text_block in enumerate(texts[:10]):
            print(f"\n  [{i}] Page: {text_block.get('page')}")
            print(f"      Text: {text_block.get('text', '')[:100]}...")
            print(f"      Index: {text_block.get('index')}")
        
        return texts, info
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_doc_dir = os.path.join(test_dir, "test_doc")
    
    # 分析新Word文件
    new_docx = os.path.join(test_doc_dir, "E3122000_02.04.2026新文件.docx")
    if os.path.exists(new_docx):
        analyze_docx(new_docx)
    else:
        print(f"文件不存在: {new_docx}")
    
    # 分析PDF历史翻译文件
    pdf_file = os.path.join(test_doc_dir, "3122059历史翻译.pdf")
    if os.path.exists(pdf_file):
        analyze_pdf(pdf_file)
    else:
        print(f"文件不存在: {pdf_file}")
    
    # 尝试分析旧.DOC文件
    old_doc = os.path.join(test_doc_dir, "3122059历史翻译.DOC")
    if os.path.exists(old_doc):
        print(f"\n{'='*60}")
        print(f"旧.DOC文件: {old_doc}")
        print('='*60)
        print("旧版.DOC格式需要额外的库来解析，建议使用PDF版本")


if __name__ == "__main__":
    main()
