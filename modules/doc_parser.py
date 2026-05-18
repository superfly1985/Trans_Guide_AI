# -*- coding: utf-8 -*-
"""
DOC 文件解析器
使用 olefile 解析 OLE 复合文档结构
支持 Word 97-2003 (.doc) 格式
"""

import struct
import re
from typing import List, Dict, Tuple


class DocParser:
    """Word DOC 文件解析器"""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def parse(self) -> Tuple[List[Dict], Dict]:
        """
        解析 DOC 文件

        Returns:
            (文本块列表, 格式信息)
        """
        text = self._extract_text_ole()
        if not text:
            text = self._extract_text_fallback()

        blocks = self._split_paragraphs(text)

        format_info = {
            "file_type": "doc",
            "parser": "olefile",
            "paragraph_count": len(blocks),
            "text_length": len(text)
        }

        return blocks, format_info

    def _extract_text_ole(self) -> str:
        """使用 olefile 从 OLE 结构中正确提取文本"""
        try:
            import olefile
        except ImportError:
            return ""

        try:
            ole = olefile.OleFileIO(self.file_path)
        except Exception:
            return ""

        try:
            if not ole.exists('WordDocument'):
                return ""

            wd = ole.openstream('WordDocument').read()

            wIdent = struct.unpack_from('<H', wd, 0)[0]
            if wIdent != 0xA5EC:
                return ""

            flags = struct.unpack_from('<H', wd, 0x0A)[0]
            fWhichTblStm = (flags >> 9) & 1
            table_stream_name = '1Table' if fWhichTblStm else '0Table'

            ccpText = struct.unpack_from('<I', wd, 0x4C)[0]
            ccpFtn = struct.unpack_from('<I', wd, 0x50)[0]
            ccpHdd = struct.unpack_from('<I', wd, 0x54)[0]
            ccpAtn = struct.unpack_from('<I', wd, 0x58)[0]
            ccpEdn = struct.unpack_from('<I', wd, 0x5C)[0]
            ccpTxbx = struct.unpack_from('<I', wd, 0x60)[0]

            fcClx = struct.unpack_from('<I', wd, 0x01A2)[0]
            lcbClx = struct.unpack_from('<I', wd, 0x01A6)[0]

            if lcbClx == 0:
                return ""

            if not ole.exists(table_stream_name):
                return ""

            table_data = ole.openstream(table_stream_name).read()
            clx_data = table_data[fcClx:fcClx + lcbClx]

            pos = 0
            while pos < len(clx_data):
                clxt = clx_data[pos]
                if clxt == 0x01:
                    cb = struct.unpack_from('<H', clx_data, pos + 1)[0]
                    pos += 3 + cb
                elif clxt == 0x02:
                    lcb = struct.unpack_from('<I', clx_data, pos + 1)[0]
                    plcpcd_data = clx_data[pos + 5:pos + 5 + lcb]

                    n = (lcb - 4) // 12
                    if n <= 0:
                        return ""

                    total_chars = ccpText + ccpFtn + ccpHdd + ccpAtn + ccpEdn + ccpTxbx

                    text_parts = []
                    for i in range(n):
                        cp_start = struct.unpack_from('<I', plcpcd_data, i * 4)[0]
                        cp_end = struct.unpack_from('<I', plcpcd_data, (i + 1) * 4)[0]

                        pcd_offset = (n + 1) * 4 + i * 8
                        fc_value = struct.unpack_from('<I', plcpcd_data, pcd_offset + 2)[0]

                        fc_compressed = (fc_value >> 30) & 1
                        fc_real = fc_value & 0x3FFFFFFF

                        char_count = cp_end - cp_start
                        if char_count <= 0:
                            continue

                        if fc_compressed:
                            raw = wd[fc_real:fc_real + char_count]
                            try:
                                text = raw.decode('cp1252', errors='replace')
                            except Exception:
                                text = raw.decode('latin-1', errors='replace')
                        else:
                            raw = wd[fc_real:fc_real + char_count * 2]
                            text = raw.decode('utf-16-le', errors='replace')

                        text_parts.append(text)

                    full_text = ''.join(text_parts)

                    if ccpText > 0 and total_chars > ccpText:
                        main_text = full_text[:ccpText]
                    else:
                        main_text = full_text

                    return main_text
                else:
                    break

            return ""
        except Exception:
            return ""
        finally:
            ole.close()

    def _extract_text_fallback(self) -> str:
        """备用方法：直接从二进制中提取文本"""
        try:
            with open(self.file_path, 'rb') as f:
                data = f.read()
        except Exception:
            return ""

        if len(data) < 8:
            return ""

        if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            return ""

        text_parts = []
        encodings = ['utf-16-le', 'cp1252', 'latin-1']

        for encoding in encodings:
            try:
                if encoding == 'utf-16-le':
                    decoded = data.decode(encoding, errors='ignore')
                else:
                    decoded = data.decode(encoding, errors='ignore')

                filtered = ''.join(
                    c for c in decoded
                    if c.isprintable() or c in '\n\r\t'
                )

                if len(filtered) > 100:
                    text_parts.append(filtered)
                    break
            except Exception:
                continue

        return '\n'.join(text_parts)

    def _split_paragraphs(self, text: str) -> List[Dict]:
        """将文本分割成段落块"""
        blocks = []

        if not text:
            return blocks

        paragraphs = re.split(r'[\n\r]+', text)

        index = 0
        for para in paragraphs:
            para = para.strip()
            if len(para) >= 2 and self._is_valid_text(para):
                blocks.append({
                    "text": para,
                    "type": "paragraph",
                    "index": index,
                    "format": {}
                })
                index += 1

        return blocks

    def _is_valid_text(self, text: str) -> bool:
        """检查文本是否有效（不是乱码）"""
        if not text or len(text) < 2:
            return False

        valid_count = 0
        for char in text:
            if '\x20' <= char <= '\x7e':
                valid_count += 1
            elif '\u4e00' <= char <= '\u9fff':
                valid_count += 1
            elif '\u3000' <= char <= '\u303f':
                valid_count += 1
            elif '\u0400' <= char <= '\u04FF':
                valid_count += 1
            elif '\u00C0' <= char <= '\u024F':
                valid_count += 1

        total = len(text)
        if total == 0:
            return False

        return (valid_count / total) > 0.5


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
