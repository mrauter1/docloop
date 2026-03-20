from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
import uuid

from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings
from shared.db import make_session_factory, session_scope
from shared.logging import configure_logging, log_event
from shared.models import AiRun, AiRunStatus, AiRunTrigger, SystemState, Ticket, TicketStatus
from shared.tickets import change_ticket_status
from worker.codex_runner import (
    CodexExecutionError,
    CodexPreparedRun,
    build_prompt,
    prepare_codex_run,
    run_codex,
)
from worker.queue import acquire_next_pending_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context
from worker.triage import (
    finalize_failure,
    finalize_skipped,
    finalize_success,
    finalize_superseded,
    validate_triage_payload,
)


LOGGER = logging.getLogger("triage-stage1.worker")
HEARTBEAT_KEY = "worker_heartbeat"


@dataclass(frozen=True)
class PreparedExecution:
    run_id: uuid.UUID
    ticket_id: uuid.UUID
    prepared_run: CodexPreparedRun


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _message_dicts(messages) -> list[dict[str, str]]:
    return [
        {
            "author_type": message.author_type,
            "source": message.source,
            "body_markdown": message.body_markdown,
            "body_text": message.body_text,
        }
        for message in messages
    ]


def _log(event: str, **fields: object) -> None:
    log_event(LOGGER, service="worker", event=event, **fields)


def claim_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
) -> PreparedExecution | None:
    claimed_at = claimed_at or now_utc()
    with session_scope(session_factory) as session:
        run = acquire_next_pending_run(session)
        if run is None:
            return None

        context = load_ticket_run_context(session, ticket_id=run.ticket_id)
        ticket = context.ticket
        fingerprint_before_start = compute_publication_fingerprint(context)

        if (
            run.triggered_by != "manual_rerun"
            and ticket.last_processed_hash
            and fingerprint_before_start == ticket.last_processed_hash
        ):
            result = finalize_skipped(session, ticket=ticket, run=run, completed_at=claimed_at)
            _log(
                "ai_run_skipped",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return None

        prompt = build_prompt(
            reference=ticket.reference,
            title=ticket.title,
            status=ticket.status,
            urgent=ticket.urgent,
            public_messages=_message_dicts(context.public_messages),
            internal_messages=_message_dicts(context.internal_messages),
        )
        prepared_run = prepare_codex_run(
            settings,
            ticket_id=ticket.id,
            run_id=run.id,
            prompt=prompt,
            image_paths=[attachment.path for attachment in context.public_attachments],
        )

        run.prompt_path = str(prepared_run.prompt_path)
        run.schema_path = str(prepared_run.schema_path)
        run.final_output_path = str(prepared_run.final_output_path)
        run.stdout_jsonl_path = str(prepared_run.stdout_jsonl_path)
        run.stderr_path = str(prepared_run.stderr_path)
        run.model_name = settings.codex_model
        run.status = AiRunStatus.RUNNING.value
        run.started_at = claimed_at
        run.error_text = None
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type="system",
            changed_at=claimed_at,
        )
        session.flush()
        run.input_hash = compute_publication_fingerprint(
            load_ticket_run_context(session, ticket_id=run.ticket_id)
        )
        _log("ai_run_started", run_id=run.id, ticket_reference=ticket.reference)
        return PreparedExecution(run_id=run.id, ticket_id=ticket.id, prepared_run=prepared_run)


def finish_prepared_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    execution: PreparedExecution,
    completed_at: datetime | None = None,
) -> str:
    completed_at = completed_at or now_utc()
    error_text: str | None = None
    payload: dict[str, object] | None = None

    try:
        result = run_codex(execution.prepared_run, settings=settings)
        payload = result.payload
    except CodexExecutionError as exc:
        error_text = str(exc)
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        error_text = f"Unexpected worker error: {exc}"

    with session_scope(session_factory) as session:
        run = session.get(AiRun, execution.run_id)
        ticket = session.get(Ticket, execution.ticket_id)
        if run is None or ticket is None:
            raise LookupError("Run or ticket disappeared while finishing worker execution")

        if error_text is not None or payload is None:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=error_text or "Unknown AI execution failure",
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        try:
            validated_output = validate_triage_payload(payload, settings=settings, ticket=ticket)
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        context = load_ticket_run_context(session, ticket_id=ticket.id)
        publication_fingerprint = compute_publication_fingerprint(context)
        if ticket.requeue_requested or publication_fingerprint != run.input_hash:
            if not ticket.requeue_requested:
                ticket.requeue_requested = True
                ticket.requeue_trigger = (
                    ticket.requeue_trigger or AiRunTrigger.REQUESTER_REPLY.value
                )
            result = finalize_superseded(session, ticket=ticket, run=run, completed_at=completed_at)
            _log(
                "ai_run_superseded",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return result.run_status

        try:
            result = finalize_success(
                session,
                ticket=ticket,
                run=run,
                output=validated_output,
                internal_body_texts=[message.body_text for message in context.internal_messages],
                publication_fingerprint=publication_fingerprint,
                completed_at=completed_at,
            )
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        _log(
            "ai_run_succeeded",
            run_id=run.id,
            ticket_reference=ticket.reference,
            action=ticket.last_ai_action,
            queued_requeue_run_id=result.queued_requeue_run_id,
        )
        return result.run_status


def process_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> str | None:
    execution = claim_next_run(session_factory, settings=settings, claimed_at=claimed_at)
    if execution is None:
        return None
    return finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=completed_at,
    )


def update_worker_heartbeat(
    session_factory: sessionmaker[Session],
    *,
    heartbeat_at: datetime | None = None,
) -> None:
    heartbeat_at = heartbeat_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, HEARTBEAT_KEY)
        payload = {"timestamp": heartbeat_at.isoformat()}
        if row is None:
            session.add(SystemState(key=HEARTBEAT_KEY, value_json=payload, updated_at=heartbeat_at))
        else:
            row.value_json = payload
            row.updated_at = heartbeat_at


def run_worker_loop(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    once: bool = False,
) -> None:
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    last_heartbeat_at: datetime | None = None

    while True:
        current = now_utc()
        if last_heartbeat_at is None or (current - last_heartbeat_at).total_seconds() >= 60:
            update_worker_heartbeat(resolved_session_factory, heartbeat_at=current)
            last_heartbeat_at = current

        process_next_run(resolved_session_factory, settings=resolved_settings)
        if once:
            return
        time.sleep(resolved_settings.worker_poll_seconds)


def main() -> None:
    configure_logging(service="worker")
    run_worker_loop()


if __name__ == "__main__":
    main()
