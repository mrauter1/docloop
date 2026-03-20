from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_settings,
    get_templates,
    require_auth_context,
    require_requester,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from app.uploads import (
    UploadValidationError,
    cleanup_written_uploads,
    persist_validated_uploads,
    validate_public_image_uploads,
)
from shared.models import AttachmentVisibility, MessageVisibility, Ticket, TicketAttachment, TicketMessage, TicketView, TicketStatus
from shared.permissions import PermissionDeniedError, ensure_dev_ti, ensure_requester_attachment_access
from shared.tickets import (
    add_requester_reply,
    create_requester_ticket,
    mark_ticket_resolved,
    upsert_ticket_view,
)


router = APIRouter()


REQUESTER_STATUS_LABELS = {
    TicketStatus.NEW.value: "Reviewing",
    TicketStatus.AI_TRIAGE.value: "Reviewing",
    TicketStatus.WAITING_ON_USER.value: "Waiting for your reply",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on team",
    TicketStatus.RESOLVED.value: "Resolved",
}


def requester_status_label(status: str) -> str:
    return REQUESTER_STATUS_LABELS.get(status, status.replace("_", " ").title())


def _get_owned_ticket_or_404(db: Session, *, reference: str, user_id) -> Ticket:
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.reference == reference,
            Ticket.created_by_user_id == user_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _build_ticket_thread(
    db: Session,
    *,
    ticket_id,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    message_ids = [message.id for message in messages]
    attachments_by_message: dict[object, list[TicketAttachment]] = defaultdict(list)
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "You" if message.author_type == "requester" else message.author_type.replace("_", " ").title()
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _render_ticket_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    reply_body: str = "",
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/detail.html",
        template_context(
            request,
            auth=auth,
            ticket=ticket,
            requester_status=requester_status_label(ticket.status),
            thread=_build_ticket_thread(db, ticket_id=ticket.id),
            error=error,
            reply_body=reply_body,
        ),
    )


@router.get("/app")
def requester_home(
    auth: AuthContext = Depends(require_requester),
):
    return RedirectResponse(url="/app/tickets", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/tickets")
def ticket_list(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    rows = db.execute(
        select(Ticket, TicketView.last_viewed_at)
        .outerjoin(
            TicketView,
            and_(
                TicketView.ticket_id == Ticket.id,
                TicketView.user_id == auth.user.id,
            ),
        )
        .where(Ticket.created_by_user_id == auth.user.id)
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    ).all()

    tickets = []
    for ticket, last_viewed_at in rows:
        tickets.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": requester_status_label(ticket.status),
                "urgent": ticket.urgent,
                "updated": last_viewed_at is None or ticket.updated_at > last_viewed_at,
                "updated_at": ticket.updated_at,
            }
        )

    return templates.TemplateResponse(
        request,
        "tickets/list.html",
        template_context(request, auth=auth, tickets=tickets),
    )


@router.get("/app/tickets/new")
def new_ticket_page(
    request: Request,
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/new.html",
        template_context(
            request,
            auth=auth,
            title_value="",
            description_value="",
            urgent=False,
            error=None,
        ),
    )


@router.post("/app/tickets")
async def create_ticket_submit(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    templates = get_templates(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))

    title = str(form.get("title", "")).strip()
    description_markdown = str(form.get("description", "")).strip()
    urgent = str(form.get("urgent", "")).lower() in {"1", "true", "on", "yes"}
    if not description_markdown:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error="Description is required.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error=str(exc),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    written_paths = []
    description_text = markdown_to_plain_text(description_markdown)
    try:
        ticket, message, _ = create_requester_ticket(
            db,
            creator=auth.user,
            title=title or None,
            description_markdown=description_markdown,
            description_text=description_text,
            urgent=urgent,
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/app/tickets/{reference}")
def ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ticket_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/app/tickets/{reference}/reply")
async def ticket_reply(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)

    body_markdown = str(form.get("body", "")).strip()
    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error=str(exc),
            reply_body=body_markdown,
        )

    if not body_markdown and not validated_uploads:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Reply text or an image is required.",
            reply_body=body_markdown,
        )

    written_paths = []
    try:
        message, _ = add_requester_reply(
            db,
            ticket=ticket,
            requester=auth.user,
            body_markdown=body_markdown,
            body_text=markdown_to_plain_text(body_markdown) if body_markdown else "",
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/app/tickets/{reference}/resolve")
async def ticket_resolve(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    mark_ticket_resolved(
        db,
        ticket=ticket,
        user=auth.user,
        changed_by_type="requester",
    )
    db.commit()
    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_auth_context),
):
    try:
        attachment_uuid = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    attachment = db.get(TicketAttachment, attachment_uuid)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    ticket = db.get(Ticket, attachment.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    try:
        if auth.user.role == "requester":
            ensure_requester_attachment_access(auth.user, ticket, attachment)
        else:
            ensure_dev_ti(auth.user)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        Path(attachment.stored_path),
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
    )
