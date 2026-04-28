# -*- coding: utf-8 -*-
"""
测试新文件翻译流程
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import parse_word_file
from modules.term_db import TermDatabase
from modules.tm_db import TMDatabase


def test_translation_flow():
    """测试完整翻译流程"""
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    new_docx = os.path.join(test_dir, "test_doc", "E3122000_02.04.2026新文件.docx")
    db_path = "./data/trans_guide.db"
    
    print("="*60)
    print("测试新文件翻译流程")
    print("="*60)
    
    # 1. 解析新文件
    print("\n1. 解析Word文件...")
    texts, info = parse_word_file(new_docx)
    print(f"   解析完成: {len(texts)} 个文本块")
    
    # 2. 初始化数据库
    print("\n2. 初始化数据库...")
    term_db = TermDatabase(db_path)
    tm_db = TMDatabase(db_path)
    
    # 3. 检查术语库和记忆库
    print("\n3. 检查术语库和记忆库...")
    all_terms_dict = term_db.get_all_terms()
    print(f"   术语库: {len(all_terms_dict)} 条")
    for en, zh in list(all_terms_dict.items())[:5]:
        print(f"      - {en} -> {zh}")
    
    # 4. 测试翻译
    print("\n4. 测试翻译...")
    
    # 翻译前5个文本块
    print("\n   翻译前5个文本块:")
    for i, text_block in enumerate(texts[:5]):
        original = text_block.get('text', '').strip()
        if not original or len(original) < 5:
            continue
            
        print(f"\n   [{i}] 原文: {original[:80]}...")
        
        # 检查是否是英文
        import re
        english_chars = len(re.findall(r'[a-zA-Z]', original))
        if english_chars < 5:
            print(f"       跳过 (非英文内容)")
            continue
        
        # 尝试从记忆库匹配
        matches = tm_db.search_similar(original, top_k=1)
        if matches:
            print(f"       TM匹配: {matches[0]['target'][:60]}... (相似度: {matches[0]['similarity']:.2f})")
        else:
            print(f"       TM匹配: 无")
        
        # 使用LLM翻译 (这里只是模拟)
        print(f"       LLM翻译: [将使用LLM翻译]")
    
    # 5. 统计信息
    print("\n" + "="*60)
    print("翻译流程测试完成")
    print("="*60)
    print(f"文档信息:")
    print(f"  - 段落数: {info.get('paragraph_count', 0)}")
    print(f"  - 表格数: {info.get('table_count', 0)}")
    print(f"  - 文本块数: {len(texts)}")
    print(f"\n知识库信息:")
    print(f"  - 术语库: {len(all_terms_dict)} 条")
    # 查询记忆库数量
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM translation_memory")
    tm_count = cursor.fetchone()[0]
    conn.close()
    print(f"  - 记忆库: {tm_count} 条")


def test_term_matching():
    """测试术语匹配功能"""
    
    print("\n" + "="*60)
    print("测试术语匹配")
    print("="*60)
    
    db_path = "./data/trans_guide.db"
    term_db = TermDatabase(db_path)
    
    test_sentences = [
        "This work instruction regulates the procedure for series release.",
        "Work Instruction for process management",
        "Series release and re-release of processes"
    ]
    
    for sentence in test_sentences:
        print(f"\n原文: {sentence}")
        
        # 查找匹配的术语
        terms_dict = term_db.get_all_terms()
        matched = []
        for en, zh in terms_dict.items():
            if en.lower() in sentence.lower():
                matched.append((en, zh))
        
        if matched:
            print(f"匹配术语:")
            for en, zh in matched:
                print(f"  - {en} -> {zh}")
        else:
            print(f"匹配术语: 无")


if __name__ == "__main__":
    test_translation_flow()
    test_term_matching()
