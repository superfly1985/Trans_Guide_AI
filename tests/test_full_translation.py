# -*- coding: utf-8 -*-
"""
测试完整翻译流程：TM + 术语库 + LLM
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_manager import ConfigManager
from modules.llm_client import create_llm_client
from modules.file_parser import parse_word_file
from modules.term_db import TermDatabase
from modules.tm_db import TMDatabase
from modules.translator import TRANSLATION_PROMPT


def format_terms(terms: dict) -> str:
    """格式化术语列表"""
    if not terms:
        return "无"
    lines = [f"  - {k} -> {v}" for k, v in terms.items()]
    return "\n".join(lines)


def format_tm_examples(examples: list) -> str:
    """格式化TM示例"""
    if not examples:
        return "无"
    lines = []
    for i, ex in enumerate(examples, 1):
        score = ex.get("similarity", 0)
        original = ex.get("original", "")
        translation = ex.get("translation", "")
        lines.append(f"  {i}. 原文: {original}")
        lines.append(f"     译文: {translation}（匹配度: {score:.1%}）")
    return "\n".join(lines)


def extract_think_content(text: str) -> tuple:
    """提取思考和翻译内容"""
    # 移除 <think> 标签及其内容
    think_pattern = r'<think>.*?</think>'
    think_match = re.search(think_pattern, text, re.DOTALL)
    think_content = think_match.group(0) if think_match else ""
    
    # 移除 think 标签获取实际翻译
    translation = re.sub(think_pattern, '', text, flags=re.DOTALL).strip()
    
    return think_content, translation


def translate_with_llm(client, text: str, terms: dict, tm_examples: list) -> dict:
    """使用LLM翻译文本"""
    
    # 构建提示词
    prompt = TRANSLATION_PROMPT.format(
        text=text,
        terms=format_terms(terms),
        tm_examples=format_tm_examples(tm_examples)
    )
    
    # 调用LLM
    response = client.generate(prompt)
    
    # 提取思考内容和翻译
    think_content, translation = extract_think_content(response)
    
    return {
        "original": text,
        "translation": translation,
        "think": think_content,
        "terms_used": terms,
        "tm_references": tm_examples
    }


def test_full_translation():
    """测试完整翻译流程"""
    
    print("="*70)
    print("测试完整翻译流程 (TM + 术语库 + LLM)")
    print("="*70)
    
    # 1. 加载配置和初始化客户端
    print("\n1. 初始化LLM客户端...")
    config = ConfigManager().get_all()
    llm_config = config.get("llm", {})
    api_config = config.get("api", {})
    
    full_config = {
        **llm_config,
        "base_url": api_config.get("base_url"),
        "api_key": api_config.get("api_key"),
        "model_name": api_config.get("model_name")
    }
    
    client = create_llm_client(full_config)
    print("   ✓ LLM客户端初始化成功")
    
    # 2. 初始化数据库
    print("\n2. 初始化数据库...")
    db_path = "./data/trans_guide.db"
    term_db = TermDatabase(db_path)
    tm_db = TMDatabase(db_path)
    print("   ✓ 数据库初始化成功")
    
    # 3. 加载术语库
    print("\n3. 加载术语库...")
    all_terms = term_db.get_all_terms()
    print(f"   ✓ 术语库: {len(all_terms)} 条")
    for en, zh in list(all_terms.items())[:3]:
        print(f"      - {en} -> {zh}")
    
    # 4. 解析新文件
    print("\n4. 解析Word文件...")
    test_dir = os.path.dirname(os.path.abspath(__file__))
    new_docx = os.path.join(test_dir, "test_doc", "E3122000_02.04.2026新文件.docx")
    texts, info = parse_word_file(new_docx)
    print(f"   ✓ 解析完成: {len(texts)} 个文本块")
    
    # 5. 翻译示例文本
    print("\n5. 翻译示例文本...")
    
    # 选择几个有代表性的文本进行翻译
    test_texts = [
        "Series release and re-release of processes",
        "This work instruction regulates the procedure for series release and re-release of processes.",
        "Applicable for all projects of Kromberg & Schubert Automotive GmbH & Co. KG."
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n   [{i}] 原文: {text}")
        
        # 查找匹配的术语
        matched_terms = {}
        for en, zh in all_terms.items():
            if en.lower() in text.lower():
                matched_terms[en] = zh
        
        if matched_terms:
            print(f"       匹配术语: {matched_terms}")
        
        # 尝试TM匹配
        tm_matches = tm_db.search_similar(text, top_k=1)
        if tm_matches and tm_matches[0].get("similarity", 0) > 0.85:
            print(f"       TM匹配: {tm_matches[0]['translation'][:50]}...")
            print(f"       翻译来源: TM (相似度: {tm_matches[0]['similarity']:.2f})")
        else:
            # 使用LLM翻译
            print(f"       正在使用LLM翻译...")
            result = translate_with_llm(client, text, matched_terms, tm_matches)
            translation = result["translation"]
            # 只显示翻译的第一行
            first_line = translation.split('\n')[0][:60]
            print(f"       译文: {first_line}...")
            print(f"       翻译来源: LLM")
    
    # 6. 总结
    print("\n" + "="*70)
    print("翻译流程测试完成")
    print("="*70)
    print(f"术语库: {len(all_terms)} 条")
    print(f"记忆库: 已导入历史翻译")
    print(f"LLM: {api_config.get('model_name')} ✓")


if __name__ == "__main__":
    test_full_translation()
