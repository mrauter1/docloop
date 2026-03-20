from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from shared.config import Settings


SESSION_COOKIE_NAME = "triage_session"
LOGIN_CSRF_COOKIE_NAME = "triage_login_csrf"
_PASSWORD_HASHER = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def session_expires_at(
    settings: Settings,
    *,
    remember_me: bool,
    now: datetime | None = None,
) -> datetime:
    now = now or utcnow()
    if remember_me:
        return now + timedelta(days=settings.session_remember_days)
    return now + timedelta(hours=settings.session_default_hours)


def session_max_age(settings: Settings, *, remember_me: bool) -> int | None:
    if not remember_me:
        return None
    return settings.session_remember_days * 24 * 60 * 60


def should_use_secure_cookies(settings: Settings) -> bool:
    return urlparse(settings.app_base_url).scheme == "https"


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def sign_login_csrf(secret_key: str, raw_token: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def generate_login_csrf_token(secret_key: str) -> str:
    raw_token = generate_csrf_token()
    signature = sign_login_csrf(secret_key, raw_token)
    return f"{raw_token}.{signature}"


def validate_login_csrf_token(secret_key: str, token: str) -> bool:
    raw_token, separator, signature = token.partition(".")
    if not separator or not raw_token or not signature:
        return False
    expected = sign_login_csrf(secret_key, raw_token)
    return constant_time_equals(signature, expected)
