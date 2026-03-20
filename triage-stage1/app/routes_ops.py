from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_templates,
    require_dev_ti,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AttachmentVisibility,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketClass,
    TicketMessage,
    TicketStatus,
    TicketView,
    User,
    UserRole,
)
from shared.permissions import ensure_dev_ti
from shared.tickets import (
    InvalidDraftStateError,
    add_internal_note,
    add_public_reply,
    approve_ai_draft,
    request_manual_rerun,
    reject_ai_draft,
    set_ticket_assignment,
    set_ticket_status_for_ops,
    upsert_ticket_view,
)


router = APIRouter()


OPS_STATUS_ORDER = [
    TicketStatus.NEW.value,
    TicketStatus.AI_TRIAGE.value,
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]
OPS_STATUS_LABELS = {
    TicketStatus.NEW.value: "New",
    TicketStatus.AI_TRIAGE.value: "AI Triage",
    TicketStatus.WAITING_ON_USER.value: "Waiting on User",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on Dev/TI",
    TicketStatus.RESOLVED.value: "Resolved",
}
REPLY_STATUS_OPTIONS = [
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]


def ops_status_label(value: str) -> str:
    return OPS_STATUS_LABELS.get(value, value.replace("_", " ").title())


def _parse_bool(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "on", "yes"}


def _get_ticket_or_404(db: Session, *, reference: str) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.reference == reference))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _get_draft_or_404(db: Session, *, draft_id: str) -> AiDraft:
    try:
        draft_uuid = uuid.UUID(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found") from exc
    draft = db.get(AiDraft, draft_uuid)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def _load_ops_users(db: Session) -> list[User]:
    return db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_([UserRole.DEV_TI.value, UserRole.ADMIN.value]),
        )
        .order_by(User.display_name.asc(), User.email.asc())
    ).all()


def _build_thread(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    visibility: str,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    attachments_by_message: dict[uuid.UUID, list[TicketAttachment]] = defaultdict(list)
    message_ids = [message.id for message in messages]
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility
                == (
                    AttachmentVisibility.PUBLIC.value
                    if visibility == MessageVisibility.PUBLIC.value
                    else AttachmentVisibility.INTERNAL.value
                ),
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "AI" if message.author_type == MessageAuthorType.AI.value else message.author_type.replace("_", " ").title()
        if message.author_type == MessageAuthorType.DEV_TI.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        if message.author_type == MessageAuthorType.REQUESTER.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "source_label": message.source.replace("_", " ").title(),
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _load_relevant_paths(latest_run: AiRun | None) -> list[dict[str, str]]:
    if latest_run is None or not latest_run.final_output_path:
        return []
    output_path = Path(latest_run.final_output_path)
    if not output_path.exists():
        return []
    try:
        payload = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    relevant_paths = payload.get("relevant_paths")
    if not isinstance(relevant_paths, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in relevant_paths:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        reason = item.get("reason")
        if isinstance(path, str) and isinstance(reason, str):
            normalized.append({"path": path, "reason": reason})
    return normalized


def _load_ops_detail_context(db: Session, *, ticket: Ticket) -> dict[str, object]:
    creator = db.get(User, ticket.created_by_user_id)
    assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
    latest_ai_note = db.scalar(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.visibility == MessageVisibility.INTERNAL.value,
            TicketMessage.author_type == MessageAuthorType.AI.value,
            TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
        )
        .order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc())
    )
    latest_run = db.scalar(
        select(AiRun)
        .where(AiRun.ticket_id == ticket.id)
        .order_by(AiRun.created_at.desc(), AiRun.id.desc())
    )
    pending_draft = db.scalar(
        select(AiDraft)
        .where(
            AiDraft.ticket_id == ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    latest_draft = db.scalar(
        select(AiDraft)
        .where(AiDraft.ticket_id == ticket.id)
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    return {
        "ticket": ticket,
        "creator": creator,
        "assignee": assignee,
        "public_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.PUBLIC.value),
        "internal_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.INTERNAL.value),
        "latest_ai_note_html": (
            markdown_to_safe_html(latest_ai_note.body_markdown) if latest_ai_note is not None else None
        ),
        "latest_ai_note_at": latest_ai_note.created_at if latest_ai_note is not None else None,
        "latest_run": latest_run,
        "relevant_paths": _load_relevant_paths(latest_run),
        "pending_draft": pending_draft,
        "pending_draft_html": (
            markdown_to_safe_html(pending_draft.body_markdown) if pending_draft is not None else None
        ),
        "latest_draft": latest_draft,
        "ops_users": _load_ops_users(db),
        "reply_status_options": [(value, ops_status_label(value)) for value in REPLY_STATUS_OPTIONS],
        "status_options": [(value, ops_status_label(value)) for value in OPS_STATUS_ORDER],
    }


def _render_ops_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    public_reply_body: str = "",
    internal_note_body: str = "",
    next_status: str | None = None,
):
    templates = get_templates(request)
    context = _load_ops_detail_context(db, ticket=ticket)
    context.update(
        {
            "error": error,
            "public_reply_body": public_reply_body,
            "internal_note_body": internal_note_body,
            "selected_next_status": next_status or TicketStatus.WAITING_ON_USER.value,
        }
    )
    return templates.TemplateResponse(
        request,
        "ops/detail.html",
        template_context(request, auth=auth, **context),
        status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK,
    )


def _selected_filters(request: Request) -> dict[str, str]:
    return {
        "status": request.query_params.get("status", ""),
        "ticket_class": request.query_params.get("ticket_class", ""),
        "assigned_to": request.query_params.get("assigned_to", ""),
        "urgent": request.query_params.get("urgent", ""),
        "unassigned_only": request.query_params.get("unassigned_only", ""),
        "created_by_me": request.query_params.get("created_by_me", ""),
        "needs_approval": request.query_params.get("needs_approval", ""),
        "updated_since_my_last_view": request.query_params.get("updated_since_my_last_view", ""),
    }


def _board_rows(db: Session, *, auth: AuthContext, filters: dict[str, str]) -> list[dict[str, object]]:
    last_viewed_at = TicketView.last_viewed_at.label("last_viewed_at")
    needs_approval = exists(
        select(1).where(
            AiDraft.ticket_id == Ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    )
    query = (
        select(Ticket, User.display_name.label("creator_name"), last_viewed_at, needs_approval.label("needs_approval"))
        .join(User, User.id == Ticket.created_by_user_id)
        .outerjoin(
            TicketView,
            and_(TicketView.ticket_id == Ticket.id, TicketView.user_id == auth.user.id),
        )
    )

    if filters["status"]:
        query = query.where(Ticket.status == filters["status"])
    if filters["ticket_class"]:
        query = query.where(Ticket.ticket_class == filters["ticket_class"])
    if filters["assigned_to"]:
        try:
            assigned_uuid = uuid.UUID(filters["assigned_to"])
        except ValueError:
            assigned_uuid = None
        if assigned_uuid is not None:
            query = query.where(Ticket.assigned_to_user_id == assigned_uuid)
    if _parse_bool(filters["urgent"]):
        query = query.where(Ticket.urgent.is_(True))
    if _parse_bool(filters["unassigned_only"]):
        query = query.where(Ticket.assigned_to_user_id.is_(None))
    if _parse_bool(filters["created_by_me"]):
        query = query.where(Ticket.created_by_user_id == auth.user.id)
    if _parse_bool(filters["needs_approval"]):
        query = query.where(needs_approval)
    if _parse_bool(filters["updated_since_my_last_view"]):
        query = query.where(
            sa.or_(TicketView.last_viewed_at.is_(None), Ticket.updated_at > TicketView.last_viewed_at)
        )

    query = query.order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    rows = db.execute(query).all()

    assignee_ids = {ticket.assigned_to_user_id for ticket, _, _, _ in rows if ticket.assigned_to_user_id}
    assignees = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(assignee_ids))).all()
    }
    rendered: list[dict[str, object]] = []
    for ticket, creator_name, viewed_at, has_pending_draft in rows:
        rendered.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": ticket.status,
                "status_label": ops_status_label(ticket.status),
                "creator_name": creator_name,
                "assignee_name": assignees.get(ticket.assigned_to_user_id),
                "ticket_class": ticket.ticket_class or "unclassified",
                "urgent": ticket.urgent,
                "needs_approval": bool(has_pending_draft),
                "updated": viewed_at is None or ticket.updated_at > viewed_at,
                "updated_at": ticket.updated_at,
            }
        )
    return rendered


