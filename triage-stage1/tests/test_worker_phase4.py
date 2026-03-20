from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AttachmentVisibility,
    Base,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    add_requester_reply,
    create_pending_ai_run,
    create_requester_ticket,
    create_ticket_message,
)
from worker.codex_runner import CodexExecutionError, CodexRunResult, EXACT_AGENTS_MD, EXACT_SKILL_MD
from worker.main import claim_next_run, finish_prepared_run, process_next_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context


def make_settings(database_url: str, workspace_dir: Path, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )


def build_session_factory():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-worker-test-"))
    db_path = temp_dir / "test.db"
    workspace_dir = temp_dir / "workspace"
    uploads_dir = temp_dir / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = make_settings(f"sqlite+pysqlite:///{db_path}", workspace_dir, uploads_dir)
    return session_factory, settings, temp_dir


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash="hashed",
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def create_ticket_fixture(
    session_factory: sessionmaker[Session],
    *,
    creator: User,
    title: str,
    body: str,
    created_at: datetime | None = None,
) -> tuple[Ticket, AiRun]:
    created_at = created_at or datetime.now(timezone.utc)
    with session_factory() as session:
        creator_db = session.get(User, creator.id)
        assert creator_db is not None
        ticket, _, run = create_requester_ticket(
            session,
            creator=creator_db,
            title=title,
            description_markdown=body,
            description_text=body,
            urgent=False,
            created_at=created_at,
        )
        session.commit()
        session.refresh(ticket)
        session.refresh(run)
        return ticket, run


def _success_payload(public_reply_markdown: str = "Please try the documented export flow.") -> dict[str, object]:
    return {
        "ticket_class": "support",
        "confidence": 0.96,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Export guidance",
        "summary_internal": "The ticket matches a documented support workflow.",
        "development_needed": False,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "manuals/export.md", "reason": "Contains the export steps."}],
        "recommended_next_action": "auto_public_reply",
        "auto_public_reply_allowed": True,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for Dev/TI.",
    }


def _clarification_payload(question: str = "Which export screen are you using?") -> dict[str, object]:
    return {
        "ticket_class": "unknown",
        "confidence": 0.62,
        "impact_level": "unknown",
        "requester_language": "en",
        "summary_short": "Need clarification",
        "summary_internal": "The request is ambiguous.",
        "development_needed": False,
        "needs_clarification": True,
        "clarifying_questions": [question],
        "incorrect_or_conflicting_details": [],
        "evidence_found": False,
        "relevant_paths": [],
        "recommended_next_action": "ask_clarification",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": question,
        "internal_note_markdown": "Internal ambiguity summary.",
    }


def _draft_payload(public_reply_markdown: str = "Please review this draft reply.") -> dict[str, object]:
    return {
        "ticket_class": "bug",
        "confidence": 0.72,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Needs review",
        "summary_internal": "The ticket needs a human-reviewed public response.",
        "development_needed": True,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "app/import.py", "reason": "Likely related implementation path."}],
        "recommended_next_action": "draft_public_reply",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for reviewer approval.",
    }


def test_worker_success_writes_workspace_artifacts_and_publishes_once(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requester@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need export help",
        body="I cannot find the export button.",
        created_at=datetime(2026, 3, 20, 9, tzinfo=timezone.utc),
    )

    attachment_path = settings.uploads_dir / "evidence.png"
    attachment_path.write_bytes(b"png")
    with session_factory() as session:
        initial_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.TICKET_CREATE.value,
            )
        )
        assert initial_message is not None
        session.add(
            TicketAttachment(
                ticket_id=ticket.id,
                message_id=initial_message.id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename="evidence.png",
                stored_path=str(attachment_path),
                mime_type="image/png",
                sha256="abc123",
                size_bytes=3,
                width=1,
                height=1,
            )
        )
        session.commit()

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 10, tzinfo=timezone.utc),
    )
    assert execution is not None
    command = execution.prepared_run.command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ask-for-approval" in command
    assert "never" in command
    assert "--json" in command
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert "--image" in command
    assert 'web_search="disabled"' in command
    assert execution.prepared_run.prompt_path.read_text(encoding="utf-8").startswith("$stage1-triage")
    assert (settings.triage_workspace_dir / "AGENTS.md").read_text(encoding="utf-8") == EXACT_AGENTS_MD
    assert (
        settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"
    ).read_text(encoding="utf-8") == EXACT_SKILL_MD

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout='{"event":"done"}\n', stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 10, 1, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value
    assert execution.prepared_run.final_output_path.exists()

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, execution.run_id)
        ai_internal_notes = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
            )
        ).all()
        ai_public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()

        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_USER.value
        assert ticket_db.last_ai_action == "auto_public_reply"
        assert ticket_db.ticket_class == "support"
        assert ticket_db.last_processed_hash
        assert run_db.status == AiRunStatus.SUCCEEDED.value
        assert len(ai_internal_notes) == 1
        assert len(ai_public_messages) == 1
        assert ai_public_messages[0].body_text == markdown_to_plain_text(payload["public_reply_markdown"])


