from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.models import SessionRecord, User, UserRole
from shared.security import (
    LOGIN_CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    generate_csrf_token,
    generate_login_csrf_token,
    generate_session_token,
    hash_token,
    session_expires_at,
    session_max_age,
    should_use_secure_cookies,
    utcnow,
    validate_login_csrf_token,
)


@dataclass
class AuthContext:
    user: User
    session_record: SessionRecord


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_templates(request: Request):
    return request.app.state.templates


def get_db_session(request: Request) -> Iterator[Session]:
    session_factory = get_session_factory(request)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _get_session_record(db: Session, raw_token: str | None) -> SessionRecord | None:
    if not raw_token:
        return None
    return db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_optional_auth_context(
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthContext | None:
    record = _get_session_record(db, request.cookies.get(SESSION_COOKIE_NAME))
    if record is None:
        return None
    if _normalize_datetime(record.expires_at) <= utcnow():
        return None

    user = db.scalar(
        select(User).where(
            User.id == record.user_id,
            User.is_active.is_(True),
        )
    )
    if user is None:
        return None
    return AuthContext(user=user, session_record=record)


def require_auth_context(
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> AuthContext:
    if auth is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return auth


def require_requester(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role != UserRole.REQUESTER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester access required")
    return auth


def require_dev_ti(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role not in {UserRole.DEV_TI.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev/TI access required")
    return auth


def create_session(
    db: Session,
    *,
    user: User,
    settings: Settings,
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
    now: datetime | None = None,
) -> tuple[SessionRecord, str]:
    now = now or utcnow()
    raw_token = generate_session_token()
    record = SessionRecord(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=generate_csrf_token(),
        remember_me=remember_me,
        expires_at=session_expires_at(settings, remember_me=remember_me, now=now),
        last_seen_at=now,
        created_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user.last_login_at = now
    db.add(record)
    db.flush()
    return record, raw_token


def set_session_cookie(
    response: Response,
    *,
    settings: Settings,
    raw_token: str,
    remember_me: bool,
) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        max_age=session_max_age(settings, remember_me=remember_me),
        path="/",
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def issue_login_csrf(response: Response, settings: Settings) -> str:
    token = generate_login_csrf_token(settings.app_secret_key)
    response.set_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        path="/",
    )
    return token


def clear_login_csrf(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def validate_login_csrf(request: Request, submitted_token: str, settings: Settings) -> bool:
    cookie_token = request.cookies.get(LOGIN_CSRF_COOKIE_NAME, "")
    if not submitted_token or submitted_token != cookie_token:
        return False
    return validate_login_csrf_token(settings.app_secret_key, submitted_token)


def require_session_csrf(auth: AuthContext, submitted_token: str) -> None:
    if not submitted_token or submitted_token != auth.session_record.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def template_context(
    request: Request,
    *,
    auth: AuthContext | None,
    csrf_token: str | None = None,
    **extra: object,
) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "current_user": auth.user if auth else None,
        "session_csrf_token": auth.session_record.csrf_token if auth else "",
        "csrf_token": csrf_token if csrf_token is not None else (auth.session_record.csrf_token if auth else ""),
    }
    context.update(extra)
    return context
