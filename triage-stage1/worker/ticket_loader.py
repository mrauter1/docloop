from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AttachmentVisibility,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
)


@dataclass(frozen=True)
class LoadedMessage:
    id: uuid.UUID
    author_type: str
    source: str
    body_markdown: str
    body_text: str


@dataclass(frozen=True)
class LoadedAttachment:
    id: uuid.UUID
    message_id: uuid.UUID
    stored_path: str
    original_filename: str
    mime_type: str
    sha256: str
    created_order: tuple[str, str, str, str]

    @property
    def path(self) -> Path:
        return Path(self.stored_path)


@dataclass(frozen=True)
class TicketRunContext:
    ticket: Ticket
    public_messages: tuple[LoadedMessage, ...]
    internal_messages: tuple[LoadedMessage, ...]
    public_attachments: tuple[LoadedAttachment, ...]


def _load_messages(session: Session, *, ticket_id: uuid.UUID, visibility: str) -> tuple[LoadedMessage, ...]:
    messages = session.scalars(
        sa.select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    return tuple(
        LoadedMessage(
            id=message.id,
            author_type=message.author_type,
            source=message.source,
            body_markdown=message.body_markdown,
            body_text=message.body_text,
        )
        for message in messages
    )


def _load_public_attachments(session: Session, *, ticket_id: uuid.UUID) -> tuple[LoadedAttachment, ...]:
    rows = session.execute(
        sa.select(
            TicketAttachment,
            TicketMessage.created_at.label("message_created_at"),
        )
        .join(TicketMessage, TicketMessage.id == TicketAttachment.message_id)
        .where(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(
            TicketMessage.created_at.asc(),
            TicketMessage.id.asc(),
            TicketAttachment.created_at.asc(),
            TicketAttachment.id.asc(),
        )
    ).all()
    return tuple(
        LoadedAttachment(
            id=attachment.id,
            message_id=attachment.message_id,
            stored_path=attachment.stored_path,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            sha256=attachment.sha256,
            created_order=(
                str(message_created_at.isoformat()),
                str(attachment.message_id),
                str(attachment.created_at.isoformat()),
                str(attachment.id),
            ),
        )
        for attachment, message_created_at in rows
    )


def load_ticket_run_context(session: Session, *, ticket_id: uuid.UUID) -> TicketRunContext:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise LookupError(f"Ticket {ticket_id} not found")
    return TicketRunContext(
        ticket=ticket,
        public_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.PUBLIC.value,
        ),
        internal_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.INTERNAL.value,
        ),
        public_attachments=_load_public_attachments(session, ticket_id=ticket_id),
    )


def compute_publication_fingerprint(context: TicketRunContext) -> str:
    payload = {
        "attachment_count": len(context.public_attachments),
        "public_attachments": [attachment.sha256 for attachment in context.public_attachments],
        "public_messages": [
            {
                "author_type": message.author_type,
                "body_text": message.body_text,
                "source": message.source,
            }
            for message in context.public_messages
        ],
        "status": context.ticket.status,
        "title": context.ticket.title,
        "urgent": context.ticket.urgent,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
