# -*- coding: utf-8 -*-
"""
基于 LLM 的术语提取模块
使用 LLM 分析文档内容，提取专业术语
"""

import json
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass

from .llm_conversation_logger import log_conversation


@dataclass
class ExtractedTerm:
    english: str
    chinese: str
    category: str = ""
    confidence: float = 0.0
    context: str = ""


class LLMTermExtractor:

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.max_text_length = 200000

    def extract_terms_from_text(self, text: str, max_terms: int = 50) -> List[ExtractedTerm]:
        if not self.llm_client:
            return []

        if len(text) > self.max_text_length:
            text = text[:self.max_text_length] + "..."

        prompt = f"""从以下英文-中文交替对照的技术文档中提取专业术语对（奇数行英文，偶数行中文，部分行内含对照）。只挑选真正算专业术语的对，排除普通词汇、日常用语、介词短语。

直接输出一个 JSON 对象，不要任何其他内容：
{{"terms":[{{"e":"English term","c":"中文译法","g":"分类"}}]}}

分类仅选：技术/管理/质量/设备/材料/工艺/文档。最多 {max_terms} 个，无术语则 {{"terms":[]}}。

文档：
{text}"""

        response = None
        try:
            print(f"[LLM术语提取] 发送请求，文本长度: {len(text)}, 请求术语数: {max_terms}")
            response = self.llm_client.generate(prompt, max_tokens=32000, temperature=0.2, system="你是术语提取器。思考要简短，然后直接输出 JSON。")
            print(f"[LLM术语提取] 收到响应，长度: {len(response)}")
            print(f"[LLM术语提取] 响应预览: {response[:500]}...")

            log_conversation('term_extraction', prompt, response, {'max_terms': max_terms, 'text_length': len(text)})

            terms = self._parse_term_response(response)
            print(f"[LLM术语提取] 解析到 {len(terms)} 个术语")
            return terms

        except Exception as e:
            print(f"[LLM术语提取] 失败: {e}")
            import traceback
            traceback.print_exc()
            log_conversation('term_extraction_error', prompt, response or str(e), {'error': str(e)})
            return []

    def extract_terms_from_file(self, file_content: str, file_type: str = "doc", max_terms: int = 50) -> List[ExtractedTerm]:
        if not file_content or not self.llm_client:
            return []

        cleaned_text = self._clean_text(file_content)

        if len(cleaned_text) > self.max_text_length:
            return self._extract_from_long_text(cleaned_text, max_terms)

        return self.extract_terms_from_text(cleaned_text, max_terms)

    def _extract_from_long_text(self, text: str, max_terms: int = 50) -> List[ExtractedTerm]:
        all_terms = []

        paragraphs = text.split('\n')
        chunk_size = 10
        per_chunk_max = max(10, max_terms // 5)

        for i in range(0, len(paragraphs), chunk_size):
            chunk = '\n'.join(paragraphs[i:i+chunk_size])
            if len(chunk) > 100:
                terms = self.extract_terms_from_text(chunk, max_terms=per_chunk_max)
                all_terms.extend(terms)

        seen = {}
        unique_terms = []
        for term in all_terms:
            key = term.english.lower().strip()
            if key not in seen:
                seen[key] = term
                unique_terms.append(term)

        if len(unique_terms) > max_terms:
            unique_terms = unique_terms[:max_terms]

        return unique_terms

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'[^\S\n]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        garbage_chars = 'Ხ᳂ᳺᵞ⼋ꗬ㞸橢夵撘抛ெ༲ⴺⵎⶼⶾⷆⷒⷦⷪⷶ⸎⸐⸒⸔⸺⸼⹀⹄⹆⼆⼊⽘⽜⾸ꐓꐔ䩃䩏䩑䩞䩡'
        for char in garbage_chars:
            text = text.replace(char, ' ')

        return text.strip()

    def _parse_term_response(self, response: str) -> List[ExtractedTerm]:
        terms = []
        json_str = None

        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

        code_block = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            terms_match = re.search(r'\{\s*"terms"\s*:\s*\[.*?\]\s*\}', response, re.DOTALL)
            if terms_match:
                json_str = terms_match.group(0)
            else:
                json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)

        if json_str:
            try:
                data = json.loads(json_str)
                term_list = data.get('terms', [])
                for term_data in term_list:
                    english = term_data.get('e', '') or term_data.get('english', '')
                    chinese = term_data.get('c', '') or term_data.get('chinese', '')
                    category = term_data.get('g', '') or term_data.get('category', '')
                    english = english.strip()
                    chinese = chinese.strip()
                    category = category.strip()
                    if self._is_valid_term(english, chinese):
                        terms.append(ExtractedTerm(
                            english=english,
                            chinese=chinese,
                            category=category,
                            confidence=0.9
                        ))
                return terms
            except (json.JSONDecodeError, TypeError):
                pass

        return self._extract_from_text_fallback(response)

    def _is_valid_term(self, english: str, chinese: str) -> bool:
        if not english or not chinese:
            return False

        if len(english) < 2 or len(chinese) < 2:
            return False

        if len(english) > 100 or len(chinese) > 100:
            return False

        import string
        if all(c in string.whitespace + string.punctuation for c in english):
            return False
        if all(c in string.whitespace + string.punctuation for c in chinese):
            return False

        special_ratio = len(re.findall(r'[!"#$%&\'()*+,./:;<=>?@\[\\\]^_`{|}~]', english)) / len(english) if len(english) > 0 else 0
        if special_ratio > 0.3:
            return False

        return True

    def _extract_from_text_fallback(self, text: str) -> List[ExtractedTerm]:
        terms = []
        json_field_names = {'english', 'chinese', 'category', 'terms', 'term_data', 'term', 'e', 'c', 'g'}

        patterns = [
            r'["\']?([^"\'\n]+)["\']?\s*[:：]\s*["\']?([^"\'\n]+)["\']?',
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z])\s*[-–—]\s*([^\n]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for en, zh in matches:
                en = en.strip()
                zh = zh.strip()
                if en.lower() in json_field_names:
                    continue
                if self._is_valid_term(en, zh):
                    terms.append(ExtractedTerm(
                        english=en,
                        chinese=zh,
                        confidence=0.7
                    ))

        return terms


def extract_terms_with_llm(file_content: str, llm_client, max_terms: int = 50) -> List[Dict]:
    print(f"[extract_terms_with_llm] 开始提取，文本长度: {len(file_content)}")
    print(f"[extract_terms_with_llm] llm_client: {llm_client}")

    if not llm_client:
        print("[extract_terms_with_llm] 错误: llm_client 为 None")
        return []

    try:
        extractor = LLMTermExtractor(llm_client)
        print(f"[extract_terms_with_llm] LLMTermExtractor 创建成功")

        terms = extractor.extract_terms_from_file(file_content, max_terms=max_terms)
        print(f"[extract_terms_with_llm] 提取完成，共 {len(terms)} 个术语")

        return [
            {
                'english': term.english,
                'chinese': term.chinese,
                'category': term.category,
                'confidence': term.confidence
            }
            for term in terms
        ]
    except Exception as e:
        print(f"[extract_terms_with_llm] 异常: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    test_text = """
    Work Instruction 作业指导书
    Process Release 过程放行
    Quality Assurance 质量保证
    All checkpoints completed 所有检查点已完成
    """

    print("术语提取模块测试")
    print("=" * 50)
    print(f"测试文本:\n{test_text}")
    print("\n注意：需要配置 LLM 客户端才能实际提取术语")
