# -*- coding: utf-8 -*-
"""
使用模拟 LLM 测试导入流程
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import file_parser
from modules.bilingual_detector import detect_bilingual_pairs


class MockLLMClient:
    """模拟 LLM 客户端"""
    
    def is_available(self):
        return True
    
    def generate(self, prompt, **kwargs):
        # 模拟返回术语 JSON
        mock_response = """{
    "terms": [
        {"english": "Work Instruction", "chinese": "作业指导书", "category": "文档类型"},
        {"english": "Process Release", "chinese": "过程放行", "category": "流程"},
        {"english": "Quality Assurance", "chinese": "质量保证", "category": "质量"},
        {"english": "Checkpoints", "chinese": "检查点", "category": "质量"},
        {"english": "Series Production", "chinese": "批量生产", "category": "生产"},
        {"english": "Customer Approval", "chinese": "客户认可", "category": "客户"},
        {"english": "Department Manager", "chinese": "部门经理", "category": "管理"}
    ]
}"""
        return mock_response


def test_import_with_mock_llm():
    """测试导入流程"""
    
    test_file = r"d:\01.AwesomeProject\52.Trans_Guide_AI\tests\test_doc\3122059历史翻译.DOC"
    
    print("=" * 60)
    print("测试导入流程（使用模拟 LLM）")
    print("=" * 60)
    
    # 1. 解析文件
    print("\n1. 解析文件...")
    try:
        blocks, format_info = file_parser.parse_file(test_file)
        print(f"✅ 解析成功: {len(blocks)} 个文本块")
    except Exception as e:
        print(f"❌ 文件解析失败: {e}")
        return
    
    # 2. 检测双语对
    print("\n2. 检测双语对...")
    pairs, analysis = detect_bilingual_pairs(blocks, None)
    print(f"✅ 检测到 {len(pairs)} 对双语内容")
    
    # 3. 使用模拟 LLM 提取术语
    print("\n3. 使用 LLM 提取术语...")
    mock_llm = MockLLMClient()
    
    from modules.llm_term_extractor import extract_terms_with_llm
    
    full_text = '\n'.join([block['text'] for block in blocks if len(block['text'].strip()) > 5])
    terms = extract_terms_with_llm(full_text, mock_llm, max_terms=30)
    
    print(f"✅ 提取到 {len(terms)} 个术语:")
    print("-" * 60)
    
    for i, term in enumerate(terms, 1):
        print(f"{i}. {term['english']} -> {term['chinese']}")
        if term.get('category'):
            print(f"   分类: {term['category']}")
    
    # 4. 模拟导入
    print("\n4. 模拟导入术语...")
    imported_count = 0
    for term in terms:
        if term.get('english') and term.get('chinese'):
            print(f"  导入: {term['english']} = {term['chinese']}")
            imported_count += 1
    
    print(f"\n✅ 导入完成: {imported_count} 个术语")


if __name__ == "__main__":
    test_import_with_mock_llm()