def test_worker_marks_run_superseded_and_enqueues_single_requeue(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requeue@example.com", role=UserRole.REQUESTER.value)
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Intermittent export issue",
        body="The export is failing.",
        created_at=datetime(2026, 3, 20, 11, tzinfo=timezone.utc),
    )

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 1, tzinfo=timezone.utc),
    )
    assert execution is not None

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        requester_db = session.get(User, requester.id)
        assert ticket_db is not None
        assert requester_db is not None
        add_requester_reply(
            session,
            ticket=ticket_db,
            requester=requester_db,
            body_markdown="More detail: it fails only for large files.",
            body_text="More detail: it fails only for large files.",
            created_at=datetime(2026, 3, 20, 11, 2, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 11, 3, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUPERSEDED.value

    with session_factory() as session:
        original_run_db = session.get(AiRun, original_run.id)
        queued_runs = session.scalars(
            sa.select(AiRun)
            .where(AiRun.ticket_id == ticket.id)
            .order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ai_run_id == original_run.id)
        ).all()
        ticket_db = session.get(Ticket, ticket.id)

        assert original_run_db is not None
        assert ticket_db is not None
        assert original_run_db.status == AiRunStatus.SUPERSEDED.value
        assert len(queued_runs) == 2
        assert queued_runs[-1].status == AiRunStatus.PENDING.value
        assert queued_runs[-1].triggered_by == "requester_reply"
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None
        assert ai_messages == []


def test_worker_disables_automatic_publication_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="leak@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need help",
        body="I need help with the import flow.",
        created_at=datetime(2026, 3, 20, 11, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Reset the finance export entitlement for this requester before replying.",
            body_text="Reset the finance export entitlement for this requester before replying.",
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Please retry now.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 31, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 32, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        pending_draft = session.scalar(
            sa.select(AiDraft).where(
                AiDraft.ticket_id == ticket.id,
                AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "draft_public_reply"
        assert public_message is None
        assert pending_draft is not None


def test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="clarify@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Unsure which screen",
        body="The export is not working.",
        created_at=datetime(2026, 3, 20, 11, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Ops already suspects the legacy export screen is involved.",
            body_text="Ops already suspects the legacy export screen is involved.",
        )
        session.commit()

    payload = _clarification_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "route_dev_ti"
        assert public_message is None


def test_worker_skips_non_manual_run_when_fingerprint_matches_last_processed_hash() -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="skip@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Repeatable request",
        body="Please help with the same issue.",
        created_at=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        session.commit()

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
    )
    assert status is None

    with session_factory() as session:
        run_db = session.get(AiRun, run.id)
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ticket_id == ticket.id, TicketMessage.ai_run_id == run.id)
        ).all()
        assert run_db is not None
        assert run_db.status == AiRunStatus.SKIPPED.value
        assert ai_messages == []


def test_worker_processes_manual_rerun_even_when_fingerprint_matches_last_processed_hash(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="manual@example.com", role=UserRole.REQUESTER.value)
    ops_user = seed_user(session_factory, email="ops-manual@example.com", role=UserRole.DEV_TI.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Manual rerun request",
        body="Please retry triage.",
        created_at=datetime(2026, 3, 20, 12, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        ops_db = session.get(User, ops_user.id)
        run_db = session.get(AiRun, run.id)
        assert ticket_db is not None
        assert ops_db is not None
        assert run_db is not None
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        run_db.status = AiRunStatus.SUCCEEDED.value
        run_db.ended_at = datetime(2026, 3, 20, 12, 31, tzinfo=timezone.utc)
        session.flush()
        create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by="manual_rerun",
            requested_by_user_id=ops_db.id,
            created_at=datetime(2026, 3, 20, 12, 32, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Manual rerun completed successfully.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 33, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 34, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        runs = session.scalars(
            sa.select(AiRun).where(AiRun.ticket_id == ticket.id).order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()
        assert [item.status for item in runs] == [AiRunStatus.SUCCEEDED.value, AiRunStatus.SUCCEEDED.value]
        assert runs[-1].triggered_by == "manual_rerun"
        assert len(public_messages) == 1


def test_worker_new_draft_supersedes_older_pending_draft(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="drafts@example.com", role=UserRole.REQUESTER.value)
    ticket, current_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Draft supersede",
        body="Need a reviewed reply.",
        created_at=datetime(2026, 3, 20, 12, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        current_run_db = session.get(AiRun, current_run.id)
        assert current_run_db is not None
        historical_run = AiRun(
            ticket_id=ticket.id,
            status=AiRunStatus.SUCCEEDED.value,
            triggered_by="new_ticket",
            requested_by_user_id=requester.id,
            created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            ended_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
        )
        session.add(historical_run)
        session.flush()
        session.add(
            AiDraft(
                ticket_id=ticket.id,
                ai_run_id=historical_run.id,
                kind="public_reply",
                body_markdown="Older pending draft.",
                body_text="Older pending draft.",
                status=AiDraftStatus.PENDING_APPROVAL.value,
                created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            )
        )
        session.commit()

    payload = _draft_payload(public_reply_markdown="New draft awaiting review.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        drafts = session.scalars(
            sa.select(AiDraft).where(AiDraft.ticket_id == ticket.id).order_by(AiDraft.created_at.asc(), AiDraft.id.asc())
        ).all()
        assert len(drafts) == 2
        assert drafts[0].status == AiDraftStatus.SUPERSEDED.value
        assert drafts[1].status == AiDraftStatus.PENDING_APPROVAL.value
        assert drafts[1].body_text == "New draft awaiting review."


def test_worker_failure_routes_ticket_to_dev_ti_and_adds_internal_failure_note(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="failure@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Broken triage",
        body="This should fail.",
        created_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )

    def fake_run_codex(_prepared_run, *, settings):
        raise CodexExecutionError("Codex exited with status 2")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 13, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 13, 2, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.FAILED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, run.id)
        failure_note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.SYSTEM.value,
            )
        )
        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert run_db.status == AiRunStatus.FAILED.value
        assert run_db.error_text == "Codex exited with status 2"
        assert failure_note is not None
