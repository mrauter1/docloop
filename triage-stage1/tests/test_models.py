from __future__ import annotations

from pathlib import Path

from shared.models import AiRun, Base, TicketView


def test_ai_runs_has_partial_unique_index_for_active_statuses() -> None:
    index = next(index for index in AiRun.__table__.indexes if index.name == "uq_ai_runs_ticket_active")
    predicate = str(index.dialect_options["postgresql"]["where"])

    assert index.unique is True
    assert "pending" in predicate
    assert "running" in predicate


def test_ticket_views_primary_key_matches_prd() -> None:
    primary_key = TicketView.__table__.primary_key

    assert [column.name for column in primary_key.columns] == ["user_id", "ticket_id"]


def test_initial_migration_declares_active_run_partial_index() -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "shared"
        / "migrations"
        / "versions"
        / "20260319_0001_initial.py"
    )
    content = migration_path.read_text()

    assert "uq_ai_runs_ticket_active" in content
    assert "status IN ('pending', 'running')" in content


def test_metadata_contains_all_prd_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "tickets",
        "ticket_messages",
        "ticket_attachments",
        "ticket_status_history",
        "ticket_views",
        "ai_runs",
        "ai_drafts",
        "system_state",
    }
