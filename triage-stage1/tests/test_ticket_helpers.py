from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRunStatus,
    AiRunTrigger,
    Base,
    StatusChangedByType,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    ActiveAIRunExistsError,
    assign_ticket_reference,
    change_ticket_status,
    create_pending_ai_run,
    format_ticket_reference,
    supersede_pending_drafts,
    upsert_ticket_view,
)


@pytest.fixture
def session() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db


def make_user(email: str) -> User:
    return User(
        email=email,
        display_name=email.split("@", 1)[0],
        password_hash="hashed",
        role=UserRole.REQUESTER.value,
    )


def make_ticket(user_id: uuid.UUID, reference_num: int = 1) -> Ticket:
    ticket = Ticket(
        reference_num=reference_num,
        reference=format_ticket_reference(reference_num),
        title="Title",
        created_by_user_id=user_id,
        status=TicketStatus.NEW.value,
    )
    return ticket


def test_format_ticket_reference_zero_pads() -> None:
    assert format_ticket_reference(42) == "T-000042"


def test_assign_ticket_reference_uses_reference_num() -> None:
    ticket = Ticket(reference_num=12, reference="placeholder", title="x", created_by_user_id=uuid.uuid4(), status="new")
    assert assign_ticket_reference(ticket) == "T-000012"


def test_change_ticket_status_writes_history_and_resolved_at(session: Session) -> None:
    actor = make_user("user@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    changed_at = datetime(2026, 3, 19, tzinfo=timezone.utc)
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=changed_at,
    )
    session.flush()

    assert history is not None
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.resolved_at == changed_at
    assert ticket.updated_at == changed_at


def test_upsert_ticket_view_updates_existing_row(session: Session) -> None:
    actor = make_user("viewer@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    first_seen = datetime(2026, 3, 19, 10, tzinfo=timezone.utc)
    second_seen = datetime(2026, 3, 19, 12, tzinfo=timezone.utc)
    first = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=first_seen)
    session.flush()
    second = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=second_seen)

    assert first.user_id == second.user_id
    assert second.last_viewed_at == second_seen


def test_supersede_pending_drafts_only_touches_pending_approval(session: Session) -> None:
    actor = make_user("author@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()
    run = create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    run.status = AiRunStatus.SUCCEEDED.value
    session.flush()

    kept = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="one",
        body_text="one",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    stale = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="two",
        body_text="two",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    published = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="three",
        body_text="three",
        status=AiDraftStatus.PUBLISHED.value,
    )
    session.add_all([kept, stale, published])
    session.flush()

    updated = supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=kept.id)

    assert updated == 1
    assert kept.status == AiDraftStatus.PENDING_APPROVAL.value
    assert stale.status == AiDraftStatus.SUPERSEDED.value
    assert published.status == AiDraftStatus.PUBLISHED.value


def test_create_pending_ai_run_rejects_second_active_run(session: Session) -> None:
    actor = make_user("queue@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    with pytest.raises(ActiveAIRunExistsError):
        create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.REQUESTER_REPLY)
