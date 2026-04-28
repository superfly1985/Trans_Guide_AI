# -*- coding: utf-8 -*-
"""
翻译记忆库（TM）数据存储模块
使用SQLite + Chroma存储
"""

import sqlite3
import os
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher


class TMDatabase:
    """翻译记忆库管理类"""
    
    def __init__(
        self,
        db_path: str = "./data/trans_guide.db",
        chroma_path: str = "./data/chroma_db"
    ):
        """
        初始化翻译记忆库
        
        Args:
            db_path: SQLite数据库路径
            chroma_path: Chroma向量库路径
        """
        self.db_path = db_path
        self.chroma_path = chroma_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(chroma_path, exist_ok=True)
        self._init_table()
        self._init_chroma()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_table(self):
        """初始化记忆库表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                translation TEXT NOT NULL,
                source_file TEXT,
                quality_score REAL DEFAULT 1.0,
                duplicate_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tm_original ON translation_memory(original)
        """)
        
        # 检查并添加缺失的列
        self._migrate_table(cursor)
        
        conn.commit()
        conn.close()
    
    def _migrate_table(self, cursor):
        """数据库迁移：添加缺失的列"""
        try:
            cursor.execute("PRAGMA table_info(translation_memory)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 添加缺失的列
            if 'updated_at' not in columns:
                cursor.execute("""
                    ALTER TABLE translation_memory 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                print("迁移: 添加 updated_at 列")
            
            if 'duplicate_count' not in columns:
                cursor.execute("""
                    ALTER TABLE translation_memory 
                    ADD COLUMN duplicate_count INTEGER DEFAULT 1
                """)
                print("迁移: 添加 duplicate_count 列")
                
            if 'quality_score' not in columns:
                cursor.execute("""
                    ALTER TABLE translation_memory 
                    ADD COLUMN quality_score REAL DEFAULT 1.0
                """)
                print("迁移: 添加 quality_score 列")
                
        except Exception as e:
            print(f"数据库迁移失败: {e}")
    
    def _init_chroma(self):
        """初始化Chroma向量库"""
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="translation_memory"
            )
        except ImportError:
            print("警告: chromadb未安装，向量检索功能不可用")
            self.chroma_client = None
            self.collection = None
    
    def _normalize_text(self, text: str) -> str:
        """标准化文本用于去重比较"""
        # 转换为小写
        text = text.lower()
        # 移除多余空格
        text = ' '.join(text.split())
        # 移除标点符号
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def check_duplicate(self, original: str, threshold: float = 0.95) -> Optional[Dict]:
        """
        检查是否存在重复或高度相似的句段
        
        Args:
            original: 原文
            threshold: 相似度阈值
            
        Returns:
            如果存在重复返回句段信息，否则None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 先检查完全匹配
        cursor.execute(
            "SELECT id, original, translation FROM translation_memory WHERE original = ?",
            (original,)
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return {
                "id": row["id"],
                "original": row["original"],
                "translation": row["translation"],
                "similarity": 1.0
            }
        
        # 检查相似内容（采样检查，避免全表扫描）
        cursor.execute(
            "SELECT id, original, translation FROM translation_memory ORDER BY RANDOM() LIMIT 100"
        )
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            similarity = self._calculate_similarity(original, row["original"])
            if similarity >= threshold:
                return {
                    "id": row["id"],
                    "original": row["original"],
                    "translation": row["translation"],
                    "similarity": similarity
                }
        
        return None
    
    def add_segment(
        self,
        original: str,
        translation: str,
        source_file: str = "",
        check_duplicate: bool = True
    ) -> Tuple[bool, str]:
        """
        添加句段到记忆库
        
        Args:
            original: 原文
            translation: 译文
            source_file: 来源文件
            check_duplicate: 是否检查重复
            
        Returns:
            (是否成功, 消息)
        """
        # 检查重复
        if check_duplicate:
            duplicate = self.check_duplicate(original)
            if duplicate:
                if duplicate["similarity"] == 1.0:
                    # 完全重复，更新计数
                    self._update_duplicate_count(duplicate["id"])
                    return True, "duplicate"
                else:
                    # 高度相似，更新为更好的版本
                    self._update_segment(duplicate["id"], original, translation)
                    return True, "updated"
        
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 添加到SQLite
            cursor.execute("""
                INSERT INTO translation_memory (original, translation, source_file, updated_at)
                VALUES (?, ?, ?, ?)
            """, (original, translation, source_file, datetime.now()))
            segment_id = cursor.lastrowid
            conn.commit()
            
            # 添加到Chroma
            if self.collection:
                try:
                    self.collection.add(
                        ids=[str(segment_id)],
                        documents=[original],
                        metadatas=[{
                            "translation": translation,
                            "source_file": source_file
                        }]
                    )
                except Exception as e:
                    print(f"添加到Chroma失败: {e}")
            
            return True, "added"
        except Exception as e:
            print(f"添加句段失败: {e}")
            return False, str(e)
        finally:
            conn.close()
    
    def _update_duplicate_count(self, segment_id: int):
        """更新重复计数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE translation_memory 
            SET duplicate_count = duplicate_count + 1, updated_at = ?
            WHERE id = ?
        """, (datetime.now(), segment_id))
        conn.commit()
        conn.close()
    
    def _update_segment(self, segment_id: int, original: str, translation: str):
        """更新句段内容"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE translation_memory 
                SET original = ?, translation = ?, updated_at = ?
                WHERE id = ?
            """, (original, translation, datetime.now(), segment_id))
            conn.commit()
            
            # 更新Chroma
            if self.collection:
                try:
                    self.collection.update(
                        ids=[str(segment_id)],
                        documents=[original],
                        metadatas=[{"translation": translation}]
                    )
                except Exception as e:
                    print(f"更新Chroma失败: {e}")
        except Exception as e:
            print(f"更新句段失败: {e}")
        finally:
            conn.close()
    
    def add_segments_batch(
        self,
        segments: List[tuple],
        source_file: str = ""
    ) -> Dict[str, int]:
        """
        批量添加句段（带去重）
        
        Args:
            segments: 句段列表 [(原文, 译文), ...]
            source_file: 来源文件
            
        Returns:
            统计信息 {"added": int, "duplicate": int, "updated": int}
        """
        stats = {"added": 0, "duplicate": 0, "updated": 0}
        
        for original, translation in segments:
            success, status = self.add_segment(original, translation, source_file)
            if success and status in stats:
                stats[status] += 1
        
        return stats
    
    def search_similar(
        self,
        text: str,
        top_k: int = 3,
        threshold: float = 0.85
    ) -> List[Dict]:
        """
        搜索相似句段
        
        Args:
            text: 查询文本
            top_k: 返回条数
            threshold: 相似度阈值
            
        Returns:
            相似句段列表 [{"original": str, "translation": str, "score": float}, ...]
        """
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[text],
                n_results=top_k
            )
            
            matches = []
            for i, doc in enumerate(results["documents"][0]):
                score = results["distances"][0][i]
                # Chroma返回的是距离，转换为相似度
                similarity = 1 - score
                if similarity >= threshold:
                    matches.append({
                        "original": doc,
                        "translation": results["metadatas"][0][i].get("translation", ""),
                        "score": similarity
                    })
            
            return matches
        except Exception as e:
            print(f"搜索相似句段失败: {e}")
            return []
    
    def find_duplicates(self, threshold: float = 0.95) -> List[Dict]:
        """
        查找所有重复句段
        
        Args:
            threshold: 相似度阈值
            
        Returns:
            重复句段组列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, original, translation FROM translation_memory")
        rows = cursor.fetchall()
        conn.close()
        
        duplicates = []
        processed = set()
        
        for i, row1 in enumerate(rows):
            if row1["id"] in processed:
                continue
            
            group = [{
                "id": row1["id"],
                "original": row1["original"],
                "translation": row1["translation"]
            }]
            
            for row2 in rows[i+1:]:
                if row2["id"] in processed:
                    continue
                
                similarity = self._calculate_similarity(row1["original"], row2["original"])
                if similarity >= threshold:
                    group.append({
                        "id": row2["id"],
                        "original": row2["original"],
                        "translation": row2["translation"],
                        "similarity": similarity
                    })
                    processed.add(row2["id"])
            
            if len(group) > 1:
                processed.add(row1["id"])
                duplicates.append(group)
        
        return duplicates
    
    def merge_duplicates(self, keep_id: int, remove_ids: List[int]):
        """
        合并重复句段
        
        Args:
            keep_id: 保留的句段ID
            remove_ids: 要删除的句段ID列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 更新保留句段的重复计数
        cursor.execute("""
            UPDATE translation_memory 
            SET duplicate_count = duplicate_count + ?, updated_at = ?
            WHERE id = ?
        """, (len(remove_ids), datetime.now(), keep_id))
        
        # 删除重复句段
        for remove_id in remove_ids:
            cursor.execute("DELETE FROM translation_memory WHERE id = ?", (remove_id,))
        
        conn.commit()
        conn.close()
        
        # 从Chroma删除
        if self.collection and remove_ids:
            try:
                self.collection.delete(ids=[str(id) for id in remove_ids])
            except Exception as e:
                print(f"从Chroma删除失败: {e}")
    
    def cleanup_low_quality(self, min_length: int = 10, max_length: int = 1000) -> int:
        """
        清理低质量句段
        
        Args:
            min_length: 最小长度
            max_length: 最大长度
            
        Returns:
            删除数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 找出低质量句段
        cursor.execute("SELECT id, original, translation FROM translation_memory")
        rows = cursor.fetchall()
        
        to_delete = []
        for row in rows:
            original = row["original"]
            translation = row["translation"]
            
            # 检查长度
            if len(original) < min_length or len(original) > max_length:
                to_delete.append(row["id"])
                continue
            
            # 检查是否包含有效字符
            if not re.search(r'[a-zA-Z]', original):
                to_delete.append(row["id"])
                continue
            
            # 检查译文质量
            if len(translation) < 2:
                to_delete.append(row["id"])
                continue
        
        # 删除低质量句段
        deleted_count = 0
        for id in to_delete:
            cursor.execute("DELETE FROM translation_memory WHERE id = ?", (id,))
            deleted_count += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # 从Chroma删除
        if self.collection and to_delete:
            try:
                self.collection.delete(ids=[str(id) for id in to_delete])
            except Exception as e:
                print(f"从Chroma删除失败: {e}")
        
        return deleted_count
    
    def delete_by_file(self, source_file: str) -> int:
        """
        按来源文件删除句段
        
        Args:
            source_file: 来源文件路径
            
        Returns:
            删除数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 获取要删除的ID
            cursor.execute(
                "SELECT id FROM translation_memory WHERE source_file = ?",
                (source_file,)
            )
            ids = [str(row["id"]) for row in cursor.fetchall()]
            
            # 从SQLite删除
            cursor.execute(
                "DELETE FROM translation_memory WHERE source_file = ?",
                (source_file,)
            )
            conn.commit()
            deleted_count = cursor.rowcount
            
            # 从Chroma删除
            if self.collection and ids:
                self.collection.delete(ids=ids)
            
            return deleted_count
        except Exception as e:
            print(f"删除句段失败: {e}")
            return 0
        finally:
            conn.close()
    
    def get_all_segments(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """
        获取所有句段
        
        Args:
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            句段列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, original, translation, source_file, quality_score, 
                   duplicate_count, created_at
            FROM translation_memory
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row["id"],
                "original": row["original"],
                "translation": row["translation"],
                "source_file": row["source_file"],
                "quality_score": row["quality_score"],
                "duplicate_count": row["duplicate_count"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 总句段数
            cursor.execute("SELECT COUNT(*) as count FROM translation_memory")
            total_segments = cursor.fetchone()["count"]
            
            # 检查是否有 duplicate_count 列
            cursor.execute("PRAGMA table_info(translation_memory)")
            columns = [row["name"] for row in cursor.fetchall()]
            
            if "duplicate_count" in columns:
                # 重复句段数
                cursor.execute("SELECT COUNT(*) as count FROM translation_memory WHERE duplicate_count > 1")
                duplicate_segments = cursor.fetchone()["count"]
                
                # 平均重复次数
                cursor.execute("SELECT AVG(duplicate_count) as avg FROM translation_memory")
                avg_duplicates = cursor.fetchone()["avg"] or 0
            else:
                duplicate_segments = 0
                avg_duplicates = 0
            
            # 来源文件数
            cursor.execute("SELECT COUNT(DISTINCT source_file) as count FROM translation_memory")
            source_files = cursor.fetchone()["count"]
            
            conn.close()
            
            return {
                "total_segments": total_segments,
                "duplicate_segments": duplicate_segments,
                "source_files": source_files,
                "avg_duplicates": round(avg_duplicates, 2)
            }
        except Exception as e:
            conn.close()
            print(f"获取统计失败: {e}")
            return {
                "total_segments": 0,
                "duplicate_segments": 0,
                "source_files": 0,
                "avg_duplicates": 0
            }
