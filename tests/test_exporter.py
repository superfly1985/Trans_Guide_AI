# -*- coding: utf-8 -*-
"""测试文件导出器"""

import sys
sys.path.insert(0, 'd:\\01.AwesomeProject\\52.Trans_Guide_AI')

from modules import file_exporter

print("="*50)
print("测试 Excel 导出:")
print("="*50)

# 测试 Excel 导出
translations = {
    ('Sheet1', 0, 0): '你好世界',
    ('Sheet1', 0, 1): '测试文档',
    ('Sheet1', 1, 0): '这是用于翻译的示例文本',
    ('Sheet1', 1, 1): '公式结果'
}

success = file_exporter.export_excel_simple(
    'tests/test_excel.xlsx',
    translations,
    'tests/test_excel_translated.xlsx',
    mode='bilingual'
)
print(f'Excel 导出: {"成功" if success else "失败"}')

print("\n" + "="*50)
print("测试 PPT 导出:")
print("="*50)

# 测试 PPT 导出
ppt_translations = {
    0: '欢迎演示',
    1: '这是用于翻译测试的示例文本。',
    2: '第二张幻灯片',
    3: '这里还有更多需要翻译的内容。'
}

success = file_exporter.export_pptx(
    'tests/test_pptx.pptx',
    ppt_translations,
    'tests/test_pptx_translated.pptx',
    mode='bilingual'
)
print(f'PPT 导出: {"成功" if success else "失败"}')

print("\n所有导出测试完成!")
print("输出文件:")
print("  - tests/test_excel_translated.xlsx")
print("  - tests/test_pptx_translated.pptx")
