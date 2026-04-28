# -*- coding: utf-8 -*-
"""
文件解析模块
支持Word、Excel、PDF、TXT、CSV格式
"""

import os
import csv
from typing import List, Dict, Tuple, Optional


def parse_word_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析Word文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 文本块列表，每个元素包含:
            - text: 文本内容
            - type: 类型 (paragraph/table/header/footer)
            - style: 段落样式名
            - index: 在文档中的索引
            - format: 格式信息 (字体、字号、加粗等)
        format_info: 文档整体格式信息
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式错误或损坏
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    try:
        doc = Document(file_path)
    except Exception as e:
        raise ValueError(f"无法解析Word文件: {e}")
    
    texts = []
    index = 0
    
    # 解析段落
    for para_idx, para in enumerate(doc.paragraphs):
        if para.text.strip():
            # 提取格式信息
            format_info = _extract_para_format(para)
            
            texts.append({
                "text": para.text,
                "type": "paragraph",
                "style": para.style.name if para.style else "Normal",
                "index": index,
                "para_index": para_idx,
                "format": format_info
            })
            index += 1
    
    # 解析表格
    for table_idx, table in enumerate(doc.tables):
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                if cell.text.strip():
                    texts.append({
                        "text": cell.text,
                        "type": "table_cell",
                        "table_index": table_idx,
                        "row": row_idx,
                        "col": cell_idx,
                        "index": index,
                        "format": {}
                    })
                    index += 1
    
    # 解析页眉
    for section_idx, section in enumerate(doc.sections):
        if section.header:
            for para in section.header.paragraphs:
                if para.text.strip():
                    texts.append({
                        "text": para.text,
                        "type": "header",
                        "section_index": section_idx,
                        "index": index,
                        "format": {}
                    })
                    index += 1
    
    # 解析页脚
    for section_idx, section in enumerate(doc.sections):
        if section.footer:
            for para in section.footer.paragraphs:
                if para.text.strip():
                    texts.append({
                        "text": para.text,
                        "type": "footer",
                        "section_index": section_idx,
                        "index": index,
                        "format": {}
                    })
                    index += 1
    
    doc_info = {
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "section_count": len(doc.sections),
        "text_block_count": len(texts)
    }
    
    return texts, doc_info


def _extract_para_format(para) -> Dict:
    """
    提取段落格式信息
    
    Args:
        para: docx段落对象
        
    Returns:
        格式信息字典
    """
    format_info = {
        "alignment": str(para.alignment) if para.alignment else None,
        "line_spacing": para.paragraph_format.line_spacing,
        "space_before": para.paragraph_format.space_before,
        "space_after": para.paragraph_format.space_after,
    }
    
    # 提取第一个run的格式（如果有）
    if para.runs:
        run = para.runs[0]
        format_info.update({
            "bold": run.bold,
            "italic": run.italic,
            "underline": run.underline,
            "font_name": run.font.name if run.font else None,
            "font_size": run.font.size.pt if run.font and run.font.size else None,
        })
    
    return format_info


def parse_excel_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析Excel文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 单元格文本列表，每个元素包含:
            - text: 文本内容
            - sheet: 工作表名
            - row: 行号 (0-based)
            - col: 列号 (0-based)
            - index: 在文档中的索引
            - format: 格式信息
        format_info: 工作簿整体格式信息
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError("请安装 openpyxl: pip install openpyxl")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    try:
        wb = load_workbook(file_path, data_only=True)
    except Exception as e:
        raise ValueError(f"无法解析Excel文件: {e}")
    
    texts = []
    index = 0
    total_cells = 0
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        
        for row_idx, row in enumerate(ws.iter_rows()):
            for col_idx, cell in enumerate(row):
                if cell.value is not None:
                    cell_text = str(cell.value).strip()
                    if cell_text:
                        # 提取格式信息
                        format_info = _extract_cell_format(cell)
                        
                        texts.append({
                            "text": cell_text,
                            "sheet": sheet_name,
                            "row": row_idx,
                            "col": col_idx,
                            "index": index,
                            "format": format_info
                        })
                        index += 1
                        total_cells += 1
    
    wb_info = {
        "sheet_count": len(wb.sheetnames),
        "sheet_names": wb.sheetnames,
        "cell_count": total_cells
    }
    
    return texts, wb_info


