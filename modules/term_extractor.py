# -*- coding: utf-8 -*-
"""
LLM术语提取模块
使用LLM从历史双语文件中提取术语
"""

import json
import re
from typing import Dict, List, Tuple


TERM_EXTRACTION_PROMPT = """你是一名专业的技术翻译术语提取专家。请从以下双语句段中提取专业术语及其中文译法。

要求：
1. 只提取具有专业含义的词汇、短语，如设备名称、工艺参数、操作动作、材料名称等
2. 忽略普通常用词（如 the, and, please, 请, 的 等）
3. 术语以英文原文为key，中文译法为value
4. 如果同一个英文术语有多个可能译法，选择最符合上下文的一个
5. 输出格式：JSON对象，{"英文术语": "中文译法", ...}

双语句段：
{segments}

请直接输出JSON，不要包含其他解释文字。"""


def format_segments_for_prompt(segments: List[Tuple[str, str]]) -> str:
    """
    格式化句段对为提示词格式
    
    Args:
        segments: 句段对列表 [(原文, 译文), ...]
        
    Returns:
        格式化后的字符串
    """
    formatted = []
    for i, (orig, trans) in enumerate(segments, 1):
        formatted.append(f"{i}. 原文: {orig}\n   译文: {trans}")
    return "\n\n".join(formatted)


def parse_term_response(response: str) -> Dict[str, str]:
    """
    解析LLM返回的术语JSON
    
    Args:
        response: LLM响应文本
        
    Returns:
        术语字典 {英文: 中文}
    """
    terms = {}
    
    # 尝试提取JSON部分
    try:
        # 查找JSON代码块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 查找花括号包裹的内容
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response
        
        # 解析JSON
        terms = json.loads(json_str)
        
        # 确保是字符串到字符串的映射
        terms = {str(k): str(v) for k, v in terms.items()}
        
    except json.JSONDecodeError:
        # 如果JSON解析失败，尝试按行解析
        for line in response.split('\n'):
            line = line.strip()
            if ':' in line or '：' in line:
                # 尝试分割键值对
                parts = re.split(r'[:：]', line, 1)
                if len(parts) == 2:
                    key = parts[0].strip().strip('"\'')
                    value = parts[1].strip().strip('"\'')
                    if key and value:
                        terms[key] = value
    
    return terms


def filter_terms(
    terms: Dict[str, str],
    min_length: int = 2
) -> Dict[str, str]:
    """
    过滤术语
    
    Args:
        terms: 术语字典
        min_length: 最小长度
        
    Returns:
        过滤后的术语字典
    """
    filtered = {}
    
    # 常见停用词
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
        'need', 'dare', 'ought', 'used', '的', '了', '在', '是', '和', '与',
        '或', '有', '为', '以', '及', '等', '请', '将', '把', '被', '让',
        '给', '向', '从', '到', '于', '关于', '根据', '按照', '通过', '对于'
    }
    
    for source, target in terms.items():
        # 过滤长度不足的
        if len(source) < min_length:
            continue
        
        # 过滤停用词
        if source.lower() in stop_words:
            continue
        
        # 过滤纯数字
        if source.replace('.', '').replace('-', '').isdigit():
            continue
        
        filtered[source] = target
    
    return filtered


class TermExtractor:
    """术语提取器"""
    
    def __init__(self, llm_client):
        """
        初始化术语提取器
        
        Args:
            llm_client: LLM客户端实例
        """
        self.llm_client = llm_client
    
    def extract_terms(
        self,
        segments: List[Tuple[str, str]],
        batch_size: int = 20
    ) -> Dict[str, str]:
        """
        从双语句段中提取术语
        
        Args:
            segments: 句段对列表
            batch_size: 每批处理的句段数
            
        Returns:
            提取的术语字典 {英文: 中文}
        """
        all_terms = {}
        
        # 分批处理
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            batch_terms = self._extract_batch(batch)
            all_terms.update(batch_terms)
        
        return all_terms
    
    def _extract_batch(self, segments: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        提取单批句段的术语
        
        Args:
            segments: 句段对列表
            
        Returns:
            术语字典
        """
        if not self.llm_client:
            return {}
        
        # 构建提示词
        segments_text = format_segments_for_prompt(segments)
        prompt = TERM_EXTRACTION_PROMPT.format(segments=segments_text)
        
        try:
            # 调用LLM
            response = self.llm_client.generate(prompt)
            
            # 解析响应
            terms = parse_term_response(response)
            
            # 过滤术语
            terms = filter_terms(terms)
            
            return terms
        except Exception as e:
            print(f"术语提取失败: {e}")
            return {}
