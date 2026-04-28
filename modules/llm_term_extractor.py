# -*- coding: utf-8 -*-
"""
基于 LLM 的术语提取模块
使用 LLM 分析文档内容，提取专业术语
"""

import json
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class ExtractedTerm:
    """提取的术语"""
    english: str
    chinese: str
    category: str = ""  # 分类，如：技术、管理、质量等
    confidence: float = 0.0  # 置信度
    context: str = ""  # 上下文


class LLMTermExtractor:
    """LLM 术语提取器"""
    
    def __init__(self, llm_client):
        """
        初始化提取器
        
        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        self.max_text_length = 80000  # MiniMax支持的最大安全文本长度
    
    def extract_terms_from_text(self, text: str, max_terms: int = 50) -> List[ExtractedTerm]:
        """
        从文本中提取术语
        
        Args:
            text: 文本内容
            max_terms: 最大提取术语数
            
        Returns:
            术语列表
        """
        if not self.llm_client:
            return []
        
        # 截断文本
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length] + "..."
        
        prompt = f"""分析以下技术文档内容，提取其中的专业术语（英文-中文对照）。

文档内容：
{text}

请提取专业术语，要求：
1. 只提取真正的专业术语，如：技术名词、行业标准、设备名称、质量术语等
2. 不要提取普通词汇（如：the, and, 你好, 谢谢）
3. 不要提取大段句子
4. 每个术语应该是词组或短句（2-10个单词）
5. 优先提取在文档中多次出现的术语

请以 JSON 格式返回，格式如下：
{{
    "terms": [
        {{
            "english": "英文术语",
            "chinese": "中文译法",
            "category": "分类（如：技术/管理/质量/设备）"
        }}
    ]
}}

最多返回 {max_terms} 个术语。如果没有找到术语，返回空数组。"""

        try:
            print(f"[LLM术语提取] 发送请求，文本长度: {len(text)}, 请求术语数: {max_terms}")
            # 减少 max_tokens 和增加 temperature 让响应更快
            response = self.llm_client.generate(prompt, max_tokens=1000, temperature=0.5)
            print(f"[LLM术语提取] 收到响应，长度: {len(response)}")
            print(f"[LLM术语提取] 响应预览: {response[:500]}...")
            
            # 解析 JSON 响应
            terms = self._parse_term_response(response)
            print(f"[LLM术语提取] 解析到 {len(terms)} 个术语")
            return terms
            
        except Exception as e:
            print(f"[LLM术语提取] 失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_terms_from_file(self, file_content: str, file_type: str = "doc", max_terms: int = 50) -> List[ExtractedTerm]:
        """
        从文件内容中提取术语
        
        Args:
            file_content: 文件文本内容
            file_type: 文件类型
            
        Returns:
            术语列表
        """
        if not file_content or not self.llm_client:
            return []
        
        # 清理文本
        cleaned_text = self._clean_text(file_content)
        
        # 如果文本太长，分段处理
        if len(cleaned_text) > self.max_text_length:
            return self._extract_from_long_text(cleaned_text, max_terms)
        
        return self.extract_terms_from_text(cleaned_text, max_terms)
    
    def _extract_from_long_text(self, text: str, max_terms: int = 50) -> List[ExtractedTerm]:
        """从长文本中提取术语（分段处理）"""
        all_terms = []
        
        # 将文本分成多个段落
        paragraphs = text.split('\n')
        
        # 每10个段落一组
        chunk_size = 10
        per_chunk_max = max(10, max_terms // 5)  # 每段最多提取的术语数
        
        for i in range(0, len(paragraphs), chunk_size):
            chunk = '\n'.join(paragraphs[i:i+chunk_size])
            if len(chunk) > 100:  # 至少100个字符
                terms = self.extract_terms_from_text(chunk, max_terms=per_chunk_max)
                all_terms.extend(terms)
        
        # 去重
        seen = {}
        unique_terms = []
        for term in all_terms:
            key = term.english.lower().strip()
            if key not in seen:
                seen[key] = term
                unique_terms.append(term)
        
        # 限制总数
        if len(unique_terms) > max_terms:
            unique_terms = unique_terms[:max_terms]
        
        return unique_terms
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 去除乱码字符
        garbage_chars = 'Ხ᳂ᳺᵞ⼋ꗬ㞸橢夵撘抛ெ༲ⴺⵎⶼⶾⷆⷒⷦⷪⷶ⸎⸐⸒⸔⸺⸼⹀⹄⹆⼆⼊⽘⽜⾸ꐓꐔ䩃䩏䩑䩞䩡'
        for char in garbage_chars:
            text = text.replace(char, ' ')
        
        return text.strip()
    
    def _parse_term_response(self, response: str) -> List[ExtractedTerm]:
        """解析 LLM 返回的术语 JSON"""
        terms = []
        
        try:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                
                term_list = data.get('terms', [])
                for term_data in term_list:
                    english = term_data.get('english', '').strip()
                    chinese = term_data.get('chinese', '').strip()
                    category = term_data.get('category', '').strip()
                    
                    # 过滤无效术语
                    if self._is_valid_term(english, chinese):
                        terms.append(ExtractedTerm(
                            english=english,
                            chinese=chinese,
                            category=category,
                            confidence=0.9
                        ))
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            # 尝试从文本中提取
            terms = self._extract_from_text_fallback(response)
        
        return terms
    
    def _is_valid_term(self, english: str, chinese: str) -> bool:
        """检查术语是否有效"""
        if not english or not chinese:
            return False
        
        # 长度检查
        if len(english) < 2 or len(chinese) < 2:
            return False
        
        if len(english) > 100 or len(chinese) > 100:
            return False
        
        # 不能全是标点
        import string
        if all(c in string.whitespace + string.punctuation for c in english):
            return False
        if all(c in string.whitespace + string.punctuation for c in chinese):
            return False
        
        # 不能包含太多特殊字符
        special_ratio = len(re.findall(r'[!"#$%&\'()*+,./:;<=>?@\[\\\]^_`{|}~]', english)) / len(english) if len(english) > 0 else 0
        if special_ratio > 0.3:
            return False
        
        return True
    
    def _extract_from_text_fallback(self, text: str) -> List[ExtractedTerm]:
        """从文本中手动提取（JSON解析失败时的备用方案）"""
        terms = []
        
        # 查找 "英文" : "中文" 或 英文 - 中文 的模式
        patterns = [
            r'["\']?([^"\'\n]+)["\']?\s*[:：]\s*["\']?([^"\'\n]+)["\']?',
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z])\s*[-–—]\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for en, zh in matches:
                en = en.strip()
                zh = zh.strip()
                if self._is_valid_term(en, zh):
                    terms.append(ExtractedTerm(
                        english=en,
                        chinese=zh,
                        confidence=0.7
                    ))
        
        return terms


def extract_terms_with_llm(file_content: str, llm_client, max_terms: int = 50) -> List[Dict]:
    """
    便捷函数：使用 LLM 提取术语
    
    Args:
        file_content: 文件内容
        llm_client: LLM 客户端
        max_terms: 最大术语数
        
    Returns:
        术语字典列表
    """
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


# 测试
if __name__ == "__main__":
    # 模拟测试
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
