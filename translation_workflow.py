# -*- coding: utf-8 -*-
"""
完整翻译工作流
整合文件解析、TM检索、术语约束、LLM翻译、文件导出
"""

import os
import sys
import re
from typing import List, Dict, Tuple
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import ConfigManager
from modules.llm_client import create_llm_client, BaseLLMClient
from modules.file_parser import parse_word_file, parse_excel_file, get_file_type
from modules.file_exporter import export_word_simple, export_excel_simple, get_output_path
from modules.term_db import TermDatabase
from modules.tm_db import TMDatabase
from modules.translator import TRANSLATION_PROMPT
from modules.logger import setup_logger


class TranslationWorkflow:
    """翻译工作流管理器"""
    
    def __init__(self, config_path: str = "./config.json"):
        """
        初始化翻译工作流
        
        Args:
            config_path: 配置文件路径
        """
        self.config = ConfigManager(config_path).get_all()
        self.logger = setup_logger(self.config.get("storage", {}).get("log_path", "./data/trans_guide.log"))
        
        # 初始化LLM客户端
        llm_config = self.config.get("llm", {})
        api_config = self.config.get("api", {})
        full_config = {
            **llm_config,
            "base_url": api_config.get("base_url"),
            "api_key": api_config.get("api_key"),
            "model_name": api_config.get("model_name")
        }
        self.llm_client = create_llm_client(full_config)
        
        # 初始化数据库
        db_path = self.config.get("storage", {}).get("db_path", "./data/trans_guide.db")
        self.term_db = TermDatabase(db_path)
        self.tm_db = TMDatabase(db_path)
        
        # 加载配置参数
        trans_config = self.config.get("translation", {})
        self.tm_threshold = trans_config.get("tm_threshold", 0.85)
        self.tm_top_k = trans_config.get("tm_top_k", 3)
        self.output_mode = trans_config.get("output_mode", "bilingual")
        
        self.logger.info("翻译工作流初始化完成")
    
    def translate_text(self, text: str) -> Dict:
        """
        翻译单个文本
        
        Args:
            text: 待翻译文本
            
        Returns:
            翻译结果字典
        """
        if not text or not text.strip():
            return {
                "original": text,
                "translation": "",
                "source": "empty"
            }
        
        # 检查是否是英文
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        if english_chars < 5:
            return {
                "original": text,
                "translation": text,  # 非英文，直接返回原文
                "source": "non_english"
            }
        
        # 1. 检索术语
        all_terms = self.term_db.get_all_terms()
        matched_terms = {}
        for en, zh in all_terms.items():
            if en.lower() in text.lower():
                matched_terms[en] = zh
        
        # 2. 检索TM
        tm_matches = self.tm_db.search_similar(text, top_k=self.tm_top_k)
        
        # 3. 检查TM匹配度
        if tm_matches and tm_matches[0].get("similarity", 0) >= self.tm_threshold:
            # 使用TM翻译
            return {
                "original": text,
                "translation": tm_matches[0]["translation"],
                "terms_used": matched_terms,
                "tm_reference": tm_matches[0],
                "source": "tm"
            }
        
        # 4. 使用LLM翻译
        terms_str = "\n".join([f"  - {k} -> {v}" for k, v in matched_terms.items()]) if matched_terms else "无"
        tm_str = format_tm_examples(tm_matches) if tm_matches else "无"
        
        prompt = TRANSLATION_PROMPT.format(
            text=text,
            terms=terms_str,
            tm_examples=tm_str
        )
        
        try:
            response = self.llm_client.generate(prompt)
            # 移除think标签
            translation = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            
            return {
                "original": text,
                "translation": translation,
                "terms_used": matched_terms,
                "tm_references": tm_matches,
                "source": "llm"
            }
        except Exception as e:
            self.logger.error(f"LLM翻译失败: {e}")
            return {
                "original": text,
                "translation": f"[翻译失败: {str(e)}]",
                "source": "error"
            }
    
    def translate_file(self, input_path: str, output_path: str = None, mode: str = None) -> bool:
        """
        翻译文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            mode: 输出模式 "bilingual" | "target_only"
            
        Returns:
            是否成功
        """
        if not os.path.exists(input_path):
            self.logger.error(f"文件不存在: {input_path}")
            return False
        
        # 确定输出路径
        if not output_path:
            suffix = "_双语" if (mode or self.output_mode) == "bilingual" else "_译文"
            output_path = get_output_path(input_path, suffix)
        
        # 确定输出模式
        if not mode:
            mode = self.output_mode
        
        file_type = get_file_type(input_path)
        self.logger.info(f"开始翻译文件: {input_path} (类型: {file_type})")
        
        try:
            if file_type == "word":
                return self._translate_word(input_path, output_path, mode)
            elif file_type == "excel":
                return self._translate_excel(input_path, output_path, mode)
            else:
                self.logger.error(f"不支持的文件类型: {file_type}")
                return False
        except Exception as e:
            self.logger.error(f"翻译文件失败: {e}")
            return False
    
    def _translate_word(self, input_path: str, output_path: str, mode: str) -> bool:
        """翻译Word文件"""
        # 解析文件
        texts, info = parse_word_file(input_path)
        self.logger.info(f"解析完成: {len(texts)} 个文本块")
        
        # 翻译每个文本块
        translations = {}
        for i, block in enumerate(texts):
            original = block.get('text', '').strip()
            if not original:
                continue
            
            result = self.translate_text(original)
            translations[i] = result["translation"]
            
            # 记录翻译来源统计
            source = result.get("source", "unknown")
            self.logger.debug(f"[{i}] {source}: {original[:50]}... -> {result['translation'][:50]}...")
            
            # 每10个文本块显示一次进度
            if (i + 1) % 10 == 0:
                print(f"  进度: {i + 1}/{len(texts)}")
        
        # 导出文件
        success = export_word_simple(input_path, translations, output_path, mode)
        if success:
            self.logger.info(f"翻译完成，输出文件: {output_path}")
            print(f"\n✓ 翻译完成！")
            print(f"  输入: {input_path}")
            print(f"  输出: {output_path}")
            print(f"  模式: {'双语对照' if mode == 'bilingual' else '仅译文'}")
            print(f"  共翻译 {len(translations)} 个文本块")
        
        return success
    
    def _translate_excel(self, input_path: str, output_path: str, mode: str) -> bool:
        """翻译Excel文件"""
        # 解析文件
        texts, info = parse_excel_file(input_path)
        self.logger.info(f"解析完成: {len(texts)} 个单元格")
        
        # 翻译每个单元格
        translations = {}
        for i, block in enumerate(texts):
            original = block.get('text', '').strip()
            if not original:
                continue
            
            sheet = block.get('sheet', 'Sheet1')
            row = block.get('row', 0)
            col = block.get('col', 0)
            
            result = self.translate_text(original)
            translations[(sheet, row, col)] = result["translation"]
            
            if (i + 1) % 10 == 0:
                print(f"  进度: {i + 1}/{len(texts)}")
        
        # 导出文件
        success = export_excel_simple(input_path, translations, output_path, mode)
        if success:
            self.logger.info(f"翻译完成，输出文件: {output_path}")
            print(f"\n✓ 翻译完成！")
            print(f"  输入: {input_path}")
            print(f"  输出: {output_path}")
            print(f"  共翻译 {len(translations)} 个单元格")
        
        return success
    
    def batch_translate(self, input_dir: str, output_dir: str = None, mode: str = None) -> Dict:
        """
        批量翻译目录中的文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录（可选）
            mode: 输出模式
            
        Returns:
            翻译统计信息
        """
        if not os.path.exists(input_dir):
            self.logger.error(f"目录不存在: {input_dir}")
            return {"success": 0, "failed": 0, "total": 0}
        
        if not output_dir:
            output_dir = os.path.join(input_dir, "translated")
        os.makedirs(output_dir, exist_ok=True)
        
        # 查找所有支持的文件
        supported_exts = ['.docx', '.xlsx', '.doc', '.xls']
        files = [f for f in os.listdir(input_dir) 
                 if os.path.isfile(os.path.join(input_dir, f))
                 and any(f.lower().endswith(ext) for ext in supported_exts)]
        
        print(f"\n找到 {len(files)} 个待翻译文件:")
        for f in files:
            print(f"  - {f}")
        
        stats = {"success": 0, "failed": 0, "total": len(files)}
        
        for i, filename in enumerate(files, 1):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            
            print(f"\n[{i}/{len(files)}] 翻译: {filename}")
            
            if self.translate_file(input_path, output_path, mode):
                stats["success"] += 1
            else:
                stats["failed"] += 1
        
        print(f"\n{'='*60}")
        print("批量翻译完成")
        print(f"  成功: {stats['success']}")
        print(f"  失败: {stats['failed']}")
        print(f"  总计: {stats['total']}")
        print(f"{'='*60}")
        
        return stats


