"""
KSD-UAP 接入单元测试(离线,不访问网络)
覆盖: PKCE S256 已知向量、登录事务生命周期、绑定票据、UID 绑定与自动开户
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.uap_auth import UapAuth, UapAuthError, s256_challenge
from modules.user_db import UserDatabase


def make_uap() -> UapAuth:
    uap = UapAuth({
        "base_url": "https://uap.example.com",
        "project_id": "proj-trans-guide",
        "scope": "openid profile",
        "clients": {
            "production": {
                "client_id": "prod-client",
                "redirect_uri": "https://translation.example.com/auth/uap/callback",
            },
            "local": {
                "client_id": "local-client",
                "redirect_uri": "http://localhost:5556/auth/uap/callback",
            },
        },
    })
    # 预置 discovery 缓存,避免测试访问网络
    uap._discovery_cache = {
        "issuer": "https://uap.example.com",
        "authorization_endpoint": "https://uap.example.com/oauth/authorize",
        "token_endpoint": "https://uap.example.com/oauth/token",
        "jwks_uri": "https://uap.example.com/.well-known/jwks.json",
        "userinfo_endpoint": "https://uap.example.com/oauth/userinfo",
    }
    uap._discovery_at = time.time()
    return uap


class TestS256:
    def test_rfc7636_known_vector(self):
        # RFC 7636 附录 B 的已知答案
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        assert s256_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class TestStartLogin:
    def test_authorize_url_contains_pkce_params(self):
        uap = make_uap()
        url = uap.start_login("translation.example.com")
        assert url.startswith("https://uap.example.com/oauth/authorize?")
        assert "client_id=prod-client" in url
        assert "response_type=code" in url
        assert "code_challenge_method=S256" in url
        assert "redirect_uri=https%3A%2F%2Ftranslation.example.com%2Fauth%2Fuap%2Fcallback" in url

    def test_local_host_selects_local_client(self):
        uap = make_uap()
        url = uap.start_login("localhost:5556")
        assert "client_id=local-client" in url

    def test_each_login_creates_unique_transaction(self):
        uap = make_uap()
        uap.start_login("translation.example.com")
        uap.start_login("translation.example.com")
        assert len(uap._transactions) == 2

    def test_unconfigured_client_raises(self):
        uap = make_uap()
        uap.clients = {}
        with pytest.raises(UapAuthError):
            uap.start_login("translation.example.com")


class TestTransactions:
    def test_transaction_single_use(self):
        uap = make_uap()
        uap.start_login("translation.example.com")
        (state, txn) = next(iter(uap._transactions.items()))
        first = uap.consume_transaction(state)
        assert first["client_id"] == "prod-client"
        with pytest.raises(UapAuthError):
            uap.consume_transaction(state)

    def test_transaction_ttl_expiry(self):
        uap = make_uap()
        uap.start_login("translation.example.com")
        (state, txn) = next(iter(uap._transactions.items()))
        txn["created_at"] = time.time() - 11 * 60
        with pytest.raises(UapAuthError):
            uap.consume_transaction(state)


class TestBindTickets:
    def test_ticket_roundtrip_and_single_use(self):
        uap = make_uap()
        ticket = uap.create_bind_ticket({"sub": "uid-1", "name": "张三"})
        claims = uap.consume_bind_ticket(ticket)
        assert claims["sub"] == "uid-1"
        assert claims["name"] == "张三"
        with pytest.raises(UapAuthError):
            uap.consume_bind_ticket(ticket)

    def test_ticket_expiry(self):
        uap = make_uap()
        ticket = uap.create_bind_ticket({"sub": "uid-1"})
        uap._bind_tickets[ticket]["created_at"] = time.time() - 11 * 60
        with pytest.raises(UapAuthError):
            uap.consume_bind_ticket(ticket)

    def test_invalid_ticket(self):
        uap = make_uap()
        with pytest.raises(UapAuthError):
            uap.consume_bind_ticket("nonexistent")


@pytest.fixture()
def user_db(tmp_path):
    return UserDatabase(str(tmp_path / "users_test.db"))


def _register_and_login(user_db, username="old.user", password="secret123"):
    """注册 → 管理员审批 → 登录,返回 login() 结果"""
    registered = user_db.register(username, password, "")
    assert registered["success"] is True
    user_db._create_default_admin()
    admin_login = user_db.login("admin", "admin123")
    assert admin_login["success"] is True
    approved = user_db.approve_user(registered["user_id"], admin_login["user"]["id"], "test")
    assert approved["success"] is True
    return user_db.login(username, password)


class TestUserBinding:
    def test_create_uap_user_activated(self, user_db):
        result = user_db.create_uap_user("uid-abc", "zhang.san", "zhang.san@example.com")
        assert result["success"] is True
        user = user_db.get_user_by_uap_id("uid-abc")
        assert user is not None
        assert user["status"] == "approved"
        assert user["username"] == "zhang.san"

    def test_created_user_cannot_password_login(self, user_db):
        user_db.create_uap_user("uid-abc", "zhang.san", "")
        user = user_db.get_user_by_uap_id("uid-abc")
        # 自动开户的随机密码不可被猜出
        assert user_db.verify_credentials(user["username"], "admin123") is None

    def test_username_collision_suffix(self, user_db):
        user_db.create_uap_user("uid-1", "zhang.san", "")
        result = user_db.create_uap_user("uid-2", "zhang.san", "")
        assert result["success"] is True
        assert result["user"]["username"] != "zhang.san"

    def test_duplicate_email_falls_back_to_empty(self, user_db):
        user_db.create_uap_user("uid-1", "user.one", "same@example.com")
        result = user_db.create_uap_user("uid-2", "user.two", "same@example.com")
        assert result["success"] is True
        assert result["user"]["email"] in (None, "")

    def test_uid_conflict_rejected(self, user_db):
        user_db.create_uap_user("uid-1", "user.one", "")
        login_result = _register_and_login(user_db)
        # uid-1 已绑定到 user.one,对 old.user 绑定同一 UID 必须被拒绝
        result = user_db.bind_uap_user(login_result["user"]["id"], "uid-1")
        assert result["success"] is False

    def test_bind_then_session(self, user_db):
        login_result = _register_and_login(user_db)
        user_id = login_result["user"]["id"]
        bind_result = user_db.bind_uap_user(user_id, "uid-1")
        assert bind_result["success"] is True

        session = user_db.issue_session(user_id, "127.0.0.1", "pytest")
        assert session["success"] is True
        assert user_db.refresh_token_login(session["refresh_token"]) is not None
        # 旧 refresh_token 已被新会话覆盖
        assert user_db.refresh_token_login(login_result["refresh_token"]) is None

    def test_bind_requires_existing_uid(self, user_db):
        login_result = _register_and_login(user_db)
        result = user_db.bind_uap_user(login_result["user"]["id"], "")
        assert result["success"] is False

    def test_verify_credentials_rejects_pending(self, user_db):
        user_db.register("pending.user", "secret123", "")
        assert user_db.verify_credentials("pending.user", "secret123") is None
        assert user_db.verify_credentials("pending.user", "wrong") is None
