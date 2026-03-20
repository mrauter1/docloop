"""Initial Stage 1 triage schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            enum_type("user_role", "requester", "dev_ti", "admin"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("csrf_token", sa.Text(), nullable=False),
        sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip_address", sa.Text()),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("reference_num", sa.BigInteger(), sa.Identity(start=1), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "status",
            enum_type(
                "ticket_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "ticket_class",
            enum_type(
                "ticket_class",
                "support",
                "access_config",
                "data_ops",
                "bug",
                "feature",
                "unknown",
            ),
        ),
        sa.Column("ai_confidence", sa.Numeric(4, 3)),
        sa.Column("impact_level", enum_type("impact_level", "low", "medium", "high", "unknown")),
        sa.Column("development_needed", sa.Boolean()),
        sa.Column(
            "clarification_rounds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("requester_language", sa.Text()),
        sa.Column("last_processed_hash", sa.Text()),
        sa.Column("last_ai_action", sa.Text()),
        sa.Column("requeue_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "requeue_trigger",
            enum_type("ticket_requeue_trigger", "requester_reply", "manual_rerun", "reopen"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("reference_num"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_tickets_status_updated_at", "tickets", ["status", sa.text("updated_at DESC")])
    op.create_index(
        "ix_tickets_created_by_updated_at",
        "tickets",
        ["created_by_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_assigned_to_updated_at",
        "tickets",
        ["assigned_to_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_urgent_status_updated_at",
        "tickets",
        ["urgent", "status", sa.text("updated_at DESC")],
    )

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_run_status",
                "pending",
                "running",
                "succeeded",
                "failed",
                "skipped",
                "superseded",
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            enum_type("ai_run_trigger", "new_ticket", "requester_reply", "manual_rerun", "reopen"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("input_hash", sa.Text()),
        sa.Column("model_name", sa.Text()),
        sa.Column("prompt_path", sa.Text()),
        sa.Column("schema_path", sa.Text()),
        sa.Column("final_output_path", sa.Text()),
        sa.Column("stdout_jsonl_path", sa.Text()),
        sa.Column("stderr_path", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("error_text", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ai_runs_status_created_at", "ai_runs", ["status", "created_at"])
    op.create_index("ix_ai_runs_ticket_created_at_desc", "ai_runs", ["ticket_id", sa.text("created_at DESC")])
    op.create_index(
        "uq_ai_runs_ticket_active",
        "ai_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "author_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "author_type",
            enum_type("message_author_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("message_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column(
            "source",
            enum_type(
                "message_source",
                "ticket_create",
                "requester_reply",
                "human_public_reply",
                "human_internal_note",
                "ai_auto_public",
                "ai_internal_note",
                "ai_draft_published",
                "system",
            ),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "ai_run_id",
            sa.Uuid(),
            sa.ForeignKey("ai_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_messages_ticket_created_at", "ticket_messages", ["ticket_id", "created_at"])
    op.create_index(
        "ix_ticket_messages_ticket_visibility_created_at",
        "ticket_messages",
        ["ticket_id", "visibility", "created_at"],
    )

    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("attachment_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
    op.create_index("ix_ticket_attachments_message_id", "ticket_attachments", ["message_id"])
    op.create_index("ix_ticket_attachments_sha256", "ticket_attachments", ["sha256"])

    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "from_status",
            enum_type(
                "history_from_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
        ),
        sa.Column(
            "to_status",
            enum_type(
                "history_to_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column(
            "changed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "changed_by_type",
            enum_type("status_changed_by_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_ticket_status_history_ticket_created_at",
        "ticket_status_history",
        ["ticket_id", "created_at"],
    )

    op.create_table(
        "ticket_views",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "last_viewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "kind",
            enum_type("ai_draft_kind", "public_reply"),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_draft_status",
                "pending_approval",
                "approved",
                "rejected",
                "superseded",
                "published",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "published_message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_ai_drafts_ticket_status_created_at_desc",
        "ai_drafts",
        ["ticket_id", "status", sa.text("created_at DESC")],
    )
    op.create_index("ix_ai_drafts_ai_run_id", "ai_drafts", ["ai_run_id"])

    op.create_table(
        "system_state",
        sa.Column("key", sa.Text(), primary_key=True, nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
    op.drop_index("ix_ai_drafts_ai_run_id", table_name="ai_drafts")
    op.drop_index("ix_ai_drafts_ticket_status_created_at_desc", table_name="ai_drafts")
    op.drop_table("ai_drafts")
    op.drop_table("ticket_views")
    op.drop_index("ix_ticket_status_history_ticket_created_at", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")
    op.drop_index("ix_ticket_attachments_sha256", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_message_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_ticket_id", table_name="ticket_attachments")
    op.drop_table("ticket_attachments")
    op.drop_index("ix_ticket_messages_ticket_visibility_created_at", table_name="ticket_messages")
    op.drop_index("ix_ticket_messages_ticket_created_at", table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_index("uq_ai_runs_ticket_active", table_name="ai_runs")
    op.drop_index("ix_ai_runs_ticket_created_at_desc", table_name="ai_runs")
    op.drop_index("ix_ai_runs_status_created_at", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_index("ix_tickets_urgent_status_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_assigned_to_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_created_by_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_status_updated_at", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("sessions")
    op.drop_table("users")
