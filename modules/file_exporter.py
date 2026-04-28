# -*- coding: utf-8 -*-
"""
文件导出模块
将译文写回Word/Excel文件
"""

import os
from typing import List, Tuple, Dict


def export_word(
    original_path: str,
    translations: List[Tuple[int, str]],
    output_path: str,
    mode: str = "bilingual"
) -> bool:
    """
    导出翻译后的Word文件
    
    Args:
        original_path: 原文件路径
        translations: 翻译结果列表 [(位置索引, 译文), ...]
        位置索引对应 parse_word_file 返回的 index 字段
        output_path: 输出路径
        mode: "bilingual"（双语）| "target_only"（仅译文）
        
    Returns:
        是否成功
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")
    
    if not os.path.exists(original_path):
        raise FileNotFoundError(f"原文件不存在: {original_path}")
    
    try:
        # 打开原文档
        doc = Document(original_path)
        
        # 构建翻译映射
        trans_map = {idx: text for idx, text in translations}
        
        # 处理段落
        para_idx = 0
        for para in doc.paragraphs:
            if para.text.strip() and para_idx in trans_map:
                translation = trans_map[para_idx]
                
                if mode == "bilingual":
                    # 双语模式：原文 + 换行 + 译文
                    # 保留原文，在后面添加译文
                    para.add_run("\n")
                    run = para.add_run(translation)
                    # 设置译文格式（红色、斜体以示区分）
                    run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
                    run.italic = True
                else:
                    # 仅译文模式：替换原文
                    para.clear()
                    para.add_run(translation)
                
                para_idx += 1
        
        # 处理表格
        table_idx_offset = para_idx
        for table_idx, table in enumerate(doc.tables):
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    current_idx = table_idx_offset + table_idx * 1000 + row_idx * 100 + cell_idx
                    if current_idx in trans_map:
                        translation = trans_map[current_idx]
                        
                        if mode == "bilingual":
                            cell.paragraphs[0].add_run("\n")
                            run = cell.paragraphs[0].add_run(translation)
                            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
                            run.italic = True
                        else:
                            cell.paragraphs[0].clear()
                            cell.paragraphs[0].add_run(translation)
        
        # 保存文档
        doc.save(output_path)
        return True
        
    except Exception as e:
        print(f"导出Word失败: {e}")
        return False


def export_word_simple(
    original_path: str,
    translation_dict: Dict[int, str],
    output_path: str,
    mode: str = "bilingual"
) -> bool:
    """
    简化版Word导出（使用字典映射）
    
    Args:
        original_path: 原文件路径
        translation_dict: 翻译字典 {index: 译文}
        output_path: 输出路径
        mode: "bilingual" | "target_only"
        
    Returns:
        是否成功
    """
    try:
        from docx import Document
        from docx.shared import RGBColor
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")
    
    if not os.path.exists(original_path):
        raise FileNotFoundError(f"原文件不存在: {original_path}")
    
    try:
        doc = Document(original_path)
        
        # 收集所有文本块及其位置
        text_blocks = []
        index = 0
        
        # 段落
        for para in doc.paragraphs:
            if para.text.strip():
                text_blocks.append(("paragraph", para, index))
                index += 1
        
        # 表格
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_blocks.append(("cell", cell, index))
                        index += 1
        
        # 应用翻译
        for block_type, block, idx in text_blocks:
            if idx in translation_dict:
                translation = translation_dict[idx]
                
                if block_type == "paragraph":
                    para = block
                    if mode == "bilingual":
                        para.add_run("\n")
                        run = para.add_run(translation)
                        run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
                        run.italic = True
                    else:
                        para.clear()
                        para.add_run(translation)
                
                elif block_type == "cell":
                    cell = block
                    if mode == "bilingual":
                        cell.paragraphs[0].add_run("\n")
                        run = cell.paragraphs[0].add_run(translation)
                        run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
                        run.italic = True
                    else:
                        cell.paragraphs[0].clear()
                        cell.paragraphs[0].add_run(translation)
        
        doc.save(output_path)
        return True
        
    except Exception as e:
        print(f"导出Word失败: {e}")
        return False


def export_excel(
    original_path: str,
    translations: List[Tuple[str, int, int, str]],
    output_path: str,
    mode: str = "bilingual"
) -> bool:
    """
    导出翻译后的Excel文件
    
    Args:
        original_path: 原文件路径
        translations: 翻译结果列表 [(sheet名, 行, 列, 译文), ...]
        行、列对应 parse_excel_file 返回的 row、col 字段
        output_path: 输出路径
        mode: "bilingual" | "target_only"
        
    Returns:
        是否成功
    """
    try:
        from openpyxl import load_workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        raise ImportError("请安装 openpyxl: pip install openpyxl")
    
    if not os.path.exists(original_path):
        raise FileNotFoundError(f"原文件不存在: {original_path}")
    
    try:
        # 打开原工作簿
        wb = load_workbook(original_path)
        
        # 构建翻译映射 {(sheet, row, col): 译文}
        trans_map = {}
        for sheet_name, row, col, translation in translations:
            trans_map[(sheet_name, row, col)] = translation
        
        # 应用翻译
        for sheet_name, row, col, translation in translations:
            if sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                cell = ws.cell(row=row + 1, column=col + 1)  # openpyxl使用1-based索引
                
                if mode == "bilingual":
                    # 双语模式：原文 + 换行 + 译文
                    original_value = str(cell.value) if cell.value else ""
                    cell.value = f"{original_value}\n{translation}"
                    # 设置译文为红色
                    cell.font = Font(color="FF0000", italic=True)
                else:
                    # 仅译文模式：替换原文
                    cell.value = translation
        
        # 保存工作簿
        wb.save(output_path)
        return True
        
    except Exception as e:
        print(f"导出Excel失败: {e}")
        return False


def export_excel_simple(
    original_path: str,
    translation_dict: Dict[Tuple[str, int, int], str],
    output_path: str,
    mode: str = "bilingual"
) -> bool:
    """
    简化版Excel导出（使用字典映射）
    
    Args:
        original_path: 原文件路径
        translation_dict: 翻译字典 {(sheet, row, col): 译文}
        output_path: 输出路径
        mode: "bilingual" | "target_only"
        
    Returns:
        是否成功
    """
    try:
        from openpyxl import load_workbook
        from openpyxl.styles import Font
    except ImportError:
        raise ImportError("请安装 openpyxl: pip install openpyxl")
    
    if not os.path.exists(original_path):
        raise FileNotFoundError(f"原文件不存在: {original_path}")
    
    try:
        wb = load_workbook(original_path)
        
        for (sheet_name, row, col), translation in translation_dict.items():
            if sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                cell = ws.cell(row=row + 1, column=col + 1)
                
                if mode == "bilingual":
                    original_value = str(cell.value) if cell.value else ""
                    cell.value = f"{original_value}\n{translation}"
                    cell.font = Font(color="FF0000", italic=True)
                else:
                    cell.value = translation
        
        wb.save(output_path)
        return True
        
    except Exception as e:
        print(f"导出Excel失败: {e}")
        return False


def export_txt(
    translations: List[Dict],
    output_path: str
) -> bool:
    """
    导出翻译后的TXT文件
    
    Args:
        translations: 翻译结果列表
        output_path: 输出路径
        
    Returns:
        是否成功
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for item in translations:
                f.write(item.get("translation", "") + "\n")
        return True
    except Exception as e:
        print(f"导出TXT失败: {e}")
        return False


def export_csv(
    translations: List[Dict],
    output_path: str
) -> bool:
    """
    导出翻译后的CSV文件
    
    Args:
        translations: 翻译结果列表
        output_path: 输出路径
        
    Returns:
        是否成功
    """
    import csv
    
    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for item in translations:
                writer.writerow([
                    item.get("original", ""),
                    item.get("translation", "")
                ])
        return True
    except Exception as e:
        print(f"导出CSV失败: {e}")
        return False


def get_output_path(input_path: str, suffix: str = "_中文") -> str:
    """
    生成输出文件路径
    
    Args:
        input_path: 输入文件路径
        suffix: 文件名后缀
        
    Returns:
        输出文件路径
    """
    dir_name = os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    name, ext = os.path.splitext(base_name)
    output_name = f"{name}{suffix}{ext}"
    return os.path.join(dir_name, output_name)
