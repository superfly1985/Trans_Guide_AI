"""
KSD-UAP 统一登录模块
OAuth 2.0 Authorization Code + S256 PKCE,服务端事务管理与 JWT 验证

职责边界:UAP 负责认证与 Token 签发;本模块只完成协议交互与校验,
账号绑定、角色与数据权限由 user_db 与业务层负责。
"""

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt
from jwt import PyJWKClient

TRANSACTION_TTL = 10 * 60
BIND_TICKET_TTL = 10 * 60
DISCOVERY_TTL = 60 * 60
HTTP_TIMEOUT = 10

BIND_TICKET_CLAIM_KEYS = ("sub", "name", "preferred_username", "email", "employee_number", "groups")


class UapAuthError(Exception):
    """可安全展示给用户的 UAP 认证错误(不含敏感凭据)"""


def s256_challenge(verifier: str) -> str:
    """RFC 7636 S256 code_challenge"""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _cleanup_expired(store: dict, now: float) -> None:
    expired = [key for key, value in store.items() if now - value["created_at"] > _entry_ttl(value)]
    for key in expired:
        store.pop(key, None)


def _entry_ttl(value: dict) -> int:
    return value.get("ttl", TRANSACTION_TTL)


class UapAuth:
    """KSD-UAP 授权码 + PKCE 登录,事务状态仅保存在服务端内存"""

    def __init__(self, config: dict):
        self.base_url = (config.get("base_url") or "").rstrip("/")
        self.project_id = config.get("project_id") or ""
        self.scope = config.get("scope") or "openid profile"
        self.clients = config.get("clients") or {}
        self._discovery_cache = None
        self._discovery_at = 0.0
        self._transactions = {}
        self._bind_tickets = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(
            self.base_url
            and self.project_id
            and any(client.get("client_id") for client in self.clients.values())
        )

    def client_for_host(self, host: str) -> dict:
        """按请求 Host 选择客户端:localhost 走本地客户端,其余走生产客户端"""
        hostname = (host or "").split(":")[0].lower()
        key = "local" if hostname in ("localhost", "127.0.0.1") else "production"
        client = self.clients.get(key) or {}
        if not client.get("client_id") or not client.get("redirect_uri"):
            raise UapAuthError("当前环境未配置 UAP 客户端")
        return client

    def start_login(self, host: str) -> str:
        """创建一次性登录事务,返回 UAP 授权页完整地址"""
        client = self.client_for_host(host)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        now = time.time()
        with self._lock:
            _cleanup_expired(self._transactions, now)
            self._transactions[state] = {
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": client["redirect_uri"],
                "client_id": client["client_id"],
                "created_at": now,
                "ttl": TRANSACTION_TTL,
            }
        discovery = self._get_discovery()
        endpoint = discovery.get("authorization_endpoint") or f"{self.base_url}/oauth/authorize"
        params = urllib.parse.urlencode({
            "client_id": client["client_id"],
            "redirect_uri": client["redirect_uri"],
            "response_type": "code",
            "scope": self.scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": s256_challenge(code_verifier),
            "code_challenge_method": "S256",
        })
        return f"{endpoint}?{params}"

    def consume_transaction(self, state: str) -> dict:
        """校验并移除一次性登录事务(单次有效)"""
        if not state:
            raise UapAuthError("登录状态无效，请重新发起登录")
        with self._lock:
            _cleanup_expired(self._transactions, time.time())
            transaction = self._transactions.pop(state, None)
        if transaction is None:
            raise UapAuthError("登录事务不存在或已过期，请重新发起登录")
        return transaction

    def complete_login(self, state: str, code: str) -> dict:
        """校验并消费事务,兑换授权码,验证 id_token,返回 claims"""
        if not code:
            raise UapAuthError("回调参数缺失，请重新发起登录")
        transaction = self.consume_transaction(state)

        discovery = self._get_discovery()
        token_endpoint = discovery.get("token_endpoint") or f"{self.base_url}/oauth/token"
        payload = self._post_form(token_endpoint, {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": transaction["client_id"],
            "redirect_uri": transaction["redirect_uri"],
            "code_verifier": transaction["code_verifier"],
        })
        id_token = payload.get("id_token")
        if not id_token:
            raise UapAuthError("UAP 未返回 id_token，已拒绝登录")
        claims = self._verify_id_token(id_token, transaction["nonce"])
        userinfo = self._get_userinfo(payload.get("access_token"), discovery)
        if userinfo and userinfo.get("sub") == claims.get("sub"):
            for key in ("name", "preferred_username", "email", "employee_number", "groups"):
                if userinfo.get(key) is not None:
                    claims[key] = userinfo[key]
        return claims

    def _verify_id_token(self, token: str, expected_nonce: str) -> dict:
        discovery = self._get_discovery()
        jwks_uri = discovery.get("jwks_uri") or f"{self.base_url}/.well-known/jwks.json"
        issuer = discovery.get("issuer") or self.base_url
        try:
            jwk_client = PyJWKClient(jwks_uri, cache_keys=True)
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.project_id,
                issuer=issuer,
            )
        except jwt.PyJWTError:
            raise UapAuthError("Token 校验失败，已拒绝登录")
        if not claims.get("sub"):
            raise UapAuthError("Token 缺少 sub，已拒绝登录")
        if claims.get("nonce") != expected_nonce:
            raise UapAuthError("Nonce 校验失败，已拒绝登录")
        return claims

    def _get_userinfo(self, access_token: str, discovery: dict):
        if not access_token:
            return None
        endpoint = discovery.get("userinfo_endpoint") or f"{self.base_url}/oauth/userinfo"
        try:
            request = urllib.request.Request(endpoint, headers={
                "Authorization": f"Bearer {access_token}",
            })
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def _post_form(self, url: str, fields: dict) -> dict:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise UapAuthError(f"授权码兑换失败（HTTP {error.code}），请重新发起登录")
        except (urllib.error.URLError, TimeoutError):
            raise UapAuthError("无法连接 UAP 服务，请稍后重试")
        except (ValueError, json.JSONDecodeError):
            raise UapAuthError("UAP 响应格式异常，已拒绝登录")

    def _get_discovery(self) -> dict:
        now = time.time()
        if self._discovery_cache is not None and now - self._discovery_at < DISCOVERY_TTL:
            return self._discovery_cache
        url = f"{self.base_url}/.well-known/openid-configuration"
        try:
            request = urllib.request.Request(url)
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                discovery = json.loads(response.read().decode("utf-8"))
            self._discovery_cache = discovery
            self._discovery_at = now
            return discovery
        except Exception:
            if self._discovery_cache is not None:
                return self._discovery_cache
            return {}

    # ---------- 首登绑定事务(未绑定 UID 时使用) ----------

    def create_bind_ticket(self, claims: dict) -> str:
        ticket = secrets.token_urlsafe(32)
        slim = {key: claims.get(key) for key in BIND_TICKET_CLAIM_KEYS}
        with self._lock:
            _cleanup_expired(self._bind_tickets, time.time())
            self._bind_tickets[ticket] = {
                "claims": slim,
                "created_at": time.time(),
                "ttl": BIND_TICKET_TTL,
            }
        return ticket

    def consume_bind_ticket(self, ticket: str) -> dict:
        if not ticket:
            raise UapAuthError("绑定会话无效，请重新发起登录")
        with self._lock:
            _cleanup_expired(self._bind_tickets, time.time())
            entry = self._bind_tickets.pop(ticket, None)
        if entry is None:
            raise UapAuthError("绑定会话不存在或已过期，请重新发起登录")
        return entry["claims"]
