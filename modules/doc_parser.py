# -*- coding: utf-8 -*-
"""
DOC 文件解析器
纯 Python 实现，不依赖外部工具
支持 Word 97-2003 (.doc) 格式
"""

import struct
import re
from typing import List, Dict, Tuple
from io import BytesIO


class DocParser:
    """Word DOC 文件解析器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = None
        self.text = ""
        
    def parse(self) -> Tuple[List[Dict], Dict]:
        """
        解析 DOC 文件
        
        Returns:
            (文本块列表, 格式信息)
        """
        with open(self.file_path, 'rb') as f:
            self.data = f.read()
        
        # 检查是否是有效的 OLE 文件
        if not self._is_ole_file():
            raise ValueError("不是有效的 DOC 文件")
        
        # 提取文本
        self.text = self._extract_text()
        
        # 按段落分割
        blocks = self._split_paragraphs()
        
        format_info = {
            "file_type": "doc",
            "parser": "built-in",
            "paragraph_count": len(blocks),
            "text_length": len(self.text)
        }
        
        return blocks, format_info
    
    def _is_ole_file(self) -> bool:
        """检查是否是 OLE 复合文档格式"""
        if len(self.data) < 8:
            return False
        # OLE 文件头签名: D0 CF 11 E0 A1 B1 1A E1
        signature = self.data[:8]
        return signature == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    
    def _extract_text(self) -> str:
        """从 DOC 文件中提取文本"""
        text_parts = []
        
        # 方法1: 尝试从 WordDocument 流提取
        word_stream = self._find_stream("WordDocument")
        if word_stream:
            text = self._extract_from_word_stream(word_stream)
            if text:
                text_parts.append(text)
        
        # 方法2: 搜索所有文本
        if not text_parts:
            text = self._extract_all_text()
            if text:
                text_parts.append(text)
        
        # 方法3: 直接提取可打印字符
        if not text_parts:
            text = self._extract_printable_text()
            if text:
                text_parts.append(text)
        
        return "\n".join(text_parts)
    
    def _find_stream(self, stream_name: str) -> bytes:
        """在 OLE 文件中查找指定流"""
        try:
            # 简单的 OLE 流查找
            # 搜索流名称 (Unicode)
            name_bytes = stream_name.encode('utf-16-le')
            pos = self.data.find(name_bytes)
            if pos != -1:
                # 找到流后，尝试提取数据
                # 这里简化处理，直接返回整个数据
                return self.data
        except:
            pass
        return b""
    
    def _extract_from_word_stream(self, data: bytes) -> str:
        """从 Word 文档流中提取文本"""
        text_parts = []
        
        # Word 文档中的文本通常以 UTF-16-LE 编码
        # 搜索文本特征
        i = 0
        while i < len(data) - 1:
            try:
                # 尝试解码 UTF-16-LE
                char = data[i:i+2].decode('utf-16-le', errors='ignore')
                
                # 检查是否是可打印字符或常用标点
                if char.isprintable() or char in '\n\r\t':
                    text_parts.append(char)
                else:
                    # 不可打印字符，添加空格作为分隔
                    if text_parts and text_parts[-1] != ' ':
                        text_parts.append(' ')
                
                i += 2
            except:
                i += 1
        
        return ''.join(text_parts)
    
    def _extract_all_text(self) -> str:
        """提取所有可能的文本"""
        text_parts = []
        
        # 尝试多种编码
        encodings = ['utf-16-le', 'utf-8', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                # 搜索文本段落特征
                # Word 文档中的段落通常以特定字符分隔
                decoded = self.data.decode(encoding, errors='ignore')
                
                # 提取看起来像是文本的部分
                # 过滤掉控制字符
                filtered = ''.join(c for c in decoded if c.isprintable() or c in '\n\r\t')
                
                # 如果提取到足够长的文本，使用它
                if len(filtered) > 100:
                    text_parts.append(filtered)
                    break
            except:
                continue
        
        return '\n'.join(text_parts)
    
    def _extract_printable_text(self) -> str:
        """提取可打印字符，过滤垃圾数据"""
        # 提取所有可打印的 ASCII 和中文字符
        text_parts = []
        current_text = []
        
        # 垃圾字符模式
        garbage_patterns = [
            r'[\x00-\x08\x0b-\x0c\x0e-\x1f]',  # 控制字符
            r'[Ხ᳂ᳺᵞ⼋ꗬ]',  # 常见乱码字符
            r'[㞸橢夵撘抛ெ༲Ხ᳂ᳺᵞ⼋]',  # 更多乱码
            r'[ⴺⵎⶼⶾⷆⷒⷦⷪⷶ⸎⸐⸒⸔⸺⸼⹀⹄⹆⼆⼊⽘⽜⾸]',  # 特殊符号
        ]
        
        # 有效的字符范围
        def is_valid_char(c):
            # 基本拉丁字母
            if '\x00' <= c <= '\x7f':
                return c.isprintable() or c in '\n\r\t'
            # 中文
            if '\u4e00' <= c <= '\u9fff':
                return True
            # 中文标点
            if '\u3000' <= c <= '\u303f':
                return True
            # 常见英文标点
            if c in '.,;:!?()-_[]{}"\'@#$%&*+=/\\|<>':
                return True
            # 数字
            if c.isdigit():
                return True
            return False
        
        # 首先尝试找到文档的实际文本内容
        # Word 文档的文本通常在特定位置
        text_start = 0
        
        # 搜索可能的文本起始位置
        for i in range(512, len(self.data) - 100, 512):
            # 检查是否有连续的文本特征
            sample = self.data[i:i+100]
            try:
                decoded = sample.decode('utf-16-le', errors='ignore')
                # 如果这段内容包含足够多的有效字符，可能是文本区域
                valid_count = sum(1 for c in decoded if is_valid_char(c))
                if valid_count > 30:  # 至少30%是有效字符
                    text_start = i
                    break
            except:
                pass
        
        # 从找到的位置开始提取
        consecutive_invalid = 0
        max_consecutive_invalid = 5  # 最多连续5个无效字符
        
        for i in range(text_start, len(self.data) - 1, 2):
            try:
                char = self.data[i:i+2].decode('utf-16-le', errors='ignore')
                
                # 检查是否是有效字符
                if is_valid_char(char):
                    consecutive_invalid = 0
                    current_text.append(char)
                elif char in '\n\r':
                    consecutive_invalid = 0
                    if current_text:
                        text_parts.append(''.join(current_text))
                        current_text = []
                else:
                    # 无效字符
                    consecutive_invalid += 1
                    # 如果连续多个无效字符，结束当前文本段
                    if consecutive_invalid >= max_consecutive_invalid:
                        if len(current_text) > 5:  # 至少5个字符才算有效段落
                            text_parts.append(''.join(current_text))
                        current_text = []
                        consecutive_invalid = 0
            except:
                consecutive_invalid += 1
        
        # 添加最后一段
        if len(current_text) > 5:
            text_parts.append(''.join(current_text))
        
        # 过滤掉包含太多乱码的行
        filtered_parts = []
        for part in text_parts:
            # 计算有效字符比例
            if len(part) == 0:
                continue
            valid_count = sum(1 for c in part if is_valid_char(c))
            ratio = valid_count / len(part)
            # 如果有效字符比例超过70%，保留
            if ratio > 0.7 and len(part.strip()) > 3:
                filtered_parts.append(part)
        
        return '\n'.join(filtered_parts)
    
    def _split_paragraphs(self) -> List[Dict]:
        """将文本分割成段落块，过滤乱码"""
        blocks = []
        
        # 按换行符分割
        paragraphs = re.split(r'[\n\r]+', self.text)
        
        # 乱码字符模式
        garbage_chars = set('Ხ᳂ᳺᵞ⼋ꗬ㞸橢夵撘抛ெ༲ⴺⵎⶼⶾⷆⷒⷦⷪⷶ⸎⸐⸒⸔⸺⸼⹀⹄⹆⼆⼊⽘⽜⾸ꐓꐔ䩃䩏䩑䩞䩡㼼㍶⏁戬沓悺碛ӭℊ䃏᪩䚒瑥祳縭৲楌㬙姫ㅌփڂᮨ㣕嫼픂헍⺜ရ鞓Ⱛ껹')
        
        def is_valid_text(text):
            """检查文本是否有效（不是乱码）"""
            if not text or len(text) < 3:
                return False
            
            # 计算有效字符
            valid_count = 0
            garbage_count = 0
            
            for char in text:
                # 检查是否是乱码字符
                if char in garbage_chars:
                    garbage_count += 1
                    continue
                # 基本拉丁字母（可打印）
                if '\x20' <= char <= '\x7e':
                    valid_count += 1
                # 中文
                elif '\u4e00' <= char <= '\u9fff':
                    valid_count += 1
                # 中文标点
                elif '\u3000' <= char <= '\u303f':
                    valid_count += 1
            
            total = len(text)
            if total == 0:
                return False
            
            # 有效字符比例 > 60%，且乱码比例 < 20%
            valid_ratio = valid_count / total
            garbage_ratio = garbage_count / total
            
            return valid_ratio > 0.6 and garbage_ratio < 0.2
        
        index = 0
        for para in paragraphs:
            para = para.strip()
            # 过滤掉太短的段落和乱码
            if len(para) >= 5 and is_valid_text(para):
                blocks.append({
                    "text": para,
                    "type": "paragraph",
                    "index": index,
                    "format": {}
                })
                index += 1
        
        return blocks


def parse_doc_file_simple(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    简化的 DOC 文件解析函数
    
    Args:
        file_path: 文件路径
        
    Returns:
        (文本块列表, 格式信息)
    """
    parser = DocParser(file_path)
    return parser.parse()


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            blocks, info = parse_doc_file_simple(test_file)
            print(f"解析成功!")
            print(f"段落数: {info['paragraph_count']}")
            print(f"文本长度: {info['text_length']}")
            print("\n前10段内容:")
            for block in blocks[:10]:
                print(f"  {block['index']}: {block['text'][:80]}...")
        except Exception as e:
            print(f"解析失败: {e}")
    else:
        print("用法: python doc_parser.py <doc文件路径>")
