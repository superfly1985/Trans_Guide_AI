# -*- coding: utf-8 -*-
"""
翻译模块
整合术语检索、TM检索、LLM翻译
"""

from typing import Dict, List, Optional


TRANSLATION_PROMPT = """你是一名专业的技术文档翻译专家，擅长翻译制造业作业指导书。

【待翻译文本】
{text}

【强制术语约束】（以下术语必须严格使用指定译法，不允许修改或替换）：
{terms}

【参考历史译法】（以下是与当前句子相似的历史翻译，请保持风格一致）：
{tm_examples}

【翻译要求】
1. 必须严格使用上述强制术语约束中的译法，不得替换为其他译法
2. 参考历史译法的风格，保持译文专业、准确、简洁
3. 忠于原文含义，不添加原文没有的内容，不遗漏原文信息
4. 译文自然流畅，符合中文技术文档表达习惯
5. 只输出译文内容，不要输出任何解释、说明、标记

请翻译："""


def format_terms(terms: Dict[str, str]) -> str:
    """
    格式化术语列表
    
    Args:
        terms: 术语字典 {英文: 中文}
        
    Returns:
        格式化字符串
    """
    if not terms:
        return "无"
    
    lines = []
    for source, target in terms.items():
        lines.append(f"  - {source} -> {target}")
    return "\n".join(lines)


def format_tm_examples(examples: List[Dict]) -> str:
    """
    格式化TM参考示例
    
    Args:
        examples: 相似句段列表
        
    Returns:
        格式化字符串
    """
    if not examples:
        return "无"
    
    lines = []
    for i, ex in enumerate(examples, 1):
        score = ex.get("score", 0)
        original = ex.get("original", "")
        translation = ex.get("translation", "")
        lines.append(f"  {i}. 原文: {original}")
        lines.append(f"     译文: {translation}（匹配度: {score:.1%}）")
    return "\n".join(lines)


def post_process_translation(
    translation: str,
    terms: Dict[str, str]
) -> str:
    """
    译文后处理：确保术语使用正确
    
    Args:
        translation: 原始译文
        terms: 术语约束
        
    Returns:
        处理后的译文
    """
    # TODO: 实现术语校验和自动替换
    # 如果译文中使用了术语的其他译法，自动替换为术语库中的标准译法
    return translation


class Translator:
    """翻译器"""
    
    def __init__(
        self,
        llm_client,
        term_db,
        tm_db,
        config: Optional[Dict] = None
    ):
        """
        初始化翻译器
        
        Args:
            llm_client: LLM客户端
            term_db: 术语库实例
            tm_db: 记忆库实例
            config: 配置字典
        """
        self.llm_client = llm_client
        self.term_db = term_db
        self.tm_db = tm_db
        self.config = config or {}
        
        self.tm_threshold = self.config.get("tm_threshold", 0.85)
        self.tm_top_k = self.config.get("tm_top_k", 3)
    
    def translate(
        self,
        text: str,
        use_cache: bool = True
    ) -> Dict:
        """
        翻译单句
        
        Args:
            text: 待翻译原文
            use_cache: 是否使用缓存
            
        Returns:
            翻译结果字典 {
                "original": 原文,
                "translation": 译文,
                "terms_used": 使用的术语,
                "tm_references": TM参考,
                "source": 翻译来源 (tm/llm)
            }
        """
        if not text or not text.strip():
            return {
                "original": text,
                "translation": "",
                "terms_used": {},
                "tm_references": [],
                "source": "empty"
            }
        
        # 1. 检索术语
        terms = self.term_db.search_terms_in_text(text)
        
        # 2. 检索TM
        tm_results = self.tm_db.search_similar(
            text,
            top_k=self.tm_top_k,
            threshold=self.tm_threshold
        )
        
        # 3. 检查是否可以直接复用TM
        if tm_results and tm_results[0]["score"] >= 0.95:
            # 相似度极高，直接复用
            translation = tm_results[0]["translation"]
            return {
                "original": text,
                "translation": translation,
                "terms_used": terms,
                "tm_references": tm_results,
                "source": "tm"
            }
        
        # 4. 调用LLM翻译
        prompt = TRANSLATION_PROMPT.format(
            text=text,
            terms=format_terms(terms),
            tm_examples=format_tm_examples(tm_results)
        )
        
        try:
            translation = self.llm_client.generate(prompt)
            
            # 后处理
            translation = post_process_translation(translation, terms)
            
            return {
                "original": text,
                "translation": translation,
                "terms_used": terms,
                "tm_references": tm_results,
                "source": "llm"
            }
        except Exception as e:
            print(f"翻译失败: {e}")
            return {
                "original": text,
                "translation": text,  # 失败时返回原文
                "terms_used": terms,
                "tm_references": tm_results,
                "source": "error",
                "error": str(e)
            }
    
    def translate_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[Dict]:
        """
        批量翻译
        
        Args:
            texts: 待翻译文本列表
            show_progress: 是否显示进度条
            
        Returns:
            翻译结果列表
        """
        results = []
        
        iterator = texts
        if show_progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(texts, desc="翻译进度")
            except ImportError:
                pass
        
        for text in iterator:
            result = self.translate(text)
            results.append(result)
        
        return results