def format_tm_examples(examples: List[Dict]) -> str:
    """格式化TM示例"""
    if not examples:
        return "无"
    lines = []
    for i, ex in enumerate(examples[:3], 1):  # 最多显示3个
        score = ex.get("similarity", 0)
        original = ex.get("original", "")
        translation = ex.get("translation", "")
        lines.append(f"  {i}. 原文: {original[:80]}...")
        lines.append(f"     译文: {translation[:80]}...（匹配度: {score:.1%}）")
    return "\n".join(lines)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='作业指导书智能翻译工具')
    parser.add_argument('input', help='输入文件或目录路径')
    parser.add_argument('-o', '--output', help='输出文件或目录路径')
    parser.add_argument('-m', '--mode', choices=['bilingual', 'target_only'], 
                        default='bilingual', help='输出模式: bilingual(双语对照) 或 target_only(仅译文)')
    parser.add_argument('-b', '--batch', action='store_true', help='批量翻译目录中的所有文件')
    
    args = parser.parse_args()
    
    # 初始化工作流
    workflow = TranslationWorkflow()
    
    if args.batch:
        # 批量翻译
        workflow.batch_translate(args.input, args.output, args.mode)
    else:
        # 单文件翻译
        if os.path.isdir(args.input):
            print(f"错误: {args.input} 是目录，请使用 -b 参数进行批量翻译")
            return
        workflow.translate_file(args.input, args.output, args.mode)


if __name__ == "__main__":
    main()