@router.get("/ops")
def ops_home(auth: AuthContext = Depends(require_dev_ti)):
    return RedirectResponse(url="/ops/board", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/ops/board")
def ops_board(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    templates = get_templates(request)
    filters = _selected_filters(request)
    rows = _board_rows(db, auth=auth, filters=filters)
    columns: list[dict[str, object]] = []
    for status_value in OPS_STATUS_ORDER:
        items = [row for row in rows if row["status"] == status_value]
        columns.append(
            {
                "status": status_value,
                "label": ops_status_label(status_value),
                "tickets": items,
            }
        )
    return templates.TemplateResponse(
        request,
        "ops/board.html",
        template_context(
            request,
            auth=auth,
            columns=columns,
            filters=filters,
            ticket_class_options=[item.value for item in TicketClass],
            assignee_options=_load_ops_users(db),
        ),
    )


@router.get("/ops/tickets/{reference}")
def ops_ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    ticket = _get_ticket_or_404(db, reference=reference)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ops_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/ops/tickets/{reference}/assign")
async def assign_ticket(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    raw_assignee = str(form.get("assigned_to_user_id", "")).strip()
    assigned_to_user_id: uuid.UUID | None = None
    if raw_assignee:
        try:
            assigned_to_user_id = uuid.UUID(raw_assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid assignee.")
        assignee = db.get(User, assigned_to_user_id)
        if assignee is None:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee not found.")
        try:
            ensure_dev_ti(assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee must be a Dev/TI or admin user.")
    set_ticket_assignment(db, ticket=ticket, assigned_to_user_id=assigned_to_user_id, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/set-status")
async def set_status(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    target_status = str(form.get("status", "")).strip()
    if target_status not in OPS_STATUS_LABELS:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid status.")
    set_ticket_status_for_ops(db, ticket=ticket, actor=auth.user, to_status=target_status)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/reply-public")
async def reply_public(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    next_status = str(form.get("next_status", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Public reply text is required.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    add_public_reply(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        next_status=next_status,
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/note-internal")
async def note_internal(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Internal note text is required.",
            internal_note_body=body_markdown,
        )
    add_internal_note(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/rerun-ai")
async def rerun_ai(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    request_manual_rerun(db, ticket=ticket, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/approve-publish")
async def approve_draft_publish(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    next_status = str(form.get("next_status", "")).strip()
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status before publishing the draft.",
            next_status=next_status,
        )
    try:
        approve_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user, next_status=next_status)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    try:
        reject_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)
