from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    ADMIN = "admin"


class TicketStatus(StrEnum):
    NEW = "new"
    AI_TRIAGE = "ai_triage"
    WAITING_ON_USER = "waiting_on_user"
    WAITING_ON_DEV_TI = "waiting_on_dev_ti"
    RESOLVED = "resolved"


class TicketClass(StrEnum):
    SUPPORT = "support"
    ACCESS_CONFIG = "access_config"
    DATA_OPS = "data_ops"
    BUG = "bug"
    FEATURE = "feature"
    UNKNOWN = "unknown"


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class MessageAuthorType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class MessageVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class MessageSource(StrEnum):
    TICKET_CREATE = "ticket_create"
    REQUESTER_REPLY = "requester_reply"
    HUMAN_PUBLIC_REPLY = "human_public_reply"
    HUMAN_INTERNAL_NOTE = "human_internal_note"
    AI_AUTO_PUBLIC = "ai_auto_public"
    AI_INTERNAL_NOTE = "ai_internal_note"
    AI_DRAFT_PUBLISHED = "ai_draft_published"
    SYSTEM = "system"


class AttachmentVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class StatusChangedByType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class AiRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class AiRunTrigger(StrEnum):
    NEW_TICKET = "new_ticket"
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class TicketRequeueTrigger(StrEnum):
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class AiDraftKind(StrEnum):
    PUBLIC_REPLY = "public_reply"


class AiDraftStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    PUBLISHED = "published"


def enum_values(enum_cls: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum_cls)


def enum_type(enum_cls: type[StrEnum], *, name: str) -> sa.Enum:
    return sa.Enum(
        *enum_values(enum_cls),
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    role: Mapped[str] = mapped_column(enum_type(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    remember_me: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    user_agent: Mapped[str | None] = mapped_column(sa.Text())
    ip_address: Mapped[str | None] = mapped_column(sa.Text())


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_updated_at", "status", sa.text("updated_at DESC")),
        Index(
            "ix_tickets_created_by_updated_at",
            "created_by_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_assigned_to_updated_at",
            "assigned_to_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_urgent_status_updated_at",
            "urgent",
            "status",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    reference_num: Mapped[int] = mapped_column(
        sa.BigInteger(),
        Identity(start=1),
        nullable=False,
        unique=True,
    )
    reference: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="ticket_status"), nullable=False)
    urgent: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    ticket_class: Mapped[str | None] = mapped_column(enum_type(TicketClass, name="ticket_class"))
    ai_confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 3))
    impact_level: Mapped[str | None] = mapped_column(enum_type(ImpactLevel, name="impact_level"))
    development_needed: Mapped[bool | None] = mapped_column(sa.Boolean())
    clarification_rounds: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    requester_language: Mapped[str | None] = mapped_column(sa.Text())
    last_processed_hash: Mapped[str | None] = mapped_column(sa.Text())
    last_ai_action: Mapped[str | None] = mapped_column(sa.Text())
    requeue_requested: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    requeue_trigger: Mapped[str | None] = mapped_column(
        enum_type(TicketRequeueTrigger, name="ticket_requeue_trigger")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class AiRun(TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_status_created_at", "status", "created_at"),
        Index("ix_ai_runs_ticket_created_at_desc", "ticket_id", sa.text("created_at DESC")),
        Index(
            "uq_ai_runs_ticket_active",
            "ticket_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'running')"),
            sqlite_where=sa.text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(enum_type(AiRunStatus, name="ai_run_status"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(
        enum_type(AiRunTrigger, name="ai_run_trigger"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    input_hash: Mapped[str | None] = mapped_column(sa.Text())
    model_name: Mapped[str | None] = mapped_column(sa.Text())
    prompt_path: Mapped[str | None] = mapped_column(sa.Text())
    schema_path: Mapped[str | None] = mapped_column(sa.Text())
    final_output_path: Mapped[str | None] = mapped_column(sa.Text())
    stdout_jsonl_path: Mapped[str | None] = mapped_column(sa.Text())
    stderr_path: Mapped[str | None] = mapped_column(sa.Text())
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(sa.Text())


class TicketMessage(TimestampMixin, Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (
        Index("ix_ticket_messages_ticket_created_at", "ticket_id", "created_at"),
        Index(
            "ix_ticket_messages_ticket_visibility_created_at",
            "ticket_id",
            "visibility",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    author_type: Mapped[str] = mapped_column(
        enum_type(MessageAuthorType, name="message_author_type"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(MessageVisibility, name="message_visibility"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(enum_type(MessageSource, name="message_source"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
    )


class TicketAttachment(TimestampMixin, Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        Index("ix_ticket_attachments_ticket_id", "ticket_id"),
        Index("ix_ticket_attachments_message_id", "message_id"),
        Index("ix_ticket_attachments_sha256", "sha256"),
        CheckConstraint(
            "visibility = 'public' OR visibility = 'internal'",
            name="ck_ticket_attachments_visibility_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(AttachmentVisibility, name="attachment_visibility"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    stored_path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer())
    height: Mapped[int | None] = mapped_column(sa.Integer())


class TicketStatusHistory(TimestampMixin, Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (Index("ix_ticket_status_history_ticket_created_at", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(enum_type(TicketStatus, name="history_from_status"))
    to_status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="history_to_status"), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    changed_by_type: Mapped[str] = mapped_column(
        enum_type(StatusChangedByType, name="status_changed_by_type"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(sa.Text())


class TicketView(Base):
    __tablename__ = "ticket_views"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_viewed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class AiDraft(TimestampMixin, Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        Index("ix_ai_drafts_ticket_status_created_at_desc", "ticket_id", "status", sa.text("created_at DESC")),
        Index("ix_ai_drafts_ai_run_id", "ai_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(enum_type(AiDraftKind, name="ai_draft_kind"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(enum_type(AiDraftStatus, name="ai_draft_status"), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    published_message_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="SET NULL"),
    )


class SystemState(Base):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(sa.Text(), primary_key=True)
    value_json: Mapped[dict] = mapped_column(sa.JSON(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
