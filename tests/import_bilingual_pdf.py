# -*- coding: utf-8 -*-
"""
从PDF历史翻译文件中提取双语对并导入到TM/TB
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import parse_pdf_file
from modules.term_db import TermDatabase
from modules.tm_db import TMDatabase


def extract_bilingual_pairs(texts):
    """
    从PDF文本块中提取双语对
    
    策略：
    1. 识别英文文本块（包含英文字符）
    2. 查找紧跟其后的中文文本块
    3. 形成双语对
    
    Args:
        texts: 文本块列表
        
    Returns:
        双语对列表 [(英文, 中文), ...]
    """
    pairs = []
    i = 0
    
    while i < len(texts) - 1:
        current_text = texts[i].get('text', '').strip()
        next_text = texts[i + 1].get('text', '').strip()
        
        # 跳过空文本和页眉页脚
        if not current_text or len(current_text) < 3:
            i += 1
            continue
        
        # 判断当前文本是否为英文
        # 英文文本特征：包含英文字母，中文字符比例低
        english_chars = len(re.findall(r'[a-zA-Z]', current_text))
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', current_text))
        
        is_english = english_chars > 5 and chinese_chars < len(current_text) * 0.3
        
        if is_english:
            # 检查下一个文本是否为中文
            next_chinese = len(re.findall(r'[\u4e00-\u9fff]', next_text))
            next_english = len(re.findall(r'[a-zA-Z]', next_text))
            
            is_chinese = next_chinese > 3 and next_english < len(next_text) * 0.3
            
            if is_chinese:
                # 清洗文本
                english = clean_text(current_text)
                chinese = clean_text(next_text)
                
                # 过滤掉太短的
                if len(english) > 5 and len(chinese) > 3:
                    pairs.append((english, chinese))
                i += 2  # 跳过已匹配的下一个
                continue
        
        i += 1
    
    return pairs


def clean_text(text):
    """清洗文本"""
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 去除页码标记
    text = re.sub(r'Page \d+ of \d+', '', text)
    # 去除表单编号等
    text = re.sub(r'^\d+\.\d+\.\d+\.\d+', '', text)
    return text.strip()


def extract_terms_from_pairs(pairs, min_length=3):
    """
    从双语对中提取可能的术语
    
    简单策略：
    1. 提取英文中的大写单词或词组
    2. 对应中文翻译中的名词
    
    Args:
        pairs: 双语对列表
        min_length: 最小术语长度
        
    Returns:
        术语字典 {英文: 中文}
    """
    terms = {}
    
    for english, chinese in pairs:
        # 提取可能的专业术语（全大写或首字母大写的词组）
        # 匹配模式：连续的大写单词或首字母大写的词组
        potential_terms = re.findall(r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)+\b', english)
        
        for term in potential_terms:
            if len(term) >= min_length and term not in terms:
                # 尝试从中文中提取对应翻译
                # 这里使用简单策略：取中文的前几个词作为对应翻译
                chinese_words = chinese.split()
                if chinese_words:
                    # 如果术语较短，取中文前2-4个字
                    if len(term) < 10:
                        chinese_term = chinese[:min(8, len(chinese))]
                    else:
                        chinese_term = chinese[:min(15, len(chinese))]
                    terms[term] = chinese_term
    
    return terms


def import_pdf_to_database(pdf_path, db_path="./data/trans_guide.db"):
    """
    导入PDF历史翻译文件到数据库
    
    Args:
        pdf_path: PDF文件路径
        db_path: 数据库路径
        
    Returns:
        导入统计信息
    """
    print(f"正在解析PDF文件: {pdf_path}")
    
    # 解析PDF
    texts, info = parse_pdf_file(pdf_path)
    print(f"共解析 {len(texts)} 个文本块，{info['page_count']} 页")
    
    # 提取双语对
    print("\n正在提取双语对...")
    pairs = extract_bilingual_pairs(texts)
    print(f"提取到 {len(pairs)} 个双语对")
    
    # 显示前5个双语对
    print("\n前5个双语对示例:")
    for i, (en, zh) in enumerate(pairs[:5], 1):
        print(f"  {i}. EN: {en[:60]}...")
        print(f"     ZH: {zh[:60]}...")
    
    # 提取术语
    print("\n正在提取术语...")
    terms = extract_terms_from_pairs(pairs)
    print(f"提取到 {len(terms)} 个潜在术语")
    
    # 显示前10个术语
    print("\n前10个术语示例:")
    for i, (en, zh) in enumerate(list(terms.items())[:10], 1):
        print(f"  {i}. {en} -> {zh}")
    
    # 初始化数据库
    print("\n正在导入数据库...")
    term_db = TermDatabase(db_path)
    tm_db = TMDatabase(db_path)
    
    # 导入术语
    term_count = 0
    for en, zh in terms.items():
        if term_db.add_term(en, zh, pdf_path):
            term_count += 1
    
    # 导入记忆库
    tm_count = 0
    for en, zh in pairs:
        if tm_db.add_segment(en, zh, pdf_path):
            tm_count += 1
    
    print(f"\n导入完成:")
    print(f"  - 术语库: {term_count} 条")
    print(f"  - 记忆库: {tm_count} 条")
    
    return {
        "pairs": len(pairs),
        "terms": len(terms),
        "imported_terms": term_count,
        "imported_segments": tm_count
    }


def main():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_file = os.path.join(test_dir, "test_doc", "3122059历史翻译.pdf")
    
    if not os.path.exists(pdf_file):
        print(f"文件不存在: {pdf_file}")
        return
    
    stats = import_pdf_to_database(pdf_file)
    
    print("\n" + "="*60)
    print("导入统计:")
    print(f"  双语对总数: {stats['pairs']}")
    print(f"  术语总数: {stats['terms']}")
    print(f"  成功导入术语: {stats['imported_terms']}")
    print(f"  成功导入句段: {stats['imported_segments']}")


if __name__ == "__main__":
    main()
