"""轻量用户鉴权：JSON 用户文件 + HMAC 签名 Cookie，不引入外部数据库。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import Cookie, HTTPException, Response

COOKIE_NAME = "emotion_auth"
TOKEN_TTL_SECONDS = 7 * 24 * 3600
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

# 登录防爆破：按用户名 / IP 记录失败次数，超限临时锁定
LOGIN_MAX_FAILS_USER = 5
LOGIN_MAX_FAILS_IP = 20
LOGIN_LOCK_SECONDS = 15 * 60

_lock = threading.Lock()


@dataclass
class AuthUser:
    user_id: str
    username: str


class LoginGuard:
    """轻量登录失败锁定状态，落盘到 login_attempts.json，重启后仍生效。"""

    def __init__(self, path: Path):
        self.path = path
        self._io_lock = threading.Lock()

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"users": {}, "ips": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"users": {}, "ips": {}}
        data.setdefault("users", {})
        data.setdefault("ips", {})
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _entry_locked(entry: dict, now: float) -> Optional[float]:
        if not entry:
            return None
        until = float(entry.get("locked_until") or 0)
        if until > now:
            return until - now
        return None

    def check_locked(self, username: str, client_ip: str) -> None:
        username = (username or "").strip().lower()
        client_ip = (client_ip or "").strip() or "unknown"
        now = time.time()
        with self._io_lock:
            data = self._load()
            user_left = self._entry_locked(data["users"].get(username, {}), now)
            ip_left = self._entry_locked(data["ips"].get(client_ip, {}), now)

        if user_left is not None:
            minutes = max(1, int(user_left // 60) + (1 if user_left % 60 else 0))
            raise HTTPException(
                429,
                f"登录失败次数过多，账号已临时锁定，请约 {minutes} 分钟后再试",
            )
        if ip_left is not None:
            minutes = max(1, int(ip_left // 60) + (1 if ip_left % 60 else 0))
            raise HTTPException(
                429,
                f"当前网络登录尝试过于频繁，已临时限制，请约 {minutes} 分钟后再试",
            )

    def record_failure(self, username: str, client_ip: str) -> None:
        username = (username or "").strip().lower()
        client_ip = (client_ip or "").strip() or "unknown"
        now = time.time()
        with self._io_lock:
            data = self._load()

            def bump(bucket: dict, key: str, max_fails: int) -> None:
                entry = bucket.get(key) or {}
                # 过期锁定自动重置计数
                if float(entry.get("locked_until") or 0) <= now:
                    if float(entry.get("locked_until") or 0) > 0:
                        entry = {"fails": 0}
                fails = int(entry.get("fails") or 0) + 1
                entry["fails"] = fails
                entry["last_fail_at"] = now
                if fails >= max_fails:
                    entry["locked_until"] = now + LOGIN_LOCK_SECONDS
                    entry["fails"] = 0
                bucket[key] = entry

            bump(data["users"], username, LOGIN_MAX_FAILS_USER)
            bump(data["ips"], client_ip, LOGIN_MAX_FAILS_IP)
            self._save(data)

    def record_success(self, username: str, client_ip: str) -> None:
        username = (username or "").strip().lower()
        client_ip = (client_ip or "").strip() or "unknown"
        with self._io_lock:
            data = self._load()
            data["users"].pop(username, None)
            # 成功登录清空该 IP 失败计数，避免误伤同出口的正常用户
            data["ips"].pop(client_ip, None)
            self._save(data)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000
    ).hex()
    return f"pbkdf2${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000
    ).hex()
    return hmac.compare_digest(candidate, digest)


class AuthStore:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.users_path = storage_dir / "users.json"
        self.secret_path = storage_dir / "auth_secret.key"
        self.login_guard = LoginGuard(storage_dir / "login_attempts.json")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _load_secret(self) -> bytes:
        if self.secret_path.is_file():
            data = self.secret_path.read_bytes().strip()
            if data:
                return data
        secret = secrets.token_bytes(32)
        self.secret_path.write_bytes(secret)
        try:
            self.secret_path.chmod(0o600)
        except OSError:
            pass
        return secret

    def _read_users(self) -> dict:
        if not self.users_path.is_file():
            return {"users": []}
        try:
            return json.loads(self.users_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"users": []}

    def _write_users(self, data: dict) -> None:
        tmp = self.users_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.users_path)

    def ensure_default_admin(self, username: str = "account", password: str = "password") -> Optional[str]:
        """首次启动且无用户时创建默认管理员，返回初始密码；已有用户则返回 None。"""
        with _lock:
            data = self._read_users()
            if data.get("users"):
                return None
            user = {
                "user_id": secrets.token_hex(8),
                "username": username,
                "password_hash": _hash_password(password),
                "created_at": int(time.time()),
            }
            data["users"] = [user]
            self._write_users(data)
            return password

    def register(self, username: str, password: str) -> AuthUser:
        """内部建号用（不对外提供注册 API）；运维可直接改 users.json。"""
        username = (username or "").strip()
        password = password or ""
        if not USERNAME_RE.match(username):
            raise HTTPException(400, "用户名需为 3-32 位字母、数字或下划线")
        if len(password) < 6:
            raise HTTPException(400, "密码至少 6 位")

        with _lock:
            data = self._read_users()
            if any(u.get("username") == username for u in data.get("users", [])):
                raise HTTPException(409, "用户名已存在")
            user = {
                "user_id": secrets.token_hex(8),
                "username": username,
                "password_hash": _hash_password(password),
                "created_at": int(time.time()),
            }
            data.setdefault("users", []).append(user)
            self._write_users(data)
            return AuthUser(user_id=user["user_id"], username=user["username"])

    def login(self, username: str, password: str, client_ip: str = "") -> AuthUser:
        username = (username or "").strip()
        client_ip = client_ip or "unknown"

        # 锁定检查在密码校验之前，避免被用来探测账号是否存在
        self.login_guard.check_locked(username, client_ip)

        matched: Optional[AuthUser] = None
        with _lock:
            data = self._read_users()
            for user in data.get("users", []):
                if user.get("username") == username:
                    if _verify_password(password or "", user.get("password_hash", "")):
                        matched = AuthUser(user_id=user["user_id"], username=user["username"])
                        break
                    break

        if matched is None:
            self.login_guard.record_failure(username, client_ip)
            raise HTTPException(401, "用户名或密码错误")

        self.login_guard.record_success(username, client_ip)
        return matched

    def create_token(self, user: AuthUser) -> str:
        secret = self._load_secret()
        payload = {
            "uid": user.user_id,
            "un": user.username,
            "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        }
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(secret, raw, hashlib.sha256).digest()
        return f"{_b64e(raw)}.{_b64e(sig)}"

    def parse_token(self, token: Optional[str]) -> Optional[AuthUser]:
        if not token:
            return None
        try:
            raw_b64, sig_b64 = token.split(".", 1)
            raw = _b64d(raw_b64)
            sig = _b64d(sig_b64)
        except ValueError:
            return None

        secret = self._load_secret()
        expected = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if int(payload.get("exp", 0)) < time.time():
            return None
        user_id = payload.get("uid")
        username = payload.get("un")
        if not user_id or not username:
            return None
        return AuthUser(user_id=str(user_id), username=str(username))

    def set_auth_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=TOKEN_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            path="/",
        )

    def clear_auth_cookie(self, response: Response) -> None:
        response.delete_cookie(COOKIE_NAME, path="/")


_store: Optional[AuthStore] = None


def get_auth_store(storage_dir: Path | None = None) -> AuthStore:
    global _store
    if _store is None:
        if storage_dir is None:
            storage_dir = Path(__file__).resolve().parent.parent / "storage"
        _store = AuthStore(storage_dir)
    return _store


def require_user(
    emotion_auth: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> AuthUser:
    user = get_auth_store().parse_token(emotion_auth)
    if user is None:
        raise HTTPException(401, "未登录或登录已过期")
    return user


def optional_user(
    emotion_auth: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> Optional[AuthUser]:
    return get_auth_store().parse_token(emotion_auth)
