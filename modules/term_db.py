# -*- coding: utf-8 -*-
"""
术语库（TB）数据存储模块
使用SQLite存储
"""

import sqlite3
import os
import csv
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class TermDatabase:
    """术语库管理类"""
    
    def __init__(self, db_path: str = "./data/trans_guide.db"):
        """
        初始化术语库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_table(self):
        """初始化术语表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 术语表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT NOT NULL UNIQUE,
                target_term TEXT NOT NULL,
                category TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 检查并添加缺失的列（迁移）
        cursor.execute("PRAGMA table_info(terms)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        if 'category' not in existing_columns:
            cursor.execute("ALTER TABLE terms ADD COLUMN category TEXT DEFAULT ''")
            print("添加列: category")
        
        if 'tags' not in existing_columns:
            cursor.execute("ALTER TABLE terms ADD COLUMN tags TEXT DEFAULT ''")
            print("添加列: tags")
        
        if 'notes' not in existing_columns:
            cursor.execute("ALTER TABLE terms ADD COLUMN notes TEXT DEFAULT ''")
            print("添加列: notes")
        
        # 分类表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS term_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 术语使用反馈表 - 用于记录用户修正，优化推断
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS term_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT NOT NULL,
                suggested_translation TEXT NOT NULL,
                context TEXT DEFAULT '',
                file_type TEXT DEFAULT '',
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 术语使用统计表 - 记录每个译词被使用的频率
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS term_usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT NOT NULL,
                translation TEXT NOT NULL,
                use_count INTEGER DEFAULT 1,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_term, translation)
            )
        """)

        conn.commit()
        conn.close()
    
    def add_term(self, source: str, target: str, source_file: str = "", 
                 category: str = "", tags: str = "", notes: str = "") -> bool:
        """
        添加术语
        
        Args:
            source: 英文术语
            target: 中文译法
            source_file: 来源文件
            category: 分类
            tags: 标签（逗号分隔）
            notes: 备注
            
        Returns:
            是否添加成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO terms (source_term, target_term, category, tags, notes, source_file, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_term) DO UPDATE SET
                    target_term = excluded.target_term,
                    category = excluded.category,
                    tags = excluded.tags,
                    notes = excluded.notes,
                    source_file = excluded.source_file,
                    updated_at = excluded.updated_at
            """, (source, target, category, tags, notes, source_file, datetime.now()))
            conn.commit()
            return True
        except Exception as e:
            print(f"添加术语失败: {e}")
            return False
        finally:
            conn.close()
    
    def add_terms_batch(self, terms: Dict[str, str], source_file: str = "") -> int:
        """
        批量添加术语
        
        Args:
            terms: 术语字典 {英文: 中文}
            source_file: 来源文件
            
        Returns:
            添加成功的数量
        """
        count = 0
        for source, target in terms.items():
            if self.add_term(source, target, source_file):
                count += 1
        return count
    
    def get_term(self, source: str) -> Optional[str]:
        """
        查询术语译法

        Args:
            source: 英文术语

        Returns:
            中文译法，不存在返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT target_term FROM terms WHERE source_term = ?",
            (source,)
        )
        row = cursor.fetchone()
        conn.close()
        return row["target_term"] if row else None

    def get_term_with_context(self, source: str, text_context: str) -> Optional[str]:
        """
        根据上下文获取最合适的术语译法

        Args:
            source: 英文术语
            text_context: 待翻译的文本片段（用于推断上下文）

        Returns:
            最合适的中文译法，不存在返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT target_term FROM terms WHERE source_term = ?",
            (source,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        target = row["target_term"]

        # 如果有多个译词（用 | 分隔），根据上下文选择
        if '|' in target:
            from .context_resolver import ContextResolver
            translations = target.split('|')
            return ContextResolver.resolve(source, translations, text_context)

        return target
    
    def get_term_detail(self, source: str) -> Optional[Dict]:
        """
        获取术语详细信息
        
        Args:
            source: 英文术语
            
        Returns:
            术语详细信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT source_term, target_term, category, tags, notes, source_file, 
                      created_at, updated_at 
               FROM terms WHERE source_term = ?""",
            (source,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "source": row["source_term"],
                "target": row["target_term"],
                "category": row["category"],
                "tags": row["tags"],
                "notes": row["notes"],
                "source_file": row["source_file"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None
    
    def get_all_terms(self) -> Dict[str, str]:
        """
        获取所有术语
        
        Returns:
            术语字典 {英文: 中文}
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source_term, target_term FROM terms")
        rows = cursor.fetchall()
        conn.close()
        return {row["source_term"]: row["target_term"] for row in rows}
    
    def get_all_terms_with_details(self) -> List[Dict]:
        """
        获取所有术语详细信息
        
        Returns:
            术语详细信息列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_term, target_term, category, tags, notes, source_file,
                   created_at, updated_at
            FROM terms
            ORDER BY updated_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "source": row["source_term"],
                "target": row["target_term"],
                "category": row["category"],
                "tags": row["tags"],
                "notes": row["notes"],
                "source_file": row["source_file"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        ]
    
    def delete_term(self, source: str) -> bool:
        """
        删除术语
        
        Args:
            source: 英文术语
            
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM terms WHERE source_term = ?",
                (source,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除术语失败: {e}")
            return False
        finally:
            conn.close()
    
    def update_term(self, source: str, target: str = None, category: str = None,
                    tags: str = None, notes: str = None) -> bool:
        """
        修改术语
        
        Args:
            source: 英文术语（作为标识）
            target: 新中文译法
            category: 新分类
            tags: 新标签
            notes: 新备注
            
        Returns:
            是否修改成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 构建更新字段
            updates = []
            params = []
            
            if target is not None:
                updates.append("target_term = ?")
                params.append(target)
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if tags is not None:
                updates.append("tags = ?")
                params.append(tags)
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if not updates:
                return True
            
            updates.append("updated_at = ?")
            params.append(datetime.now())
            params.append(source)
            
            sql = f"UPDATE terms SET {', '.join(updates)} WHERE source_term = ?"
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"修改术语失败: {e}")
            return False
        finally:
            conn.close()
    
    def search_terms(self, keyword: str) -> List[Dict]:
        """
        搜索术语
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的术语列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        keyword_like = f"%{keyword}%"
        cursor.execute("""
            SELECT source_term, target_term, category, tags, notes
            FROM terms
            WHERE source_term LIKE ? OR target_term LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
        """, (keyword_like, keyword_like, keyword_like))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "source": row["source_term"],
                "target": row["target_term"],
                "category": row["category"],
                "tags": row["tags"],
                "notes": row["notes"]
            }
            for row in rows
        ]
    
    def get_terms_by_category(self, category: str) -> List[Dict]:
        """
        按分类获取术语
        
        Args:
            category: 分类名称
            
        Returns:
            术语列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_term, target_term, category, tags, notes
            FROM terms
            WHERE category = ?
            ORDER BY updated_at DESC
        """, (category,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "source": row["source_term"],
                "target": row["target_term"],
                "category": row["category"],
                "tags": row["tags"],
                "notes": row["notes"]
            }
            for row in rows
        ]
    
    def get_categories(self) -> List[Dict]:
        """
        获取所有分类
        
        Returns:
            分类列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.name, c.description, COUNT(t.id) as term_count
            FROM term_categories c
            LEFT JOIN terms t ON c.name = t.category
            GROUP BY c.name
            ORDER BY c.name
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "name": row["name"],
                "description": row["description"],
                "term_count": row["term_count"]
            }
            for row in rows
        ]
    
    def add_category(self, name: str, description: str = "") -> bool:
        """
        添加分类
        
        Args:
            name: 分类名称
            description: 分类描述
            
        Returns:
            是否添加成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO term_categories (name, description)
                VALUES (?, ?)
            """, (name, description))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 分类已存在
            return False
        except Exception as e:
            print(f"添加分类失败: {e}")
            return False
        finally:
            conn.close()
    
    def delete_category(self, name: str) -> bool:
        """
        删除分类
        
        Args:
            name: 分类名称
            
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 先将该分类下的术语分类置空
            cursor.execute("UPDATE terms SET category = '' WHERE category = ?", (name,))
            # 删除分类
            cursor.execute("DELETE FROM term_categories WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除分类失败: {e}")
            return False
        finally:
            conn.close()
    
    def import_from_csv(self, csv_path: str, category: str = "") -> int:
        """
        从CSV导入术语
        
        Args:
            csv_path: CSV文件路径
            category: 默认分类
            
        Returns:
            导入数量
        """
        count = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    if self.add_term(row[0], row[1], category=category):
                        count += 1
        return count
    
    def export_to_csv(self, csv_path: str, category: str = None) -> bool:
        """
        导出术语到CSV
        
        Args:
            csv_path: CSV文件路径
            category: 指定分类，None表示全部
            
        Returns:
            是否导出成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if category:
                cursor.execute("""
                    SELECT source_term, target_term, category, tags, notes
                    FROM terms WHERE category = ?
                    ORDER BY source_term
                """, (category,))
            else:
                cursor.execute("""
                    SELECT source_term, target_term, category, tags, notes
                    FROM terms ORDER BY source_term
                """)
            
            rows = cursor.fetchall()
            conn.close()
            
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["英文术语", "中文译法", "分类", "标签", "备注"])
                for row in rows:
                    writer.writerow([
                        row["source_term"],
                        row["target_term"],
                        row["category"],
                        row["tags"],
                        row["notes"]
                    ])
            return True
        except Exception as e:
            print(f"导出术语失败: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 总术语数
        cursor.execute("SELECT COUNT(*) as count FROM terms")
        total_terms = cursor.fetchone()["count"]
        
        # 分类数
        cursor.execute("SELECT COUNT(*) as count FROM term_categories")
        category_count = cursor.fetchone()["count"]
        
        # 各分类术语数
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM terms 
            WHERE category != ''
            GROUP BY category
        """)
        category_stats = {row["category"]: row["count"] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            "total_terms": total_terms,
            "category_count": category_count,
            "category_stats": category_stats
        }
    
    def search_terms_in_text(self, text: str) -> Dict[str, str]:
        """
        在文本中搜索匹配的术语
        
        Args:
            text: 待搜索文本
            
        Returns:
            匹配到的术语 {英文: 中文}
        """
        all_terms = self.get_all_terms()
        matched = {}
        text_lower = text.lower()
        
        # 按术语长度降序排序，优先匹配长术语
        sorted_terms = sorted(all_terms.items(), key=lambda x: len(x[0]), reverse=True)
        
        for source, target in sorted_terms:
            # 大小写不敏感匹配
            if source.lower() in text_lower:
                matched[source] = target

        return matched

    # ==================== 术语反馈和统计 ====================

    def record_term_feedback(self, source: str, suggested: str, context: str = "",
                            file_type: str = "", user_id: int = None) -> bool:
        """
        记录术语使用反馈（用户修正）

        Args:
            source: 原文术语
            suggested: 用户建议的译词
            context: 使用上下文
            file_type: 文件类型
            user_id: 用户ID

        Returns:
            是否记录成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO term_feedback (source_term, suggested_translation, context, file_type, user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (source, suggested, context, file_type, user_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"记录术语反馈失败: {e}")
            return False
        finally:
            conn.close()

    def update_term_usage_stats(self, source: str, translation: str) -> bool:
        """
        更新术语使用统计

        Args:
            source: 原文术语
            translation: 实际使用的译词

        Returns:
            是否更新成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO term_usage_stats (source_term, translation, use_count, last_used_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(source_term, translation) DO UPDATE SET
                    use_count = use_count + 1,
                    last_used_at = excluded.last_used_at
            """, (source, translation, datetime.now()))
            conn.commit()
            return True
        except Exception as e:
            print(f"更新术语使用统计失败: {e}")
            return False
        finally:
            conn.close()

    def get_term_usage_stats(self, source: str) -> Dict[str, int]:
        """
        获取术语使用统计

        Args:
            source: 原文术语

        Returns:
            各译词使用次数字典 {译词: 次数}
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT translation, use_count
            FROM term_usage_stats
            WHERE source_term = ?
            ORDER BY use_count DESC
        """, (source,))
        rows = cursor.fetchall()
        conn.close()
        return {row["translation"]: row["use_count"] for row in rows}

    def get_popular_translations(self, source: str, translations: List[str]) -> List[str]:
        """
        根据使用统计排序译词（使用频率高的优先）

        Args:
            source: 原文术语
            translations: 所有可能的译词列表

        Returns:
            按使用频率排序的译词列表
        """
        stats = self.get_term_usage_stats(source)
        if not stats:
            return translations

        # 按使用频率排序
        sorted_trans = sorted(translations, key=lambda t: stats.get(t, 0), reverse=True)
        return sorted_trans
