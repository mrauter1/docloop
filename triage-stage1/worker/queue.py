from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import AiRun, AiRunStatus, AiRunTrigger, Ticket, TicketRequeueTrigger
from shared.tickets import create_pending_ai_run


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
    active_run = session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket.id,
            AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
        )
    )
    if active_run is not None:
        return None

    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=_normalize_trigger(ticket.requeue_trigger),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at,
    )
    ticket.requeue_requested = False
    ticket.requeue_trigger = None
    return run

