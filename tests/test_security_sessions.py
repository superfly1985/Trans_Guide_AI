# -*- coding: utf-8 -*-
"""
安全修复验证:会话配对校验(③) + 核心接口认证与属主校验(④)

用 Flask test_client 走真实请求路径,验证:
1. 仅伪造 X-User-ID(旧攻击手法)被 401 拒绝
2. 用户ID与令牌不配对被 401 拒绝
3. 上传/批量翻译/导出/下载 未登录均被 401 拒绝
4. 用户 B 不能导出/下载用户 A 的文件(属主校验)
5. 属主本人可完整走通 上传→导出→下载
6. 普通用户访问 admin 接口被 403
"""
import io
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.user_db import UserDatabase  # noqa: E402


USER_A = "sec_test_user_a"
USER_B = "sec_test_user_b"
USER_ADMIN = "sec_test_user_admin"
PASSWORD = "sec_test_pass_123"


def _make_docx_bytes(text: str) -> bytes:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def app_ctx():
    import web.app as webapp

    yield webapp


@pytest.fixture(scope="module")
def client(app_ctx):
    app_ctx.app.config["TESTING"] = True
    with app_ctx.app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def users(app_ctx):
    """创建 A(普通)/B(普通)/管理员 三个已审批测试用户,返回 {name: (id, token)}"""
    import sqlite3

    udb: UserDatabase = app_ctx.user_db

    def find_user(name):
        conn = sqlite3.connect(str(udb.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, username, role, status FROM users WHERE username = ?", (name,)).fetchone()
        conn.close()
        return dict(row) if row else None

    result = {}
    for name in (USER_A, USER_B, USER_ADMIN):
        row = find_user(name)
        if not row:
            reg = udb.register(name, PASSWORD, None)
            assert reg["success"], reg
            row = find_user(name)
        result[name] = {"id": row["id"], "role": row["role"]}

    # 直接置为已审批;管理员角色
    import sqlite3

    conn = sqlite3.connect(str(udb.db_path))
    conn.execute("UPDATE users SET status='approved' WHERE username IN (?,?,?)",
                 (USER_A, USER_B, USER_ADMIN))
    conn.execute("UPDATE users SET role='admin' WHERE username = ?", (USER_ADMIN,))
    conn.commit()
    conn.close()

    for name in result:
        login = udb.login(name, PASSWORD, "127.0.0.1", "security-test")
        assert login["success"], login
        result[name]["token"] = login["refresh_token"]

    yield result

    # 清理测试数据
    conn = sqlite3.connect(str(udb.db_path))
    ids = ",".join(str(v["id"]) for v in result.values())
    conn.execute(f"DELETE FROM users WHERE id IN ({ids})")
    conn.execute(f"DELETE FROM login_logs WHERE user_id IN ({ids})")
    conn.execute(f"DELETE FROM upload_files WHERE user_id IN ({ids})")
    conn.execute(f"DELETE FROM translation_history WHERE user_id IN ({ids})")
    conn.commit()
    conn.close()


def auth_headers(user):
    return {"X-User-ID": str(user["id"]), "X-Session-Token": user["token"]}


def test_forged_user_id_without_token_rejected(client):
    """旧攻击手法:仅伪造 X-User-ID(如管理员 id=1)必须被拒绝"""
    for uid in ("1", "2", "999"):
        resp = client.get("/api/stats", headers={"X-User-ID": uid})
        assert resp.status_code == 401, f"X-User-ID={uid} 未被拒绝: {resp.get_json()}"


def test_mismatched_pair_rejected(client, users):
    """用户ID与令牌不配对必须被拒绝(A 的 id + B 的 token)"""
    resp = client.get("/api/stats", headers={
        "X-User-ID": str(users[USER_A]["id"]),
        "X-Session-Token": users[USER_B]["token"],
    })
    assert resp.status_code == 401


def test_valid_pair_accepted(client, users):
    resp = client.get("/api/stats", headers=auth_headers(users[USER_A]))
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_upload_requires_login(client, app_ctx, tmp_path):
    docx = _make_docx_bytes("Security test paragraph one.")
    resp = client.post("/api/upload", data={
        "file": (io.BytesIO(docx), "sec_test_noauth.docx"),
    }, content_type="multipart/form-data")
    assert resp.status_code == 401


def test_batch_translate_requires_login(client):
    resp = client.post("/api/translate/batch", json={"texts": [{"index": 0, "text": "hi"}]})
    assert resp.status_code == 401


def test_download_requires_login(client):
    resp = client.get("/api/download/whatever_20261010_01.docx")
    assert resp.status_code == 401


def test_full_flow_owner_allowed_attacker_blocked(client, users, app_ctx):
    """A 上传→导出→下载 全链路;B 无法导出/下载 A 的文件"""
    docx = _make_docx_bytes("Hello security world. This is a test block.")

    # A 登录上传
    resp = client.post("/api/upload", data={
        "file": (io.BytesIO(docx), "sec_test_owner.docx"),
    }, content_type="multipart/form-data", headers=auth_headers(users[USER_A]))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["success"] is True
    filename = body["filename"]

    # 属主已记录
    assert app_ctx.user_db.get_upload_file_owner(filename) == users[USER_A]["id"]

    # B 冒充导出 A 的文件 → 403
    resp = client.post("/api/translate/file", headers=auth_headers(users[USER_B]), json={
        "filename": filename,
        "original_filename": "sec_test_owner.docx",
        "translations": {"0": "你好安全世界。"},
        "mode": "bilingual",
    })
    assert resp.status_code == 403, resp.get_json()

    # 未认证导出 → 401
    resp = client.post("/api/translate/file", json={
        "filename": filename,
        "translations": {"0": "你好安全世界。"},
    })
    assert resp.status_code == 401

    # A 自己导出 → 成功
    resp = client.post("/api/translate/file", headers=auth_headers(users[USER_A]), json={
        "filename": filename,
        "original_filename": "sec_test_owner.docx",
        "translations": {"0": "你好安全世界。"},
        "mode": "bilingual",
    })
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["success"] is True, data
    output_name = data["download_url"].rsplit("/", 1)[-1]

    # B / 未认证 下载 A 的成果 → 401/403
    resp = client.get(f"/api/download/{output_name}", headers=auth_headers(users[USER_B]))
    assert resp.status_code in (401, 403)
    resp = client.get(f"/api/download/{output_name}")
    assert resp.status_code == 401

    # A 用查询参数方式(iframe 下载路径)下载 → 200
    resp = client.get(
        f"/api/download/{output_name}?user_id={users[USER_A]['id']}&session_token={users[USER_A]['token']}")
    assert resp.status_code == 200, resp.get_json()

    # 管理员可下载(管理豁免)
    resp = client.get(f"/api/download/{output_name}", headers=auth_headers(users[USER_ADMIN]))
    assert resp.status_code == 200

    # 清理测试产生的文件
    try:
        (app_ctx.UPLOAD_DIR / filename).unlink(missing_ok=True)
        (app_ctx.OUTPUT_DIR / output_name).unlink(missing_ok=True)
    except OSError:
        pass


def test_admin_endpoints_forbidden_for_normal_user(client, users):
    resp = client.get("/api/admin/users", headers=auth_headers(users[USER_A]))
    assert resp.status_code == 403
    resp = client.get("/api/admin/users", headers=auth_headers(users[USER_ADMIN]))
    assert resp.status_code == 200


def test_get_current_user_requires_valid_session(client, users):
    resp = client.get("/api/auth/user", headers={"X-User-ID": "1"})
    assert resp.status_code == 401
    resp = client.get("/api/auth/user", headers=auth_headers(users[USER_A]))
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == USER_A
