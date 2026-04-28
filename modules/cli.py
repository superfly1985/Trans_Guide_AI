# -*- coding: utf-8 -*-
"""
命令行交互模块
"""

import os
import sys
import argparse
from typing import List

from .config_manager import ConfigManager
from .logger import setup_logger


class CLI:
    """命令行界面"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.logger = setup_logger(self.config.get("storage.log_path"))
        self._init_databases()
    
    def _init_databases(self):
        """初始化数据库连接"""
        from .term_db import TermDatabase
        from .tm_db import TMDatabase
        
        db_path = self.config.get("storage.db_path")
        chroma_path = self.config.get("storage.chroma_path")
        
        self.term_db = TermDatabase(db_path)
        self.tm_db = TMDatabase(db_path, chroma_path)
    
    def _get_llm_client(self):
        """获取LLM客户端"""
        from .llm_client import create_llm_client
        
        llm_type = self.config.get("llm.type")
        if llm_type == "local":
            config = {
                "type": "local",
                "local_model_path": self.config.get("llm.local_model_path"),
                "context_length": self.config.get("llm.context_length"),
                "temperature": self.config.get("llm.temperature"),
                "gpu_layers": self.config.get("llm.gpu_layers"),
                "max_tokens": self.config.get("llm.max_tokens")
            }
        else:
            config = {
                "type": "api",
                "base_url": self.config.get("api.base_url"),
                "api_key": self.config.get("api.api_key"),
                "model_name": self.config.get("api.model_name"),
                "temperature": self.config.get("llm.temperature"),
                "max_tokens": self.config.get("llm.max_tokens")
            }
        
        return create_llm_client(config)
    
    def run(self, args: List[str] = None):
        """运行CLI"""
        parser = argparse.ArgumentParser(
            description="作业指导书智能翻译系统",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例:
  python main.py import -t ./data/bilingual.docx
  python main.py term -list
  python main.py translate -f ./doc.docx -o ./doc_cn.docx
  python main.py config -set llm.type local
            """
        )
        
        subparsers = parser.add_subparsers(dest="command", help="可用命令")
        
        # import 命令
        import_parser = subparsers.add_parser("import", help="导入历史双语文件")
        import_parser.add_argument("-t", "--target", required=True, help="文件路径")
        import_parser.add_argument("-a", "--align", default="auto", help="对齐方式")
        
        # term 命令
        term_parser = subparsers.add_parser("term", help="术语库管理")
        term_parser.add_argument("-list", action="store_true", help="列出所有术语")
        term_parser.add_argument("-add", nargs=2, metavar=("SOURCE", "TARGET"), help="添加术语")
        term_parser.add_argument("-del", metavar="SOURCE", help="删除术语")
        term_parser.add_argument("-edit", nargs=2, metavar=("SOURCE", "TARGET"), help="修改术语")
        term_parser.add_argument("-import", dest="import_csv", metavar="PATH", help="从CSV导入")
        term_parser.add_argument("-export", dest="export_csv", metavar="PATH", help="导出到CSV")
        
        # translate 命令
        trans_parser = subparsers.add_parser("translate", help="翻译文件")
        trans_parser.add_argument("-f", "--file", required=True, help="待翻译文件路径")
        trans_parser.add_argument("-o", "--output", help="输出文件路径")
        trans_parser.add_argument("-m", "--mode", default="bilingual", choices=["bilingual", "target_only"], help="输出模式")
        
        # config 命令
        config_parser = subparsers.add_parser("config", help="配置管理")
        config_parser.add_argument("-set", nargs=2, metavar=("KEY", "VALUE"), help="设置配置")
        config_parser.add_argument("-get", metavar="KEY", help="获取配置")
        config_parser.add_argument("-list", action="store_true", help="列出所有配置")
        
        # stats 命令
        subparsers.add_parser("stats", help="查看统计信息")
        
        # backup 命令
        subparsers.add_parser("backup", help="备份数据")
        
        # restore 命令
        restore_parser = subparsers.add_parser("restore", help="恢复数据")
        restore_parser.add_argument("path", help="备份文件路径")
        
        # help 命令
        subparsers.add_parser("help", help="显示帮助信息")
        
        parsed_args = parser.parse_args(args)
        
        if not parsed_args.command:
            parser.print_help()
            return
        
        # 执行命令
        handler = getattr(self, f"cmd_{parsed_args.command}", None)
        if handler:
            handler(parsed_args)
        else:
            print(f"未知命令: {parsed_args.command}")
    
    def cmd_import(self, args):
        """处理import命令"""
        from .data_importer import import_bilingual_file
        from .term_extractor import TermExtractor
        
        file_path = args.target
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        print(f"正在导入文件: {file_path}")
        
        # 导入句段
        pairs = import_bilingual_file(file_path, args.align)
        print(f"成功导入 {len(pairs)} 个句段对")
        
        # 添加到TM
        count = self.tm_db.add_segments_batch(pairs, file_path)
        print(f"成功添加 {count} 个句段到翻译记忆库")
        
        # 提取术语
        try:
            llm_client = self._get_llm_client()
            extractor = TermExtractor(llm_client)
            batch_size = self.config.get("extraction.term_batch_size", 20)
            
            print("正在提取术语...")
            terms = extractor.extract_terms(pairs, batch_size)
            
            # 添加到术语库
            term_count = self.term_db.add_terms_batch(terms, file_path)
            print(f"成功提取并添加 {term_count} 个术语")
            
        except Exception as e:
            print(f"术语提取失败: {e}")
            print("请手动添加术语或使用 term -import 从CSV导入")
    
    def cmd_term(self, args):
        """处理term命令"""
        if args.list:
            terms = self.term_db.get_all_terms()
            if not terms:
                print("术语库为空")
            else:
                print(f"术语库共 {len(terms)} 条:")
                print("-" * 50)
                for source, target in sorted(terms.items()):
                    print(f"{source} -> {target}")
        
        elif args.add:
            source, target = args.add
            if self.term_db.add_term(source, target):
                print(f"添加成功: {source} -> {target}")
            else:
                print("添加失败")
        
        elif args.del_:
            if self.term_db.delete_term(args.del_):
                print(f"删除成功: {args.del_}")
            else:
                print("删除失败或术语不存在")
        
        elif args.edit:
            source, target = args.edit
            if self.term_db.update_term(source, target):
                print(f"修改成功: {source} -> {target}")
            else:
                print("修改失败或术语不存在")
        
        elif args.import_csv:
            count = self.term_db.import_from_csv(args.import_csv)
            print(f"成功导入 {count} 个术语")
        
        elif args.export_csv:
            if self.term_db.export_to_csv(args.export_csv):
                print(f"成功导出到: {args.export_csv}")
            else:
                print("导出失败")
    
    def cmd_translate(self, args):
        """处理translate命令"""
        from .file_parser import parse_file, get_file_type
        from .translator import Translator
        from . import file_exporter
        
        file_path = args.file
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        output_path = args.output or file_exporter.get_output_path(file_path)
        
        print(f"正在翻译文件: {file_path}")
        
        try:
            # 解析文件
            texts, format_info = parse_file(file_path)
            text_list = [t.get("text", "") for t in texts]
            print(f"共 {len(text_list)} 个文本块")
            
            # 初始化翻译器
            llm_client = self._get_llm_client()
            trans_config = {
                "tm_threshold": self.config.get("translation.tm_threshold"),
                "tm_top_k": self.config.get("translation.tm_top_k")
            }
            translator = Translator(llm_client, self.term_db, self.tm_db, trans_config)
            
            # 批量翻译
            results = translator.translate_batch(text_list)
            
            # 统计
            tm_count = sum(1 for r in results if r.get("source") == "tm")
            llm_count = sum(1 for r in results if r.get("source") == "llm")
            print(f"翻译完成: {tm_count} 句来自记忆库, {llm_count} 句来自LLM")
            
            # 导出
            file_type = get_file_type(file_path)
            if file_type == "word":
                # TODO: 实现Word导出
                print("Word导出功能待实现，暂导出为TXT")
                file_exporter.export_txt(results, output_path + ".txt")
            elif file_type == "excel":
                # TODO: 实现Excel导出
                print("Excel导出功能待实现，暂导出为CSV")
                file_exporter.export_csv(results, output_path + ".csv")
            elif file_type == "txt":
                file_exporter.export_txt(results, output_path)
            elif file_type == "csv":
                file_exporter.export_csv(results, output_path)
            else:
                file_exporter.export_txt(results, output_path + ".txt")
            
            print(f"输出文件: {output_path}")
            
        except Exception as e:
            print(f"翻译失败: {e}")
    
    def cmd_config(self, args):
        """处理config命令"""
        if args.set:
            key, value = args.set
            # 尝试转换类型
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif "." in value and value.replace(".", "").isdigit():
                value = float(value)
            
            if self.config.set(key, value):
                print(f"设置成功: {key} = {value}")
            else:
                print("设置失败")
        
        elif args.get:
            value = self.config.get(args.get)
            print(f"{args.get} = {value}")
        
        elif args.list:
            import json
            print(json.dumps(self.config.get_all(), ensure_ascii=False, indent=2))
    
    def cmd_stats(self, args):
        """处理stats命令"""
        term_stats = self.term_db.get_stats()
        tm_stats = self.tm_db.get_stats()
        
        print("=" * 40)
        print("统计信息")
        print("=" * 40)
        print(f"术语库条目数: {term_stats.get('total_terms', 0)}")
        print(f"记忆库句段数: {tm_stats.get('total_segments', 0)}")
        print("=" * 40)
    
    def cmd_backup(self, args):
        """处理backup命令"""
        import zipfile
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"./backup_{timestamp}.zip"
        
        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                db_path = self.config.get("storage.db_path")
                chroma_path = self.config.get("storage.chroma_path")
                
                if os.path.exists(db_path):
                    zf.write(db_path, os.path.basename(db_path))
                
                if os.path.exists(chroma_path):
                    for root, dirs, files in os.walk(chroma_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(chroma_path))
                            zf.write(file_path, arcname)
            
            print(f"备份成功: {backup_path}")
        except Exception as e:
            print(f"备份失败: {e}")
    
    def cmd_restore(self, args):
        """处理restore命令"""
        import zipfile
        
        backup_path = args.path
        if not os.path.exists(backup_path):
            print(f"备份文件不存在: {backup_path}")
            return
        
        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall("./")
            
            print(f"恢复成功: {backup_path}")
            print("请重新启动程序以加载恢复的数据")
        except Exception as e:
            print(f"恢复失败: {e}")
    
    def cmd_help(self, args):
        """处理help命令"""
        print("""
作业指导书智能翻译系统 - 使用帮助

命令列表:
  import -t <文件路径>          导入历史双语文件，提取术语和句段
  term -list                    列出所有术语
  term -add <英文> <中文>       添加术语
  term -del <英文>              删除术语
  term -edit <英文> <新中文>    修改术语
  term -import <CSV路径>        从CSV导入术语
  term -export <CSV路径>        导出术语到CSV
  translate -f <文件路径>       翻译文件
  config -set <键> <值>         设置配置
  config -get <键>              获取配置
  stats                         查看统计信息
  backup                        备份数据
  restore <备份文件路径>        恢复数据
  help                          显示此帮助信息

示例:
  1. 导入历史双语文件:
     python main.py import -t ./data/bilingual.docx

  2. 查看术语库:
     python main.py term -list

  3. 添加术语:
     python main.py term -add "torque wrench" "扭力扳手"

  4. 翻译文件:
     python main.py translate -f ./document.docx -o ./document_cn.docx

  5. 设置本地模型路径:
     python main.py config -set llm.local_model_path ./models/qwen.gguf
        """)


def main():
    """入口函数"""
    cli = CLI()
    cli.run()


if __name__ == "__main__":
    main()
