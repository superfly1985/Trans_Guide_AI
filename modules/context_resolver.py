"""
术语上下文推断模块
根据文本上下文推断最合适的译词
"""

from typing import List, Optional, Dict


class ContextResolver:
    """根据上下文推断最合适的译词"""

    # 领域关键词映射 - 用于推断文本所属领域
    DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        'excel': ['单元格', '工作表', '公式', '函数', '表格', 'sheet', 'cell', 'formula'],
        'biology': ['细胞', '基因', '蛋白质', '组织', '生物', 'cell', 'gene', 'protein'],
        'power': ['电池', '电压', '电流', '充电', '电源', 'battery', 'voltage', 'current'],
        'finance': ['银行', '账户', '存款', '贷款', '金融', 'bank', 'account', 'deposit'],
        'geography': ['河岸', '河流', '地形', '地貌', '地理', 'river', 'bank', 'terrain'],
        'programming': ['库', '函数库', '代码库', '编程', 'library', 'function', 'code'],
    }

    # 译词到领域的映射 - 用于快速查找
    TERM_DOMAIN_MAP: Dict[str, str] = {
        '单元格': 'excel',
        '细胞': 'biology',
        '电池': 'power',
        '银行': 'finance',
        '河岸': 'geography',
        '库': 'programming',
    }

    @classmethod
    def resolve(cls, source_term: str, translations: List[str], text_context: str,
                term_db=None) -> str:
        """
        根据上下文选择最合适的翻译

        Args:
            source_term: 原文术语（如 'cell'）
            translations: 所有可能的译词（如 ['单元格', '细胞', '电池']）
            text_context: 待翻译的文本片段（用于推断上下文）
            term_db: 术语数据库实例（可选，用于获取使用统计）

        Returns:
            最合适的译词
        """
        if not translations:
            return source_term

        if len(translations) == 1:
            return translations[0]

        # 策略0：如果有使用统计，优先使用频率高的
        if term_db:
            try:
                sorted_trans = term_db.get_popular_translations(source_term, translations)
                # 如果有使用记录，优先返回使用最多的
                stats = term_db.get_term_usage_stats(source_term)
                if stats and max(stats.values(), default=0) > 0:
                    # 使用频率最高的译词
                    return sorted_trans[0]
            except Exception:
                pass  # 统计失败则继续其他策略

        text_lower = text_context.lower()

        # 策略1：直接匹配上下文中的关键词
        for trans in translations:
            if trans in text_context:
                # 如果译词本身出现在上下文中，说明可能是该领域
                return trans

        # 策略2：计算每个领域的匹配度
        domain_scores: Dict[str, int] = {}
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                domain_scores[domain] = score

        if domain_scores:
            # 找到最可能的领域
            best_domain = max(domain_scores, key=domain_scores.get)

            # 在该领域的译词中选择
            for trans in translations:
                trans_domain = cls.TERM_DOMAIN_MAP.get(trans)
                if trans_domain == best_domain:
                    return trans

        # 策略3：返回第一个作为默认
        return translations[0]

    @classmethod
    def resolve_batch(cls, source_term: str, translations: List[str],
                      contexts: List[str], term_db=None) -> str:
        """
        根据多个上下文片段综合推断

        Args:
            source_term: 原文术语
            translations: 所有可能的译词
            contexts: 多个文本片段
            term_db: 术语数据库实例（可选）

        Returns:
            最合适的译词
        """
        if not translations:
            return source_term

        if len(translations) == 1:
            return translations[0]

        # 合并所有上下文
        combined_context = ' '.join(contexts)
        return cls.resolve(source_term, translations, combined_context, term_db)

    @classmethod
    def get_domain_hint(cls, text_context: str) -> Optional[str]:
        """
        获取文本所属的领域提示

        Args:
            text_context: 文本片段

        Returns:
            领域名称或 None
        """
        text_lower = text_context.lower()
        domain_scores: Dict[str, int] = {}

        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                domain_scores[domain] = score

        if domain_scores:
            return max(domain_scores, key=domain_scores.get)

        return None

    @classmethod
    def add_domain_keywords(cls, domain: str, keywords: List[str]):
        """
        动态添加领域关键词（用于扩展）

        Args:
            domain: 领域名称
            keywords: 关键词列表
        """
        if domain not in cls.DOMAIN_KEYWORDS:
            cls.DOMAIN_KEYWORDS[domain] = []
        cls.DOMAIN_KEYWORDS[domain].extend(keywords)
        # 去重
        cls.DOMAIN_KEYWORDS[domain] = list(set(cls.DOMAIN_KEYWORDS[domain]))

    @classmethod
    def add_term_domain_mapping(cls, term: str, domain: str):
        """
        添加译词到领域的映射

        Args:
            term: 译词
            domain: 领域
        """
        cls.TERM_DOMAIN_MAP[term] = domain
