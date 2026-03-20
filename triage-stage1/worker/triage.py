from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftKind,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketClass,
    TicketStatus,
)
from shared.tickets import (
    bump_ticket_updated_at,
    change_ticket_status,
    create_ticket_message,
    supersede_pending_drafts,
)
from worker.queue import enqueue_deferred_requeue


class RelevantPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class TriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_class: Literal["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    impact_level: Literal["low", "medium", "high", "unknown"]
    requester_language: str = Field(min_length=2)
    summary_short: str = Field(min_length=1, max_length=120)
    summary_internal: str = Field(min_length=1)
    development_needed: bool
    needs_clarification: bool
    clarifying_questions: list[str] = Field(default_factory=list, max_length=3)
    incorrect_or_conflicting_details: list[str] = Field(default_factory=list)
    evidence_found: bool
    relevant_paths: list[RelevantPath] = Field(default_factory=list)
    recommended_next_action: Literal[
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti",
    ]
    auto_public_reply_allowed: bool
    public_reply_markdown: str = ""
    internal_note_markdown: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_rules(self) -> "TriageOutput":
        if (
            self.recommended_next_action == "ask_clarification"
            and (not self.needs_clarification or not self.public_reply_markdown.strip())
        ):
            raise ValueError("ask_clarification requires clarification and a public reply")
        if self.recommended_next_action == "auto_public_reply":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_public_reply requires auto_public_reply_allowed=true")
            if not self.evidence_found:
                raise ValueError("auto_public_reply requires evidence_found=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_public_reply requires a public reply")
            if self.ticket_class == TicketClass.UNKNOWN.value:
                raise ValueError("unknown tickets cannot auto publish")
        if self.recommended_next_action == "auto_confirm_and_route":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_confirm_and_route requires auto_public_reply_allowed=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_confirm_and_route requires a public reply")
        if self.recommended_next_action == "draft_public_reply":
            if self.auto_public_reply_allowed:
                raise ValueError("draft_public_reply requires auto_public_reply_allowed=false")
            if not self.public_reply_markdown.strip():
                raise ValueError("draft_public_reply requires a public reply")
        if self.recommended_next_action == "route_dev_ti" and self.public_reply_markdown is None:
            raise ValueError("route_dev_ti requires public_reply_markdown to be present")
        return self


class TriageValidationError(ValueError):
    """Raised when the AI payload violates product-level validation rules."""


@dataclass(frozen=True)
class PublicationResult:
    run_status: str
    queued_requeue_run_id: uuid.UUID | None


def _resolved_publication_result(run: AiRun) -> PublicationResult:
    return PublicationResult(run_status=run.status, queued_requeue_run_id=None)


def _run_already_terminal(run: AiRun) -> bool:
    return run.status not in {
        AiRunStatus.PENDING.value,
        AiRunStatus.RUNNING.value,
    }


def guard_auto_public_reply(
    output: TriageOutput,
    *,
    internal_body_texts: list[str],
) -> TriageOutput:
    if output.recommended_next_action not in {
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
    }:
        return output
    if not internal_body_texts:
        return output

    if output.recommended_next_action == "ask_clarification":
        return output.model_copy(
            update={
                "recommended_next_action": "route_dev_ti",
                "auto_public_reply_allowed": False,
                "public_reply_markdown": "",
            }
        )
    return output.model_copy(
        update={
            "recommended_next_action": "draft_public_reply",
            "auto_public_reply_allowed": False,
        }
    )


def validate_triage_payload(
    payload: dict[str, object],
    *,
    settings: Settings,
    ticket: Ticket,
) -> TriageOutput:
    try:
        result = TriageOutput.model_validate(payload)
    except ValidationError as exc:
        raise TriageValidationError(str(exc)) from exc

    if (
        result.recommended_next_action == "auto_public_reply"
        and result.confidence < settings.auto_support_reply_min_confidence
    ):
        raise TriageValidationError("auto_public_reply confidence is below the configured threshold")
    if (
        result.recommended_next_action == "auto_confirm_and_route"
        and result.confidence < settings.auto_confirm_intent_min_confidence
    ):
        raise TriageValidationError(
            "auto_confirm_and_route confidence is below the configured threshold"
        )
    if (
        result.recommended_next_action == "ask_clarification"
        and ticket.clarification_rounds >= 2
    ):
        raise TriageValidationError("clarification limit already reached for this ticket")
    return result


def apply_ticket_classification(ticket: Ticket, output: TriageOutput) -> None:
    ticket.ticket_class = output.ticket_class
    ticket.ai_confidence = Decimal(str(output.confidence)).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )
    ticket.impact_level = output.impact_level
    ticket.development_needed = output.development_needed
    ticket.requester_language = output.requester_language


def publish_internal_ai_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    created_at,
) -> None:
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.AI_INTERNAL_NOTE,
        body_markdown=output.internal_note_markdown,
        body_text=markdown_to_plain_text(output.internal_note_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def publish_failure_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    created_at,
) -> None:
    body_markdown = (
        "AI triage failed for this run.\n\n"
        f"- Run ID: `{run.id}`\n"
        f"- Error: {error_text}"
    )
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.SYSTEM,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.SYSTEM,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def apply_ai_action(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    acted_at,
) -> None:
    public_body_text = markdown_to_plain_text(output.public_reply_markdown)

    if output.recommended_next_action == "ask_clarification":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        ticket.clarification_rounds += 1
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_public_reply":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_confirm_and_route":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "draft_public_reply":
        draft = AiDraft(
            ticket_id=ticket.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            status=AiDraftStatus.PENDING_APPROVAL.value,
            created_at=acted_at,
        )
        session.add(draft)
        session.flush()
        supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=draft.id)
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "route_dev_ti":
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    else:
        raise TriageValidationError(f"Unsupported action: {output.recommended_next_action}")

    ticket.last_ai_action = output.recommended_next_action


def finalize_success(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    internal_body_texts: list[str],
    publication_fingerprint: str,
    completed_at,
) -> PublicationResult:
    if _run_already_terminal(run):
        return _resolved_publication_result(run)

    guarded_output = guard_auto_public_reply(
        output,
        internal_body_texts=internal_body_texts,
    )
    apply_ticket_classification(ticket, guarded_output)
    publish_internal_ai_note(
        session,
        ticket=ticket,
        run=run,
        output=guarded_output,
        created_at=completed_at,
    )
    apply_ai_action(session, ticket=ticket, run=run, output=guarded_output, acted_at=completed_at)
    ticket.last_processed_hash = publication_fingerprint
    run.status = "succeeded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_failure(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    completed_at,
) -> PublicationResult:
    if _run_already_terminal(run):
        return _resolved_publication_result(run)

    publish_failure_note(session, ticket=ticket, run=run, error_text=error_text, created_at=completed_at)
    change_ticket_status(
        session,
        ticket,
        TicketStatus.WAITING_ON_DEV_TI,
        changed_by_type=StatusChangedByType.SYSTEM,
        changed_at=completed_at,
    )
    run.status = "failed"
    run.ended_at = completed_at
    run.error_text = error_text
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_superseded(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    if _run_already_terminal(run):
        return _resolved_publication_result(run)

    run.status = "superseded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_skipped(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    if _run_already_terminal(run):
        return _resolved_publication_result(run)

    run.status = "skipped"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))
