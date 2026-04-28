# -*- coding: utf-8 -*-
"""
测试 LLM 术语提取功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.llm_client import LLMClient
from modules.llm_term_extractor import extract_terms_with_llm, LLMTermExtractor
from modules import file_parser


def test_llm_term_extraction():
    """测试 LLM 术语提取"""
    
    test_file = r"d:\01.AwesomeProject\52.Trans_Guide_AI\tests\test_doc\3122059历史翻译.DOC"
    
    print("=" * 60)
    print("测试 LLM 术语提取")
    print("=" * 60)
    
    # 1. 初始化 LLM 客户端
    print("\n1. 初始化 LLM 客户端...")
    try:
        llm_client = LLMClient()
        print("✅ LLM 客户端初始化成功")
        
        # 检查 LLM 是否可用
        if llm_client.is_available():
            print("✅ LLM 可用")
        else:
            print("❌ LLM 不可用")
            return
    except Exception as e:
        print(f"❌ LLM 客户端初始化失败: {e}")
        return
    
    # 2. 解析文件
    print("\n2. 解析文件...")
    try:
        blocks, format_info = file_parser.parse_file(test_file)
        print(f"✅ 解析成功: {len(blocks)} 个文本块")
    except Exception as e:
        print(f"❌ 文件解析失败: {e}")
        return
    
    # 3. 合并文本
    print("\n3. 提取术语...")
    full_text = '\n'.join([block['text'] for block in blocks if len(block['text'].strip()) > 5])
    print(f"文本长度: {len(full_text)} 字符")
    
    # 4. 使用 LLM 提取术语
    try:
        terms = extract_terms_with_llm(full_text, llm_client, max_terms=30)
        
        print(f"\n✅ 提取到 {len(terms)} 个术语:")
        print("-" * 60)
        
        for i, term in enumerate(terms[:20], 1):
            print(f"{i}. {term['english']}")
            print(f"   {term['chinese']}")
            if term.get('category'):
                print(f"   分类: {term['category']}")
            print()
        
        if len(terms) > 20:
            print(f"... 还有 {len(terms) - 20} 个术语")
            
    except Exception as e:
        print(f"❌ 术语提取失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_llm_term_extraction()
