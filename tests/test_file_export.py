# -*- coding: utf-8 -*-
"""
测试文件导出功能
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_parser import parse_word_file
from modules.file_exporter import export_word_simple, get_output_path


def test_word_export():
    """测试Word文件导出"""
    print("="*60)
    print("测试Word文件导出")
    print("="*60)
    
    # 测试文件路径
    test_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(test_dir, "test_doc", "E3122000_02.04.2026新文件.docx")
    
    if not os.path.exists(input_file):
        print(f"✗ 测试文件不存在: {input_file}")
        return False
    
    print(f"\n1. 解析原文件...")
    texts, info = parse_word_file(input_file)
    print(f"   ✓ 解析完成: {len(texts)} 个文本块")
    
    print(f"\n2. 准备翻译数据...")
    # 模拟翻译结果（实际使用时来自LLM翻译）
    translations = {}
    for i, block in enumerate(texts[:10]):  # 只翻译前10个文本块作为测试
        original = block.get('text', '').strip()
        if original and len(original) > 5:
            # 模拟翻译：简单地在原文后加"[中文]"
            translations[i] = f"[中文翻译]{original[:30]}..."
    
    print(f"   ✓ 准备 {len(translations)} 条翻译")
    
    print(f"\n3. 导出双语文件...")
    output_file = os.path.join(test_dir, "test_output", "E3122000_双语测试.docx")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    success = export_word_simple(
        original_path=input_file,
        translation_dict=translations,
        output_path=output_file,
        mode="bilingual"
    )
    
    if success:
        print(f"   ✓ 导出成功: {output_file}")
    else:
        print(f"   ✗ 导出失败")
        return False
    
    print(f"\n4. 导出仅译文文件...")
    output_file2 = os.path.join(test_dir, "test_output", "E3122000_译文测试.docx")
    
    success = export_word_simple(
        original_path=input_file,
        translation_dict=translations,
        output_path=output_file2,
        mode="target_only"
    )
    
    if success:
        print(f"   ✓ 导出成功: {output_file2}")
    else:
        print(f"   ✗ 导出失败")
        return False
    
    print(f"\n5. 测试自动生成输出路径...")
    auto_path = get_output_path(input_file, "_已翻译")
    print(f"   输入: {input_file}")
    print(f"   输出: {auto_path}")
    
    return True


def test_export_with_real_translation():
    """使用真实翻译结果测试导出"""
    print("\n" + "="*60)
    print("使用真实翻译结果测试导出")
    print("="*60)
    
    from modules.config_manager import ConfigManager
    from modules.llm_client import create_llm_client
    from modules.term_db import TermDatabase
    from modules.translator import TRANSLATION_PROMPT
    import re
    
    # 加载配置
    config = ConfigManager().get_all()
    llm_config = config.get("llm", {})
    api_config = config.get("api", {})
    
    full_config = {
        **llm_config,
        "base_url": api_config.get("base_url"),
        "api_key": api_config.get("api_key"),
        "model_name": api_config.get("model_name")
    }
    
    # 初始化客户端
    client = create_llm_client(full_config)
    term_db = TermDatabase("./data/trans_guide.db")
    all_terms = term_db.get_all_terms()
    
    # 解析文件
    test_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(test_dir, "test_doc", "E3122000_02.04.2026新文件.docx")
    texts, info = parse_word_file(input_file)
    
    print(f"\n1. 翻译前5个文本块...")
    translations = {}
    
    for i, block in enumerate(texts[:5]):
        original = block.get('text', '').strip()
        if not original or len(original) < 5:
            continue
        
        # 检查是否是英文
        english_chars = len(re.findall(r'[a-zA-Z]', original))
        if english_chars < 5:
            continue
        
        print(f"\n   [{i}] 原文: {original[:50]}...")
        
        # 查找匹配的术语
        matched_terms = {}
        for en, zh in all_terms.items():
            if en.lower() in original.lower():
                matched_terms[en] = zh
        
        # 构建提示词
        terms_str = "\n".join([f"  - {k} -> {v}" for k, v in matched_terms.items()]) if matched_terms else "无"
        prompt = TRANSLATION_PROMPT.format(
            text=original,
            terms=terms_str,
            tm_examples="无"
        )
        
        # 调用LLM翻译
        response = client.generate(prompt)
        
        # 提取翻译（移除think标签）
        translation = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        
        print(f"       译文: {translation[:50]}...")
        translations[i] = translation
    
    print(f"\n2. 导出翻译结果...")
    output_file = os.path.join(test_dir, "test_output", "E3122000_真实翻译.docx")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    success = export_word_simple(
        original_path=input_file,
        translation_dict=translations,
        output_path=output_file,
        mode="bilingual"
    )
    
    if success:
        print(f"   ✓ 导出成功: {output_file}")
        print(f"\n   共翻译 {len(translations)} 个文本块")
        return True
    else:
        print(f"   ✗ 导出失败")
        return False


if __name__ == "__main__":
    success1 = test_word_export()
    success2 = test_export_with_real_translation()
    
    print("\n" + "="*60)
    if success1 and success2:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")
    print("="*60)
