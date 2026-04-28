# -*- coding: utf-8 -*-
"""
双语对智能检测模块
使用规则 + LLM 辅助检测文档中的双语对
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class BilingualPair:
    """双语对数据结构"""
    source: str  # 原文（英文）
    target: str  # 译文（中文）
    confidence: float = 0.0  # 置信度
    method: str = "rule"  # 检测方法: rule, llm, table
    index: int = 0  # 序号


class BilingualDetector:
    """双语对检测器"""
    
    def __init__(self, llm_client=None):
        """
        初始化检测器
        
        Args:
            llm_client: LLM 客户端，用于智能检测
        """
        self.llm_client = llm_client
        self.min_en_length = 3  # 英文最小长度
        self.min_zh_length = 2  # 中文最小长度
    
    def detect_language(self, text: str) -> str:
        """
        检测文本主要语言
        
        Args:
            text: 文本内容
            
        Returns:
            'en', 'zh', 'mixed', 'unknown'
        """
        if not text:
            return 'unknown'
        
        text = text.strip()
        
        # 统计字符
        en_chars = len(re.findall(r'[a-zA-Z]', text))
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        
        if total_chars == 0:
            return 'unknown'
        
        en_ratio = en_chars / total_chars
        zh_ratio = zh_chars / total_chars
        
        if en_ratio > 0.8:
            return 'en'
        elif zh_ratio > 0.8:
            return 'zh'
        elif en_ratio > 0.3 and zh_ratio > 0.3:
            return 'mixed'
        else:
            return 'unknown'
    
    def is_likely_english(self, text: str) -> bool:
        """判断文本是否主要是英文"""
        return self.detect_language(text) == 'en'
    
    def is_likely_chinese(self, text: str) -> bool:
        """判断文本是否主要是中文"""
        return self.detect_language(text) == 'zh'
    
    def is_mixed_bilingual(self, text: str) -> bool:
        """判断文本是否包含混合双语"""
        return self.detect_language(text) == 'mixed'
    
    def split_mixed_line(self, text: str) -> Tuple[str, str]:
        """
        分割混合双语行
        例如: "Hello world 你好世界" -> ("Hello world", "你好世界")
        
        Args:
            text: 混合文本
            
        Returns:
            (英文部分, 中文部分)
        """
        # 尝试按常见分隔符分割
        # 模式1: 英文 + 分隔符 + 中文
        patterns = [
            r'^([a-zA-Z][a-zA-Z\s\-\(\)\[\]0-9.,:;!?]*?)\s*[-–—:：]\s*([\u4e00-\u9fff][\u4e00-\u9fff\s\-\(\)\[\]0-9.,:;!?]*)$',
            r'^([a-zA-Z][a-zA-Z\s\-\(\)\[\]0-9.,:;!?]*?)\s+([\u4e00-\u9fff][\u4e00-\u9fff\s\-\(\)\[\]0-9.,:;!?]*)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text.strip())
            if match:
                return match.group(1).strip(), match.group(2).strip()
        
        # 如果没有匹配到，尝试按字符类型分割
        en_part = re.sub(r'[^\x00-\x7F]+', ' ', text).strip()
        zh_part = re.sub(r'[\x00-\x7F]+', ' ', text).strip()
        
        return en_part, zh_part
    
    def detect_from_blocks(self, blocks: List[Dict]) -> List[BilingualPair]:
        """
        从文本块中检测双语对
        
        Args:
            blocks: 文本块列表，每个块包含 'text' 字段
            
        Returns:
            双语对列表
        """
        pairs = []
        
        # 策略1: 交替检测 (英文块、中文块、英文块、中文块...)
        pairs.extend(self._detect_alternate(blocks))
        
        # 策略2: 表格结构检测
        pairs.extend(self._detect_table_structure(blocks))
        
        # 策略3: 混合行检测
        pairs.extend(self._detect_mixed_lines(blocks))
        
        # 去重并排序
        pairs = self._deduplicate_pairs(pairs)
        
        return pairs
    
    def _detect_alternate(self, blocks: List[Dict]) -> List[BilingualPair]:
        """检测交替排列的双语对"""
        pairs = []
        i = 0
        
        while i < len(blocks) - 1:
            current = blocks[i]['text'].strip()
            next_block = blocks[i + 1]['text'].strip()
            
            current_lang = self.detect_language(current)
            next_lang = self.detect_language(next_block)
            
            # 如果当前是英文，下一个是中文
            if current_lang == 'en' and next_lang == 'zh':
                if len(current) >= self.min_en_length and len(next_block) >= self.min_zh_length:
                    pairs.append(BilingualPair(
                        source=current,
                        target=next_block,
                        confidence=0.8,
                        method='alternate',
                        index=len(pairs)
                    ))
                    i += 2
                    continue
            
            # 如果当前是中文，下一个是英文（反向顺序）
            elif current_lang == 'zh' and next_lang == 'en':
                if len(next_block) >= self.min_en_length and len(current) >= self.min_zh_length:
                    pairs.append(BilingualPair(
                        source=next_block,
                        target=current,
                        confidence=0.8,
                        method='alternate',
                        index=len(pairs)
                    ))
                    i += 2
                    continue
            
            i += 1
        
        return pairs
    
    def _detect_table_structure(self, blocks: List[Dict]) -> List[BilingualPair]:
        """从表格结构中检测双语对"""
        pairs = []
        
        # 按表格分组
        table_blocks = {}
        for block in blocks:
            if block.get('type') == 'table_cell':
                table_idx = block.get('table_index', 0)
                row = block.get('row', 0)
                col = block.get('col', 0)
                
                if table_idx not in table_blocks:
                    table_blocks[table_idx] = {}
                if row not in table_blocks[table_idx]:
                    table_blocks[table_idx][row] = {}
                
                table_blocks[table_idx][row][col] = block['text'].strip()
        
        # 分析每个表格
        for table_idx, rows in table_blocks.items():
            for row_idx, cols in rows.items():
                if len(cols) >= 2:
                    # 假设第一列是英文，第二列是中文
                    col_keys = sorted(cols.keys())
                    first_col = cols[col_keys[0]]
                    second_col = cols[col_keys[1]]
                    
                    first_lang = self.detect_language(first_col)
                    second_lang = self.detect_language(second_col)
                    
                    if first_lang == 'en' and second_lang == 'zh':
                        pairs.append(BilingualPair(
                            source=first_col,
                            target=second_col,
                            confidence=0.9,
                            method='table',
                            index=len(pairs)
                        ))
                    elif first_lang == 'zh' and second_lang == 'en':
                        pairs.append(BilingualPair(
                            source=second_col,
                            target=first_col,
                            confidence=0.9,
                            method='table',
                            index=len(pairs)
                        ))
        
        return pairs
    
    def _detect_mixed_lines(self, blocks: List[Dict]) -> List[BilingualPair]:
        """检测包含混合双语的行"""
        pairs = []
        
        for block in blocks:
            text = block['text'].strip()
            
            if self.is_mixed_bilingual(text):
                en_part, zh_part = self.split_mixed_line(text)
                
                if len(en_part) >= self.min_en_length and len(zh_part) >= self.min_zh_length:
                    pairs.append(BilingualPair(
                        source=en_part,
                        target=zh_part,
                        confidence=0.7,
                        method='mixed',
                        index=len(pairs)
                    ))
        
        return pairs
    
    def _is_valid_text(self, text: str) -> bool:
        """检查文本是否有效（不包含太多乱码）"""
        if not text:
            return False
        
        # 乱码字符集合 - 扩展
        garbage_chars = set('Ხ᳂ᳺᵞ⼋ꗬ㞸橢夵撘抛ெ༲ⴺⵎⶼⶾⷆⷒⷦⷪⷶ⸎⸐⸒⸔⸺⸼⹀⹄⹆⼆⼊⽘⽜⾸ꐓꐔ䩃䩏䩑䩞䩡㼼㍶⏁戬沓悺碛ӭℊ䃏᪩䚒瑥祳縭৲楌㬙姫ㅌփڂᮨ㣕嫼픂헍⺜ရ鞓Ⱛ껹ÿ恴䄀䐀搀晁餌騀Ѐ仰눀ࣰꗬÁmЉዸ¿က㠀㞸橢橢Љ夵撘抛撘抛ெĕ·༲༲ᲮᲮ᳂ᳺᵞ⼋萏葞')
        
        garbage_count = sum(1 for char in text if char in garbage_chars)
        
        # 如果乱码字符超过5%，认为是无效文本（更严格）
        if len(text) > 0 and garbage_count / len(text) > 0.05:
            return False
        
        # 检查是否包含太多特殊符号（如 ! " # $ % & ' ( ) * + 连续出现）
        # 匹配连续的特殊字符，允许中间有空格
        special_chars_pattern = r'(?:[!"#$%&\'()*+,./:;<=>?@\[\\\]^_`{|}~]\s*){5,}'
        if re.search(special_chars_pattern, text):
            return False
        
        # 检查是否包含数字序列（如 0 1 2 3 4 5 6 7 8 9）
        digit_sequence_pattern = r'(?:\d\s*){5,}'
        if re.search(digit_sequence_pattern, text):
            return False
        
        # 检查是否包含OLE/Word内部标记
        ole_markers = ['Properties', 'CompObj', 'WordDocument', 'Table Grid', 'Überschrift']
        for marker in ole_markers:
            if marker in text:
                return False
        
        # 检查是否包含太多非标准字符
        valid_count = 0
        for char in text:
            # 基本拉丁字母（可打印）
            if '\x20' <= char <= '\x7e':
                valid_count += 1
            # 中文
            elif '\u4e00' <= char <= '\u9fff':
                valid_count += 1
            # 中文标点
            elif '\u3000' <= char <= '\u303f':
                valid_count += 1
            # 德文字母（Überschrift 等）
            elif '\u00c0' <= char <= '\u00ff':
                valid_count += 1
        
        # 有效字符比例必须 > 70%
        if len(text) > 0 and valid_count / len(text) < 0.7:
            return False
        
        return True
    
    def _deduplicate_pairs(self, pairs: List[BilingualPair]) -> List[BilingualPair]:
        """去重双语对，并过滤掉包含乱码的对"""
        seen = {}
        unique_pairs = []
        
        for pair in pairs:
            # 过滤掉包含乱码的对
            if not self._is_valid_text(pair.source) or not self._is_valid_text(pair.target):
                continue
            
            # 过滤掉太短的对
            if len(pair.source.strip()) < 3 or len(pair.target.strip()) < 2:
                continue
            
            # 使用原文作为key
            key = pair.source.lower().strip()
            if key not in seen:
                seen[key] = pair
                unique_pairs.append(pair)
        
        # 重新编号
        for i, pair in enumerate(unique_pairs):
            pair.index = i
        
        return unique_pairs
    
    def detect_with_llm(self, text_samples: List[str]) -> List[BilingualPair]:
        """
        使用 LLM 辅助检测双语对
        
        Args:
            text_samples: 文本样本列表
            
        Returns:
            双语对列表
        """
        if not self.llm_client or len(text_samples) == 0:
            return []
        
        # 构建提示
        samples_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(text_samples[:20])])
        
        prompt = f"""分析以下文本样本，识别其中的双语对（英文-中文对照）。

