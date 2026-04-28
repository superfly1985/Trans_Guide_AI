# -*- coding: utf-8 -*-
"""
测试真实 DOC 文件的完整导入流程
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import parse_file
from modules.bilingual_detector import detect_bilingual_pairs


def test_doc_import():
    """测试 DOC 文件导入流程"""
    
    test_file = r"d:\01.AwesomeProject\52.Trans_Guide_AI\tests\test_doc\3122059历史翻译.DOC"
    
    print("=" * 60)
    print("1. 测试文件解析")
    print("=" * 60)
    
    if not os.path.exists(test_file):
        print(f"❌ 文件不存在: {test_file}")
        return
    
    print(f"文件: {test_file}")
    print(f"文件大小: {os.path.getsize(test_file)} bytes")
    
    try:
        # 解析文件
        blocks, format_info = parse_file(test_file)
        print(f"\n✅ 解析成功!")
        print(f"格式信息: {format_info}")
        print(f"文本块数: {len(blocks)}")
        
        # 显示前10个文本块
        print("\n前10个文本块:")
        for block in blocks[:10]:
            text = block['text'][:80].replace('\n', ' ')
            print(f"  [{block['index']:3d}] {text}...")
        
    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("2. 测试双语对检测")
    print("=" * 60)
    
    try:
        # 检测双语对
        pairs, analysis = detect_bilingual_pairs(blocks)
        
        print(f"\n文档分析:")
        print(f"  总块数: {analysis['structure']['total_blocks']}")
        print(f"  英文块: {analysis['structure']['en_blocks']}")
        print(f"  中文块: {analysis['structure']['zh_blocks']}")
        print(f"  混合块: {analysis['structure']['mixed_blocks']}")
        print(f"  表格块: {analysis['structure']['table_blocks']}")
        print(f"  可能是双语: {analysis['structure']['likely_bilingual']}")
        
        print(f"\n检测方法: {analysis['methods_used']}")
        print(f"检测到 {len(pairs)} 对双语内容")
        
        # 显示前20对
        print("\n前20对双语内容:")
        for pair in pairs[:20]:
            source = pair['source'][:50] + "..." if len(pair['source']) > 50 else pair['source']
            target = pair['target'][:50] + "..." if len(pair['target']) > 50 else pair['target']
            print(f"\n  [{pair['index']:3d}] [{pair['method']}] 置信度:{pair['confidence']:.2f}")
            print(f"       EN: {source}")
            print(f"       ZH: {target}")
        
        if len(pairs) == 0:
            print("\n⚠️ 未检测到双语对，显示所有文本块供分析:")
            for block in blocks[:20]:
                text = block['text'][:100].replace('\n', ' ')
                print(f"  [{block['index']:3d}] {text}...")
        
    except Exception as e:
        print(f"\n❌ 检测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_doc_import()
