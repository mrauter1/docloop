from __future__ import annotations

from shared.models import (
    AttachmentVisibility,
    Ticket,
    TicketAttachment,
    User,
    UserRole,
)


class PermissionDeniedError(ValueError):
    """Raised when a user attempts an unauthorized action."""


def has_role(user: User, *roles: UserRole | str) -> bool:
    allowed = {role.value if isinstance(role, UserRole) else role for role in roles}
    return user.role in allowed


def ensure_role(user: User, *roles: UserRole | str) -> None:
    if not has_role(user, *roles):
        joined = ", ".join(sorted(role.value if isinstance(role, UserRole) else role for role in roles))
        raise PermissionDeniedError(f"User role {user.role!r} does not satisfy required roles: {joined}")


def ensure_requester(user: User) -> None:
    ensure_role(user, UserRole.REQUESTER)


def ensure_dev_ti(user: User) -> None:
    ensure_role(user, UserRole.DEV_TI, UserRole.ADMIN)


def ensure_requester_ticket_access(user: User, ticket: Ticket) -> None:
    ensure_requester(user)
    if ticket.created_by_user_id != user.id:
        raise PermissionDeniedError("Requester does not own this ticket")


def ensure_requester_attachment_access(
    user: User,
    ticket: Ticket,
    attachment: TicketAttachment,
) -> None:
    ensure_requester_ticket_access(user, ticket)
    if attachment.visibility != AttachmentVisibility.PUBLIC.value:
        raise PermissionDeniedError("Requester cannot access non-public attachments")