文本样本：
{samples_text}

请返回识别到的双语对，格式如下：
英文原文 | 中文译文

只返回确信的双语对，每行一个。如果没有识别到，返回"无"。"""

        try:
            response = self.llm_client.generate(prompt)
            
            pairs = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if '|' in line and line != '无':
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        source = parts[0].strip()
                        target = parts[1].strip()
                        if source and target:
                            pairs.append(BilingualPair(
                                source=source,
                                target=target,
                                confidence=0.85,
                                method='llm',
                                index=len(pairs)
                            ))
            
            return pairs
        except Exception as e:
            print(f"LLM 检测失败: {e}")
            return []
    
    def analyze_document_structure(self, blocks: List[Dict]) -> Dict:
        """
        分析文档结构
        
        Args:
            blocks: 文本块列表
            
        Returns:
            文档结构信息
        """
        total_blocks = len(blocks)
        en_blocks = 0
        zh_blocks = 0
        mixed_blocks = 0
        table_blocks = 0
        
        for block in blocks:
            text = block.get('text', '')
            lang = self.detect_language(text)
            
            if lang == 'en':
                en_blocks += 1
            elif lang == 'zh':
                zh_blocks += 1
            elif lang == 'mixed':
                mixed_blocks += 1
            
            if block.get('type') == 'table_cell':
                table_blocks += 1
        
        return {
            'total_blocks': total_blocks,
            'en_blocks': en_blocks,
            'zh_blocks': zh_blocks,
            'mixed_blocks': mixed_blocks,
            'table_blocks': table_blocks,
            'likely_bilingual': (en_blocks > 0 and zh_blocks > 0) or mixed_blocks > 0
        }


def detect_bilingual_pairs(blocks: List[Dict], llm_client=None) -> Tuple[List[Dict], Dict]:
    """
    便捷函数：检测双语对
    
    Args:
        blocks: 文本块列表
        llm_client: 可选的 LLM 客户端
        
    Returns:
        (双语对列表, 分析信息)
    """
    detector = BilingualDetector(llm_client)
    
    # 分析文档结构
    structure = detector.analyze_document_structure(blocks)
    
    # 检测双语对
    pairs = detector.detect_from_blocks(blocks)
    
    # 如果规则检测到的对数较少，尝试使用 LLM
    if len(pairs) < 5 and llm_client and structure['likely_bilingual']:
        text_samples = [b['text'] for b in blocks if len(b['text'].strip()) > 10]
        llm_pairs = detector.detect_with_llm(text_samples)
        
        # 合并结果
        existing_sources = {p.source.lower() for p in pairs}
        for lp in llm_pairs:
            if lp.source.lower() not in existing_sources:
                lp.index = len(pairs)
                pairs.append(lp)
    
    # 转换为字典列表
    result_pairs = [
        {
            'index': p.index,
            'source': p.source,
            'target': p.target,
            'confidence': p.confidence,
            'method': p.method
        }
        for p in pairs
    ]
    
    analysis = {
        'structure': structure,
        'total_pairs': len(pairs),
        'methods_used': list(set(p.method for p in pairs))
    }
    
    return result_pairs, analysis


if __name__ == "__main__":
    # 测试
    test_blocks = [
        {'text': 'Hello world', 'type': 'paragraph'},
        {'text': '你好世界', 'type': 'paragraph'},
        {'text': 'This is a test', 'type': 'paragraph'},
        {'text': '这是一个测试', 'type': 'paragraph'},
        {'text': 'QA issues release confirmation', 'type': 'paragraph'},
        {'text': 'QA负责对所有检验项目进行放行确认', 'type': 'paragraph'},
    ]
    
    detector = BilingualDetector()
    pairs = detector.detect_from_blocks(test_blocks)
    
    print("检测到的双语对：")
    for p in pairs:
        print(f"{p.index}. [{p.method}] {p.source} -> {p.target}")
