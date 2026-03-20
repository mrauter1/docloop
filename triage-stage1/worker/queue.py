from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models import AiRun, AiRunStatus, AiRunTrigger, Ticket, TicketRequeueTrigger
from shared.tickets import ActiveAIRunExistsError, create_pending_ai_run


def acquire_next_pending_run(session: Session) -> AiRun | None:
    query = (
        sa.select(AiRun)
        .where(AiRun.status == AiRunStatus.PENDING.value)
        .order_by(AiRun.created_at.asc(), AiRun.id.asc())
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    return session.scalar(query)


def _normalize_trigger(value: str | None) -> str:
    if value in {
        TicketRequeueTrigger.REQUESTER_REPLY.value,
        TicketRequeueTrigger.MANUAL_RERUN.value,
        TicketRequeueTrigger.REOPEN.value,
    }:
        return value
    return AiRunTrigger.REQUESTER_REPLY.value


def _active_run_query(ticket_id) -> sa.Select:
    return sa.select(AiRun).where(
        AiRun.ticket_id == ticket_id,
        AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
    )


def _load_active_run(session: Session, *, ticket_id) -> AiRun | None:
    return session.scalar(_active_run_query(ticket_id))


def _is_active_run_integrity_error(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc))
    return "uq_ai_runs_ticket_active" in message or "ai_runs.ticket_id" in message


def enqueue_deferred_requeue(
    session: Session,
    *,
    ticket: Ticket,
    created_at: datetime,
    requested_by_user_id: uuid.UUID | None = None,
) -> AiRun | None:
    if not ticket.requeue_requested:
        return None

    session.flush()
    run: AiRun | None = None
    try:
        with session.begin_nested():
            run = create_pending_ai_run(
                session,
                ticket_id=ticket.id,
                triggered_by=_normalize_trigger(ticket.requeue_trigger),
                requested_by_user_id=requested_by_user_id,
                created_at=created_at,
            )
            session.flush()
    except ActiveAIRunExistsError:
        run = None
    except IntegrityError as exc:
        if not _is_active_run_integrity_error(exc):
            raise
        run = None

    active_run = run or _load_active_run(session, ticket_id=ticket.id)
    if active_run is None:
        return None

    ticket.requeue_requested = False
    ticket.requeue_trigger = None
    return run
