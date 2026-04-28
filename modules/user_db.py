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
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT role FROM users WHERE id = ?", (admin_id,))
        admin = cursor.fetchone()
        if not admin or admin['role'] != 'admin':
            conn.close()
            return {'success': False, 'message': '无权限执行此操作'}

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


# 全局实例
user_db = UserDatabase()
