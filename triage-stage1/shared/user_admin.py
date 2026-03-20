from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models import User, UserRole
from shared.security import hash_password, normalize_email


class UserAdminError(RuntimeError):
    """Raised when a user administration command cannot be completed."""


def _require_role(role: str) -> str:
    allowed = {item.value for item in UserRole}
    if role not in allowed:
        joined = ", ".join(sorted(allowed))
        raise UserAdminError(f"Invalid role '{role}'. Allowed roles: {joined}")
    return role


def create_user_account(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str,
) -> User:
    normalized_email = normalize_email(email)
    role = _require_role(role)
    existing = session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise UserAdminError(f"User already exists: {normalized_email}")

    user = User(
        email=normalized_email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, *, email: str) -> User:
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise UserAdminError(f"User not found: {normalized_email}")
    return user


def set_user_password(session: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(session, email=email)
    user.password_hash = hash_password(password)
    session.flush()
    return user


def deactivate_user_account(session: Session, *, email: str) -> User:
    user = get_user_by_email(session, email=email)
    user.is_active = False
    session.flush()
    return user
