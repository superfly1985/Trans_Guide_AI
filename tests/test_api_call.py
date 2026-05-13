# -*- coding: utf-8 -*-
"""测试导入API调用"""
import sys
sys.path.insert(0, ".")

from web.app import app, user_db

with app.test_client() as client:
    # 获取 admin 用户ID - 直接查数据库
    import sqlite3
    conn = sqlite3.connect("./data/users.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    row = cursor.fetchone()
    user_id = row["id"] if row else 1
    conn.close()
    print(f"Admin user_id: {user_id}")
    
    # 调用导入
    resp = client.post('/api/import/process',
        json={
            "filename": "test.docx",
            "filepath": "/root/Trans_Guide_AI/uploads/20260512_164208_2050459_Monthly_Quality_Reports_2024.07.16_OK.doc",
            "pairs": [
                {"source": "hello world", "target": "你好世界"},
                {"source": "Quality Report", "target": "质量报告"}
            ],
            "terms": [
                {"english": "Quality Report", "chinese": "质量报告", "category": "质量"}
            ]
        },
        headers={"X-User-ID": str(user_id)}
    )
    print(f"Import Status: {resp.status_code}")
    print(f"Import Response: {resp.get_json()}")