def _extract_cell_format(cell) -> Dict:
    """
    提取单元格格式信息
    
    Args:
        cell: openpyxl单元格对象
        
    Returns:
        格式信息字典
    """
    format_info = {}
    
    if cell.font:
        format_info.update({
            "font_name": cell.font.name,
            "font_size": cell.font.size,
            "bold": cell.font.bold,
            "italic": cell.font.italic,
            "underline": cell.font.underline,
        })
    
    if cell.fill and cell.fill.fgColor:
        format_info["fill_color"] = cell.fill.fgColor.rgb
    
    if cell.alignment:
        format_info.update({
            "horizontal": cell.alignment.horizontal,
            "vertical": cell.alignment.vertical,
            "wrap_text": cell.alignment.wrap_text,
        })
    
    if cell.border:
        format_info["has_border"] = any([
            cell.border.left.style,
            cell.border.right.style,
            cell.border.top.style,
            cell.border.bottom.style
        ])
    
    return format_info


def parse_pdf_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析PDF文件（仅文本提取）
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 文本块列表，每个元素包含:
            - text: 文本内容
            - page: 页码 (0-based)
            - index: 在文档中的索引
            - bbox: 文本块位置 (x0, y0, x1, y1)
        format_info: 文档页数等信息
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"无法解析PDF文件: {e}")
    
    texts = []
    index = 0
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 提取文本块
        text_blocks = page.get_text("blocks")
        
        for block in text_blocks:
            # block格式: (x0, y0, x1, y1, text, block_no, block_type)
            x0, y0, x1, y1, text, block_no, block_type = block
            
            text = text.strip()
            if text:
                texts.append({
                    "text": text,
                    "page": page_num,
                    "index": index,
                    "bbox": (x0, y0, x1, y1),
                    "block_no": block_no,
                    "block_type": block_type
                })
                index += 1
    
    doc_info = {
        "page_count": len(doc),
        "text_block_count": len(texts)
    }
    
    doc.close()
    return texts, doc_info


def parse_txt_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析TXT文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 文本行列表
        format_info: 文件编码等信息
    """
    texts = []
    encodings = ["utf-8", "gbk", "gb2312", "utf-16"]
    
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                texts.append({
                    "text": line.rstrip("\n\r"),
                    "line_no": i + 1,
                    "type": "line"
                })
            return texts, {"encoding": encoding, "line_count": len(lines)}
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"无法识别文件编码: {file_path}")


def parse_csv_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析CSV文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 单元格文本列表
        format_info: 行列数等信息
    """
    texts = []
    encodings = ["utf-8", "gbk", "gb2312"]
    
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                for row_idx, row in enumerate(reader):
                    for col_idx, cell in enumerate(row):
                        texts.append({
                            "text": cell,
                            "row": row_idx,
                            "col": col_idx,
                            "type": "cell"
                        })
            return texts, {"encoding": encoding, "rows": row_idx + 1}
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"无法识别文件编码: {file_path}")


def parse_doc_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析旧版 .doc 文件
    优先使用内置解析器，失败时尝试外部工具
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 文本块列表
        format_info: 格式信息
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 首先尝试使用内置解析器
    try:
        from .doc_parser import parse_doc_file_simple
        return parse_doc_file_simple(file_path)
    except Exception as e:
        print(f"内置解析器失败: {e}，尝试外部工具...")
    
    texts = []
    
    # 尝试使用 textract
    try:
        import textract
        text = textract.process(file_path).decode('utf-8')
        
        # 按段落分割
        for i, para in enumerate(text.split('\n')):
            para = para.strip()
            if para:
                texts.append({
                    "text": para,
                    "type": "paragraph",
                    "index": i,
                    "format": {}
                })
        
        return texts, {"method": "textract", "paragraph_count": len(texts)}
    except ImportError:
        pass
    
    # 尝试使用 antiword (Windows 上可能不可用)
    try:
        import subprocess
        result = subprocess.run(['antiword', file_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            for i, para in enumerate(result.stdout.split('\n')):
                para = para.strip()
                if para:
                    texts.append({
                        "text": para,
                        "type": "paragraph",
                        "index": i,
                        "format": {}
                    })
            return texts, {"method": "antiword", "paragraph_count": len(texts)}
    except:
        pass
    
    raise ValueError(
        "无法解析 .doc 文件。请将 .doc 文件另存为 .docx 格式后重试。"
    )


def parse_file(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    自动识别文件类型并解析
    
    Args:
        file_path: 文件路径
        
    Returns:
        texts: 文本内容列表
        format_info: 格式信息
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    parsers = {
        ".docx": parse_word_file,
        ".doc": parse_doc_file,
        ".xlsx": parse_excel_file,
        ".pdf": parse_pdf_file,
        ".txt": parse_txt_file,
        ".csv": parse_csv_file
    }
    
    if ext in parsers:
        return parsers[ext](file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def get_file_type(file_path: str) -> str:
    """
    获取文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件类型标识
    """
    ext = os.path.splitext(file_path)[1].lower()
    type_map = {
        ".docx": "word",
        ".xlsx": "excel",
        ".pdf": "pdf",
        ".txt": "txt",
        ".csv": "csv"
    }
    return type_map.get(ext, "unknown")
