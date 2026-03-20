from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AiRunTrigger,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketStatusHistory,
    TicketRequeueTrigger,
    TicketView,
    User,
)


class TicketError(ValueError):
    """Base class for shared ticket-domain helper errors."""


class MissingTicketReferenceNumberError(TicketError):
    """Raised when a ticket reference cannot be derived yet."""


class ActiveAIRunExistsError(TicketError):
    """Raised when a second active AI run is requested for the same ticket."""


class InvalidDraftStateError(TicketError):
    """Raised when a draft transition is attempted from the wrong state."""


ACTIVE_AI_RUN_STATUSES = (
    AiRunStatus.PENDING.value,
    AiRunStatus.RUNNING.value,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_requeue_trigger(value: TicketRequeueTrigger | str) -> str:
    return value.value if isinstance(value, TicketRequeueTrigger) else value


def normalize_status(value: TicketStatus | str) -> str:
    return value.value if isinstance(value, TicketStatus) else value


def normalize_changed_by_type(value: StatusChangedByType | str) -> str:
    return value.value if isinstance(value, StatusChangedByType) else value


def normalize_run_trigger(value: AiRunTrigger | str) -> str:
    return value.value if isinstance(value, AiRunTrigger) else value


def format_ticket_reference(reference_num: int) -> str:
    return f"T-{reference_num:06d}"


def assign_ticket_reference(ticket: Ticket) -> str:
    if ticket.reference_num is None:
        raise MissingTicketReferenceNumberError(
            "Ticket reference_num must be assigned before formatting the reference"
        )
    ticket.reference = format_ticket_reference(ticket.reference_num)
    return ticket.reference


def bump_ticket_updated_at(ticket: Ticket, when: datetime | None = None) -> datetime:
    ticket.updated_at = when or now_utc()
    return ticket.updated_at


def change_ticket_status(
    session: Session,
    ticket: Ticket,
    to_status: TicketStatus | str,
    *,
    changed_by_type: StatusChangedByType | str,
    changed_by_user_id: uuid.UUID | None = None,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    target_status = normalize_status(to_status)
    previous_status = ticket.status
    if previous_status == target_status:
        return None

    changed_at = changed_at or now_utc()
    ticket.status = target_status
    ticket.resolved_at = changed_at if target_status == TicketStatus.RESOLVED.value else None
    bump_ticket_updated_at(ticket, changed_at)

    history = TicketStatusHistory(
        ticket_id=ticket.id,
        from_status=previous_status,
        to_status=target_status,
        changed_by_user_id=changed_by_user_id,
        changed_by_type=normalize_changed_by_type(changed_by_type),
        note=note,
        created_at=changed_at,
    )
    session.add(history)
    return history


def first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Untitled ticket"
    parts = re.split(r"(?<=[.!?])\s+|\n+", stripped, maxsplit=1)
    candidate = parts[0].strip() if parts else stripped
    return candidate or "Untitled ticket"


def derive_ticket_title(title: str | None, description_text: str) -> str:
    candidate = (title or "").strip()
    if candidate:
        return candidate[:120]
    return first_sentence(description_text)[:120]


def _needs_manual_reference_assignment(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_reference_num(session: Session) -> int:
    next_value = session.scalar(sa.select(sa.func.coalesce(sa.func.max(Ticket.reference_num), 0) + 1))
    return int(next_value or 1)


def upsert_ticket_view(
    session: Session,
    *,
    user_id: uuid.UUID,
    ticket_id: uuid.UUID,
    viewed_at: datetime | None = None,
) -> TicketView:
    viewed_at = viewed_at or now_utc()
    ticket_view = session.scalar(
        sa.select(TicketView).where(
            TicketView.user_id == user_id,
            TicketView.ticket_id == ticket_id,
        )
    )
    if ticket_view is None:
        ticket_view = TicketView(user_id=user_id, ticket_id=ticket_id, last_viewed_at=viewed_at)
        session.add(ticket_view)
    else:
        ticket_view.last_viewed_at = viewed_at
    return ticket_view


def supersede_pending_drafts(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    keep_draft_id: uuid.UUID | None = None,
) -> int:
    drafts = session.scalars(
        sa.select(AiDraft).where(
            AiDraft.ticket_id == ticket_id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    ).all()
    updated = 0
    for draft in drafts:
        if keep_draft_id is not None and draft.id == keep_draft_id:
            continue
        draft.status = AiDraftStatus.SUPERSEDED.value
        updated += 1
    return updated


def find_active_ai_run(session: Session, *, ticket_id: uuid.UUID) -> AiRun | None:
    return session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket_id,
            AiRun.status.in_(ACTIVE_AI_RUN_STATUSES),
        )
    )


def create_pending_ai_run(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    triggered_by: AiRunTrigger | str,
    requested_by_user_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> AiRun:
    existing = find_active_ai_run(session, ticket_id=ticket_id)
    if existing is not None:
        raise ActiveAIRunExistsError(
            f"Ticket {ticket_id} already has an active AI run ({existing.id})"
        )

    run = AiRun(
        ticket_id=ticket_id,
        status=AiRunStatus.PENDING.value,
        triggered_by=normalize_run_trigger(triggered_by),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at or now_utc(),
    )
    session.add(run)
    return run


def create_ticket_message(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    author_type: MessageAuthorType | str,
    visibility: MessageVisibility | str,
    source: MessageSource | str,
    body_markdown: str,
    body_text: str,
    ai_run_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> TicketMessage:
    message = TicketMessage(
        ticket_id=ticket_id,
        author_user_id=author_user_id,
        author_type=author_type.value if isinstance(author_type, MessageAuthorType) else author_type,
        visibility=visibility.value if isinstance(visibility, MessageVisibility) else visibility,
        source=source.value if isinstance(source, MessageSource) else source,
        body_markdown=body_markdown,
        body_text=body_text,
        ai_run_id=ai_run_id,
        created_at=created_at or now_utc(),
    )
    session.add(message)
    return message


def create_requester_ticket(
    session: Session,
    *,
    creator: User,
    title: str | None,
    description_markdown: str,
    description_text: str,
    urgent: bool,
    created_at: datetime | None = None,
) -> tuple[Ticket, TicketMessage, AiRun]:
    created_at = created_at or now_utc()
    reference_num = _next_reference_num(session) if _needs_manual_reference_assignment(session) else None

    ticket = Ticket(
        reference_num=reference_num,
        reference="pending",
        title=derive_ticket_title(title, description_text),
        created_by_user_id=creator.id,
        status=TicketStatus.NEW.value,
        urgent=urgent,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(ticket)
    session.flush()

    if ticket.reference_num is None:
        ticket.reference_num = _next_reference_num(session)
        session.flush()
    assign_ticket_reference(ticket)

    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=creator.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.TICKET_CREATE,
        body_markdown=description_markdown,
        body_text=description_text,
        created_at=created_at,
    )
    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=AiRunTrigger.NEW_TICKET,
        requested_by_user_id=creator.id,
        created_at=created_at,
    )
    session.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=None,
            to_status=TicketStatus.NEW.value,
            changed_by_user_id=creator.id,
            changed_by_type=StatusChangedByType.REQUESTER.value,
            created_at=created_at,
        )
    )
    upsert_ticket_view(session, user_id=creator.id, ticket_id=ticket.id, viewed_at=created_at)
    return ticket, message, run


def add_requester_reply(
    session: Session,
    *,
    ticket: Ticket,
    requester: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, AiRun | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=requester.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.REQUESTER_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)

    trigger = (
        AiRunTrigger.REOPEN.value
        if ticket.status == TicketStatus.RESOLVED.value
        else AiRunTrigger.REQUESTER_REPLY.value
    )
    run: AiRun | None = None
    active_run = find_active_ai_run(session, ticket_id=ticket.id)
    if active_run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=trigger,
            requested_by_user_id=requester.id,
            created_at=created_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = normalize_requeue_trigger(trigger)

    change_ticket_status(
        session,
        ticket,
        TicketStatus.AI_TRIAGE,
        changed_by_type=StatusChangedByType.REQUESTER,
        changed_by_user_id=requester.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=requester.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, run


def mark_ticket_resolved(
    session: Session,
    *,
    ticket: Ticket,
    user: User,
    changed_by_type: StatusChangedByType | str,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=changed_by_type,
        changed_by_user_id=user.id,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=user.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def set_ticket_assignment(
    session: Session,
    *,
    ticket: Ticket,
    assigned_to_user_id: uuid.UUID | None,
    actor: User,
    changed_at: datetime | None = None,
) -> bool:
    changed_at = changed_at or now_utc()
    changed = ticket.assigned_to_user_id != assigned_to_user_id
    if changed:
        ticket.assigned_to_user_id = assigned_to_user_id
        bump_ticket_updated_at(ticket, changed_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return changed


def set_ticket_status_for_ops(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    to_status: TicketStatus | str,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        to_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        note=note,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def add_public_reply(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    next_status: TicketStatus | str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.HUMAN_PUBLIC_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, history


def add_internal_note(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> TicketMessage:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.HUMAN_INTERNAL_NOTE,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message


def request_manual_rerun(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    requested_at: datetime | None = None,
) -> AiRun | None:
    requested_at = requested_at or now_utc()
    run = find_active_ai_run(session, ticket_id=ticket.id)
    if run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=AiRunTrigger.MANUAL_RERUN,
            requested_by_user_id=actor.id,
            created_at=requested_at,
        )
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type=StatusChangedByType.DEV_TI,
            changed_by_user_id=actor.id,
            changed_at=requested_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = TicketRequeueTrigger.MANUAL_RERUN.value
        bump_ticket_updated_at(ticket, requested_at)
        run = None
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=requested_at)
    return run


def approve_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    next_status: TicketStatus | str,
    published_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be published")

    published_at = published_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.AI_DRAFT_PUBLISHED,
        body_markdown=draft.body_markdown,
        body_text=draft.body_text,
        ai_run_id=draft.ai_run_id,
        created_at=published_at,
    )
    draft.status = AiDraftStatus.PUBLISHED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = published_at
    draft.published_message_id = message.id
    bump_ticket_updated_at(ticket, published_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=published_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=published_at)
    return message, history


def reject_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    rejected_at: datetime | None = None,
) -> None:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be rejected")

    rejected_at = rejected_at or now_utc()
    draft.status = AiDraftStatus.REJECTED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = rejected_at
    bump_ticket_updated_at(ticket, rejected_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=rejected_at)
