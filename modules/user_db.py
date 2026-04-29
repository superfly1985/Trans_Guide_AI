"""
用户数据库管理模块
支持用户注册、登录、权限管理和审批流程
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List


class UserDatabase:
    """用户数据库管理"""

    def __init__(self, db_path: str = "data/users.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_count INTEGER DEFAULT 0,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                reject_reason TEXT
            )
        """)

        # 登录日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 审批记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                performed_by INTEGER NOT NULL,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (performed_by) REFERENCES users(id)
            )
        """)

        # 翻译历史记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                output_filename TEXT NOT NULL,
                file_type TEXT,
                summary TEXT,
                block_count INTEGER,
                total_chars INTEGER,
                mode TEXT,
                source_lang TEXT DEFAULT 'en',
                target_lang TEXT DEFAULT 'zh',
                status TEXT DEFAULT 'processing',
                error_message TEXT,
                file_size INTEGER,
                file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON translation_history(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_created
            ON translation_history(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_status
            ON translation_history(status)
        """)

        # LLM使用统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                operation_type TEXT,
                model_name TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                response_time_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                request_size_bytes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id ON llm_usage(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_created_at ON llm_usage(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_operation ON llm_usage(operation_type)
        """)

        # 系统统计快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date DATE UNIQUE,
                total_users INTEGER DEFAULT 0,
                active_users_7d INTEGER DEFAULT 0,
                active_users_30d INTEGER DEFAULT 0,
                new_users_today INTEGER DEFAULT 0,
                total_files INTEGER DEFAULT 0,
                files_today INTEGER DEFAULT 0,
                total_words_translated INTEGER DEFAULT 0,
                total_terms INTEGER DEFAULT 0,
                new_terms_today INTEGER DEFAULT 0,
                llm_calls_today INTEGER DEFAULT 0,
                llm_tokens_today INTEGER DEFAULT 0,
                llm_errors_today INTEGER DEFAULT 0,
                db_size_bytes INTEGER DEFAULT 0,
                log_size_bytes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_stats_date ON system_stats(stat_date)
        """)

        # 术语反馈表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS term_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_source TEXT NOT NULL,
                current_target TEXT,
                suggested_target TEXT,
                feedback_type TEXT DEFAULT 'better',
                user_id INTEGER,
                status TEXT DEFAULT 'pending',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_term_feedback_status ON term_feedback(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_term_feedback_created ON term_feedback(created_at)
        """)

        conn.commit()

        # 创建默认管理员账号（如果不存在）
        self._create_default_admin()

        conn.close()

    def _create_default_admin(self):
        """创建默认管理员账号"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        if not cursor.fetchone():
            # 默认管理员: admin / admin123
            salt = secrets.token_hex(16)
            password_hash = self._hash_password('admin123', salt)

            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, role, status, approved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('admin', 'admin@local.com', password_hash, salt, 'admin', 'approved', datetime.now()))

            conn.commit()
            print("已创建默认管理员账号: admin / admin123")

        conn.close()

    def _hash_password(self, password: str, salt: str) -> str:
        """密码哈希"""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def _verify_password(self, password: str, salt: str, password_hash: str) -> bool:
        """验证密码"""
        return self._hash_password(password, salt) == password_hash

    def register(self, username: str, password: str, email: str = "") -> Dict:
        """
        用户注册
        返回: {'success': bool, 'message': str, 'user_id': int}
        """
        if len(username) < 3:
            return {'success': False, 'message': '用户名至少需要3个字符'}

        if len(password) < 6:
            return {'success': False, 'message': '密码至少需要6个字符'}

        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'message': '用户名已存在'}

        # 检查邮箱是否已存在
        if email:
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                return {'success': False, 'message': '邮箱已被注册'}

        # 创建用户
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)

        try:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, role, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, password_hash, salt, 'user', 'pending'))

            user_id = cursor.lastrowid
            conn.commit()

            return {
                'success': True,
                'message': '注册成功，请等待管理员审批',
                'user_id': user_id
            }

        except Exception as e:
            return {'success': False, 'message': f'注册失败: {str(e)}'}

        finally:
            conn.close()

    def login(self, username: str, password: str, ip_address: str = "", user_agent: str = "") -> Dict:
        """
        用户登录
        返回: {'success': bool, 'message': str, 'user': dict}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, email, password_hash, salt, role, status, last_login
            FROM users WHERE username = ?
        """, (username,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'success': False, 'message': '用户名或密码错误'}

        user = dict(row)

        # 验证密码
        if not self._verify_password(password, user['salt'], user['password_hash']):
            # 记录失败日志
            cursor.execute("""
                INSERT INTO login_logs (user_id, ip_address, user_agent, success)
                VALUES (?, ?, ?, ?)
            """, (user['id'], ip_address, user_agent, False))
            conn.commit()
            conn.close()
            return {'success': False, 'message': '用户名或密码错误'}

        # 检查账号状态
        if user['status'] == 'pending':
            conn.close()
            return {'success': False, 'message': '账号正在等待审批，请联系管理员'}

        if user['status'] == 'rejected':
            conn.close()
            return {'success': False, 'message': '账号已被拒绝，请联系管理员'}

        if user['status'] == 'disabled':
            conn.close()
            return {'success': False, 'message': '账号已被禁用，请联系管理员'}

        # 更新最后登录时间
        cursor.execute("""
            UPDATE users SET last_login = ? WHERE id = ?
        """, (datetime.now(), user['id']))

        # 记录登录日志
        cursor.execute("""
            INSERT INTO login_logs (user_id, ip_address, user_agent, success)
            VALUES (?, ?, ?, ?)
        """, (user['id'], ip_address, user_agent, True))

        conn.commit()
        conn.close()

        # 移除敏感信息
        user.pop('password_hash', None)
        user.pop('salt', None)

        return {
            'success': True,
            'message': '登录成功',
            'user': user
        }

    def approve_user(self, user_id: int, admin_id: int, reason: str = "") -> Dict:
        """
        审批通过用户
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] not in ['admin', 'manager']:
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 更新用户状态
        cursor.execute("""
            UPDATE users SET status = 'approved', approved_by = ?, approved_at = ?
            WHERE id = ?
        """, (admin_id, datetime.now(), user_id))

        # 记录审批日志
        cursor.execute("""
            INSERT INTO approval_logs (user_id, action, performed_by, reason)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'approve', admin_id, reason))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '审批通过'}

    def reject_user(self, user_id: int, admin_id: int, reason: str = "") -> Dict:
        """
        拒绝用户
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] not in ['admin', 'manager']:
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 更新用户状态
        cursor.execute("""
            UPDATE users SET status = 'rejected', approved_by = ?, approved_at = ?, reject_reason = ?
            WHERE id = ?
        """, (admin_id, datetime.now(), reason, user_id))

        # 记录审批日志
        cursor.execute("""
            INSERT INTO approval_logs (user_id, action, performed_by, reason)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'reject', admin_id, reason))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '已拒绝用户'}

    def disable_user(self, user_id: int, admin_id: int, reason: str = "") -> Dict:
        """
        禁用用户
        规则：
        1. 只有管理员可以禁用用户
        2. 不能禁用自己
        3. 不能禁用初始管理员（username='admin'）
        4. 可以禁用其他管理员
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查操作者权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 不能禁用自己
        if user_id == admin_id:
            conn.close()
            return {'success': False, 'message': '不能禁用自己'}

        # 获取目标用户信息
        cursor.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
        target_user = cursor.fetchone()
        if not target_user:
            conn.close()
            return {'success': False, 'message': '用户不存在'}

        # 不能禁用初始管理员（username='admin'）
        if target_user['username'] == 'admin':
            conn.close()
            return {'success': False, 'message': '不能禁用初始管理员'}

        cursor.execute("""
            UPDATE users SET status = 'disabled' WHERE id = ?
        """, (user_id,))

        cursor.execute("""
            INSERT INTO approval_logs (user_id, action, performed_by, reason)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'disable', admin_id, reason))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '已禁用用户'}

    def get_pending_users(self) -> List[Dict]:
        """获取待审批用户列表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, email, created_at
            FROM users WHERE status = 'pending'
            ORDER BY created_at DESC
        """)

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return users

    def get_all_users(self, admin_id: int) -> List[Dict]:
        """获取所有用户列表（管理员功能）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] not in ['admin', 'manager']:
            conn.close()
            return []

        cursor.execute("""
            SELECT u.id, u.username, u.email, u.role, u.status, u.created_at, u.last_login,
                   a.username as approved_by_name
            FROM users u
            LEFT JOIN users a ON u.approved_by = a.id
            ORDER BY u.created_at DESC
        """)

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return users

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict:
        """修改密码"""
        if len(new_password) < 6:
            return {'success': False, 'message': '新密码至少需要6个字符'}

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'success': False, 'message': '用户不存在'}

        if not self._verify_password(old_password, row['salt'], row['password_hash']):
            conn.close()
            return {'success': False, 'message': '原密码错误'}

        # 更新密码
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(new_password, salt)

        cursor.execute("""
            UPDATE users SET password_hash = ?, salt = ?, updated_at = ?
            WHERE id = ?
        """, (password_hash, salt, datetime.now(), user_id))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '密码修改成功'}

    def reset_password(self, user_id: int, admin_id: int, new_password: str) -> Dict:
        """管理员重置密码"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        salt = secrets.token_hex(16)
        password_hash = self._hash_password(new_password, salt)

        cursor.execute("""
            UPDATE users SET password_hash = ?, salt = ?, updated_at = ?
            WHERE id = ?
        """, (password_hash, salt, datetime.now(), user_id))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '密码重置成功'}

    def delete_user(self, user_id: int, admin_id: int) -> Dict:
        """删除用户"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 不能删除自己
        if user_id == admin_id:
            conn.close()
            return {'success': False, 'message': '不能删除自己的账号'}

        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        return {'success': True, 'message': '用户已删除'}

    def update_user(self, user_id: int, admin_id: int, email: str = None, role: str = None, password: str = None) -> Dict:
        """编辑用户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 检查用户是否存在
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'message': '用户不存在'}

        # 构建更新字段
        updates = []
        params = []

        if email is not None:
            updates.append("email = ?")
            params.append(email)

        if role is not None:
            updates.append("role = ?")
            params.append(role)

        if password and len(password) >= 6:
            salt = secrets.token_hex(16)
            password_hash = self._hash_password(password, salt)
            updates.append("password_hash = ?")
            params.append(password_hash)
            updates.append("salt = ?")
            params.append(salt)

        if not updates:
            conn.close()
            return {'success': False, 'message': '没有要更新的内容'}

        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.append(user_id)

        # 执行更新
        cursor.execute(f"""
            UPDATE users SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        conn.close()

        return {'success': True, 'message': '用户信息已更新'}

    def enable_user(self, user_id: int, admin_id: int) -> Dict:
        """启用用户"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查管理员权限
        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

        # 更新用户状态
        cursor.execute("""
            UPDATE users SET status = 'approved', updated_at = ?
            WHERE id = ?
        """, (datetime.now(), user_id))

        # 记录操作日志
        cursor.execute("""
            INSERT INTO approval_logs (user_id, action, performed_by, reason)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'enable', admin_id, '管理员启用用户'))

        conn.commit()
        conn.close()

        return {'success': True, 'message': '用户已启用'}

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, email, role, status, created_at, last_login
            FROM users WHERE id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_user_settings(self, user_id: int, old_password: str, new_email: str = None, new_password: str = None) -> Dict:
        """
        用户自己修改设置（邮箱和密码）

        Args:
            user_id: 用户ID
            old_password: 旧密码（用于验证身份）
            new_email: 新邮箱（可选）
            new_password: 新密码（可选）

        Returns:
            {'success': bool, 'message': str}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 获取用户信息
        cursor.execute("""
            SELECT id, username, email, password_hash, salt, role, status
            FROM users WHERE id = ?
        """, (user_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return {'success': False, 'message': '用户不存在'}

        user = dict(row)

        # 验证旧密码
        if not self._verify_password(old_password, user['salt'], user['password_hash']):
            conn.close()
            return {'success': False, 'message': '当前密码错误'}

        # 检查新邮箱是否已被使用
        if new_email and new_email != user['email']:
            cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user_id))
            if cursor.fetchone():
                conn.close()
                return {'success': False, 'message': '该邮箱已被其他用户使用'}

        # 构建更新字段
        updates = []
        params = []

        if new_email and new_email != user['email']:
            updates.append("email = ?")
            params.append(new_email)

        if new_password and len(new_password) >= 6:
            salt = secrets.token_hex(16)
            password_hash = self._hash_password(new_password, salt)
            updates.append("password_hash = ?")
            params.append(password_hash)
            updates.append("salt = ?")
            params.append(salt)

        if not updates:
            conn.close()
            return {'success': False, 'message': '没有要更新的内容'}

        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.append(user_id)

        # 执行更新
        cursor.execute(f"""
            UPDATE users SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        conn.close()

        return {'success': True, 'message': '个人设置已更新'}

    # ==================== 翻译历史记录管理 ====================

    def create_translation_record(self, user_id: int, username: str, original_filename: str,
                                  output_filename: str, file_type: str, summary: str,
                                  block_count: int, total_chars: int, mode: str,
                                  file_path: str) -> int:
        """
        创建翻译历史记录
        返回: 记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO translation_history 
            (user_id, username, original_filename, output_filename, file_type,
             summary, block_count, total_chars, mode, file_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, original_filename, output_filename, file_type,
              summary, block_count, total_chars, mode, file_path, 'processing'))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return record_id

    def complete_translation_record(self, record_id: int, file_size: int,
                                    error_message: str = None,
                                    summary: str = None) -> bool:
        """标记翻译记录为完成或失败，可选更新摘要"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if error_message:
            cursor.execute("""
                UPDATE translation_history
                SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
            """, (error_message, datetime.now(), record_id))
        else:
            if summary:
                # 更新摘要和完成状态
                cursor.execute("""
                    UPDATE translation_history
                    SET status = 'completed', file_size = ?, completed_at = ?, summary = ?
                    WHERE id = ?
                """, (file_size, datetime.now(), summary, record_id))
            else:
                cursor.execute("""
                    UPDATE translation_history
                    SET status = 'completed', file_size = ?, completed_at = ?
                    WHERE id = ?
                """, (file_size, datetime.now(), record_id))

        conn.commit()
        conn.close()

        return True

    def get_translation_history(self, user_id: int = None, page: int = 1,
                                limit: int = 20, status: str = None,
                                keyword: str = None, username: str = None) -> Dict:
        """
        获取翻译历史列表，支持模糊搜索和用户筛选
        返回: {'total': int, 'page': int, 'limit': int, 'items': List[Dict]}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if status:
            conditions.append("status = ?")
            params.append(status)

        if username:
            conditions.append("username = ?")
            params.append(username)

        if keyword:
            # 模糊搜索：文件名、摘要、用户名
            conditions.append("(original_filename LIKE ? OR summary LIKE ? OR username LIKE ?)")
            keyword_pattern = f"%{keyword}%"
            params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # 查询总数
        cursor.execute(f"""
            SELECT COUNT(*) FROM translation_history {where_clause}
        """, params)
        total = cursor.fetchone()[0]

        # 查询列表
        offset = (page - 1) * limit
        cursor.execute(f"""
            SELECT id, user_id, username, original_filename, output_filename,
                   file_type, summary, block_count, total_chars, mode, status,
                   file_size, created_at, completed_at
            FROM translation_history
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        rows = cursor.fetchall()
        items = [dict(row) for row in rows]

        conn.close()

        return {
            'total': total,
            'page': page,
            'limit': limit,
            'items': items
        }

    def get_translation_record(self, record_id: int) -> Optional[Dict]:
        """获取单条翻译记录详情"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM translation_history WHERE id = ?
        """, (record_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def delete_translation_record(self, record_id: int, user_id: int = None) -> bool:
        """删除翻译记录（可选：只能删除自己的）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if user_id:
            cursor.execute("""
                DELETE FROM translation_history WHERE id = ? AND user_id = ?
            """, (record_id, user_id))
        else:
            cursor.execute("""
                DELETE FROM translation_history WHERE id = ?
            """, (record_id,))

        conn.commit()
        conn.close()

        return True

    def get_user_today_file_count(self, user_id: int, date_str: str) -> int:
        """获取用户当天翻译文件数量"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM translation_history
            WHERE user_id = ? AND date(created_at) = date(?)
        """, (user_id, date_str))

        count = cursor.fetchone()[0]
        conn.close()

        return count

    # ========================================
    # LLM使用统计方法
    # ========================================

    def record_llm_usage(self, user_id: int, operation_type: str, model_name: str,
                        input_tokens: int = 0, output_tokens: int = 0,
                        response_time_ms: int = 0, status: str = 'success',
                        error_message: str = '', request_size_bytes: int = 0) -> bool:
        """记录LLM使用情况"""
        conn = self._get_connection()
        cursor = conn.cursor()

        total_tokens = input_tokens + output_tokens

        try:
            cursor.execute("""
                INSERT INTO llm_usage
                (user_id, operation_type, model_name, input_tokens, output_tokens,
                 total_tokens, response_time_ms, status, error_message, request_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, operation_type, model_name, input_tokens, output_tokens,
                  total_tokens, response_time_ms, status, error_message, request_size_bytes))

            conn.commit()
            return True
        except Exception as e:
            print(f"记录LLM使用失败: {e}")
            return False
        finally:
            conn.close()

    def get_llm_usage_stats(self, days: int = 30) -> Dict:
        """获取LLM使用统计"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 总调用次数
        cursor.execute("SELECT COUNT(*) FROM llm_usage")
        total_calls = cursor.fetchone()[0]

        # 今日调用
        cursor.execute("""
            SELECT COUNT(*) FROM llm_usage
            WHERE date(created_at) = date('now')
        """)
        today_calls = cursor.fetchone()[0]

        # 总token消耗
        cursor.execute("SELECT SUM(total_tokens) FROM llm_usage")
        total_tokens = cursor.fetchone()[0] or 0

        # 平均响应时间
        cursor.execute("""
            SELECT AVG(response_time_ms) FROM llm_usage
            WHERE status = 'success'
        """)
        avg_response_time = cursor.fetchone()[0] or 0

        # 错误率
        cursor.execute("""
            SELECT COUNT(*) FROM llm_usage WHERE status != 'success'
        """)
        error_count = cursor.fetchone()[0]
        error_rate = error_count / total_calls if total_calls > 0 else 0

        # 各操作类型分布
        cursor.execute("""
            SELECT operation_type, COUNT(*) as count
            FROM llm_usage
            GROUP BY operation_type
            ORDER BY count DESC
        """)
        operation_stats = {row[0]: row[1] for row in cursor.fetchall()}

        # 趋势数据
        cursor.execute("""
            SELECT date(created_at) as date, COUNT(*) as count, SUM(total_tokens) as tokens
            FROM llm_usage
            WHERE created_at >= date('now', '-{} days')
            GROUP BY date(created_at)
            ORDER BY date
        """.format(days))

        trend = []
        for row in cursor.fetchall():
            trend.append({
                'date': row[0],
                'calls': row[1],
                'tokens': row[2] or 0
            })

        conn.close()

        return {
            'total_calls': total_calls,
            'today_calls': today_calls,
            'total_tokens': total_tokens,
            'avg_response_time': round(avg_response_time, 2),
            'error_rate': round(error_rate, 4),
            'operation_stats': operation_stats,
            'trend': trend
        }

    # ========================================
    # 系统统计方法
    # ========================================

    def get_system_overview(self) -> Dict:
        """获取系统概览统计"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 用户统计
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE status = 'pending'
        """)
        pending_users = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE last_login >= date('now', '-7 days')
        """)
        active_7d = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE last_login >= date('now', '-30 days')
        """)
        active_30d = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE date(created_at) = date('now')
        """)
        new_today = cursor.fetchone()[0]

        # 文件统计
        cursor.execute("SELECT COUNT(*) FROM translation_history")
        total_files = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM translation_history
            WHERE date(created_at) = date('now')
        """)
        files_today = cursor.fetchone()[0]

        # 本月统计
        cursor.execute("""
            SELECT COUNT(*) FROM translation_history
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """)
        files_this_month = cursor.fetchone()[0]

        conn.close()

        return {
            'users': {
                'total': total_users,
                'pending': pending_users,
                'active_7d': active_7d,
                'active_30d': active_30d,
                'new_today': new_today
            },
            'files': {
                'total': total_files,
                'today': files_today,
                'this_month': files_this_month
            }
        }

    def update_user_login(self, user_id: int):
        """更新用户最后登录时间"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP,
                login_count = login_count + 1
            WHERE id = ?
        """, (user_id,))

        conn.commit()
        conn.close()


# 全局实例
user_db = UserDatabase()
