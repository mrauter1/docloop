from __future__ import annotations

from shared.config import Settings
from shared.security import (
    generate_login_csrf_token,
    hash_password,
    hash_token,
    session_max_age,
    validate_login_csrf_token,
    verify_password,
)


def make_settings() -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "https://triage.example.test",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
        }
    )


def test_password_hash_round_trip() -> None:
    hashed = hash_password("hunter2")

    assert hashed != "hunter2"
    assert verify_password(hashed, "hunter2") is True
    assert verify_password(hashed, "wrong") is False


def test_login_csrf_token_round_trip() -> None:
    token = generate_login_csrf_token("secret")

    assert validate_login_csrf_token("secret", token) is True
    assert validate_login_csrf_token("secret", f"{token}x") is False


def test_session_max_age_only_for_remember_me() -> None:
    settings = make_settings()

    assert session_max_age(settings, remember_me=False) is None
    assert session_max_age(settings, remember_me=True) == 30 * 24 * 60 * 60


def test_hash_token_is_sha256_hex() -> None:
    digest = hash_token("plain-token")

    assert len(digest) == 64
    assert digest != "plain-token"
