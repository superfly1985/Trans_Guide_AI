# -*- coding: utf-8 -*-
"""
数据导入模块
负责数据清洗、双语对齐、结构化存储
"""

import re
from typing import List, Tuple, Optional


def clean_text(text: str) -> str:
    """
    清洗文本
    
    Args:
        text: 原始文本
        
    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    
    # 去除首尾空白
    text = text.strip()
    
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # 去除多余空格
    text = re.sub(r"\s+", " ", text)
    
    return text


def is_valid_text(text: str, min_length: int = 3) -> bool:
    """
    检查文本是否有效
    
    Args:
        text: 文本内容
        min_length: 最小有效长度
        
    Returns:
        是否有效
    """
    if not text:
        return False
    text = clean_text(text)
    return len(text) >= min_length


def align_bilingual_data(
    original_list: List[str],
    translation_list: List[str],
    align_mode: str = "auto"
) -> List[Tuple[str, str]]:
    """
    对齐原文和译文
    
    Args:
        original_list: 原文列表
        translation_list: 译文列表
        align_mode: 对齐方式，"auto" | "paragraph" | "line" | "alternate"
        
    Returns:
        对齐后的句段对列表 [(原文, 译文), ...]
    """
    pairs = []
    
    if align_mode == "auto":
        # 自动检测对齐方式
        if len(original_list) == len(translation_list):
            # 可能是逐行对照
            align_mode = "line"
        elif len(original_list) * 2 == len(translation_list):
            # 可能是交替排列（原文、译文、原文、译文...）
            align_mode = "alternate"
        else:
            # 默认按段落对照
            align_mode = "paragraph"
    
    if align_mode == "line":
        # 逐行对照
        for orig, trans in zip(original_list, translation_list):
            orig_clean = clean_text(orig)
            trans_clean = clean_text(trans)
            if is_valid_text(orig_clean) and is_valid_text(trans_clean):
                pairs.append((orig_clean, trans_clean))
    
    elif align_mode == "alternate":
        # 交替排列：奇数原文，偶数译文
        combined = original_list + translation_list
        for i in range(0, len(combined) - 1, 2):
            orig = clean_text(combined[i])
            trans = clean_text(combined[i + 1])
            if is_valid_text(orig) and is_valid_text(trans):
                pairs.append((orig, trans))
    
    elif align_mode == "paragraph":
        # 按段落对照（默认）
        min_len = min(len(original_list), len(translation_list))
        for i in range(min_len):
            orig = clean_text(original_list[i])
            trans = clean_text(translation_list[i])
            if is_valid_text(orig) and is_valid_text(trans):
                pairs.append((orig, trans))
    
    return pairs


def deduplicate_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    去重句段对，保留最新的译文
    
    Args:
        pairs: 句段对列表
        
    Returns:
        去重后的列表
    """
    seen = {}
    for orig, trans in pairs:
        # 使用原文作为key，后面的会覆盖前面的（保留最新）
        seen[orig] = trans
    
    return list(seen.items())


def filter_pairs(
    pairs: List[Tuple[str, str]],
    min_length: int = 3,
    max_length: int = 5000
) -> List[Tuple[str, str]]:
    """
    过滤句段对
    
    Args:
        pairs: 句段对列表
        min_length: 最小长度
        max_length: 最大长度
        
    Returns:
        过滤后的列表
    """
    filtered = []
    for orig, trans in pairs:
        if min_length <= len(orig) <= max_length and min_length <= len(trans) <= max_length:
            filtered.append((orig, trans))
    return filtered


def import_bilingual_file(
    file_path: str,
    align_mode: str = "auto"
) -> List[Tuple[str, str]]:
    """
    导入双语文件并返回句段对
    
    Args:
        file_path: 文件路径
        align_mode: 对齐方式
        
    Returns:
        句段对列表
    """
    from .file_parser import parse_file
    
    # 解析文件
    texts, format_info = parse_file(file_path)
    
    # 提取文本内容
    text_list = [t.get("text", "") for t in texts]
    
    # TODO: 根据文件类型判断如何分割原文和译文
    # 目前简单处理：前半部分原文，后半部分译文
    mid = len(text_list) // 2
    original_list = text_list[:mid]
    translation_list = text_list[mid:]
    
    # 对齐
    pairs = align_bilingual_data(original_list, translation_list, align_mode)
    
    # 去重
    pairs = deduplicate_pairs(pairs)
    
    # 过滤
    pairs = filter_pairs(pairs)
    
    return pairs
