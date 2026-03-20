from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from scripts import bootstrap_workspace as bootstrap_workspace_script
from scripts import create_admin as create_admin_script
from scripts import create_user as create_user_script
from scripts import deactivate_user as deactivate_user_script
from scripts import run_web as run_web_script
from scripts import run_worker as run_worker_script
from scripts import set_password as set_password_script
from shared.bootstrap import bootstrap_workspace
from shared.config import Settings
from shared.models import Base, SystemState, User, UserRole
from shared.security import verify_password
from worker.main import run_worker_loop


def build_runtime(tmp_path: Path) -> tuple[sessionmaker, Settings]:
    db_path = tmp_path / "test.db"
    workspace_dir = tmp_path / "workspace"
    uploads_dir = tmp_path / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": f"sqlite+pysqlite:///{db_path}",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )
    return session_factory, settings


def test_bootstrap_workspace_script_creates_git_artifacts_and_bootstrap_state(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    exit_code = bootstrap_workspace_script.main(
        ["--bootstrap-version", "phase5-test"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert Path(payload["workspace_dir"], ".git").exists()
    assert Path(payload["uploads_dir"]).is_dir()
    assert Path(payload["workspace_dir"], "AGENTS.md").is_file()
    assert Path(payload["workspace_dir"], ".agents", "skills", "stage1-triage", "SKILL.md").is_file()
    assert Path(payload["workspace_dir"], "runs").is_dir()

    head = subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert head.returncode == 0
    assert head.stdout.strip()

    with session_factory() as session:
        bootstrap_row = session.get(SystemState, "bootstrap_version")
        assert bootstrap_row is not None
        assert bootstrap_row.value_json["version"] == "phase5-test"


def test_bootstrap_workspace_script_returns_error_when_required_mount_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)
    settings.manuals_mount_dir.rmdir()

    exit_code = bootstrap_workspace_script.main(
        [],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert "manuals mount is missing" in payload["error"]


def test_user_management_scripts_create_reset_and_deactivate_accounts(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_admin_script.main(
            [
                "--email",
                "Admin@Example.com",
                "--display-name",
                "Admin User",
                "--password",
                "secret-1",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        set_password_script.main(
            ["--email", "requester@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        deactivate_user_script.main(
            ["--email", "requester@example.com"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )

    with session_factory() as session:
        admin_user = session.scalar(sa.select(User).where(User.email == "admin@example.com"))
        requester_user = session.scalar(sa.select(User).where(User.email == "requester@example.com"))
        assert admin_user is not None
        assert requester_user is not None
        assert admin_user.role == UserRole.ADMIN.value
        assert verify_password(requester_user.password_hash, "changed-password")
        assert requester_user.is_active is False

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [line["status"] for line in lines] == ["ok", "ok", "ok", "ok"]


def test_user_management_scripts_report_duplicate_and_missing_user_errors(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )
    assert (
        set_password_script.main(
            ["--email", "missing@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["status"] == "ok"
    assert lines[1] == {"status": "error", "error": "User already exists: requester@example.com"}
    assert lines[2] == {"status": "error", "error": "User not found: missing@example.com"}


def test_health_and_readiness_routes_report_bootstrap_state(tmp_path: Path) -> None:
    session_factory, settings = build_runtime(tmp_path)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    health_response = client.get("/healthz")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    readiness_before = client.get("/readyz")
    assert readiness_before.status_code == 503
    issues = readiness_before.json()["issues"]
    assert any("uploads_dir missing" in issue for issue in issues)
    assert any("agents_md missing" in issue for issue in issues)

    bootstrap_workspace(settings, session_factory=session_factory)

    readiness_after = client.get("/readyz")
    assert readiness_after.status_code == 200
    assert readiness_after.json() == {"status": "ok"}


def test_readyz_reports_database_failure(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    bootstrap_workspace(settings, session_factory=session_factory)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    monkeypatch.setattr("app.main.check_database_readiness", lambda _factory: "db offline")
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["issues"][0] == "database not ready: db offline"


def test_worker_once_updates_heartbeat_system_state(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)

    monkeypatch.setattr("worker.main.process_next_run", lambda *args, **kwargs: None)
    run_worker_loop(settings=settings, session_factory=session_factory, once=True)

    with session_factory() as session:
        heartbeat = session.get(SystemState, "worker_heartbeat")
        assert heartbeat is not None
        timestamp = heartbeat.value_json["timestamp"]
        assert datetime.fromisoformat(timestamp).tzinfo == timezone.utc


def test_run_web_script_passes_configured_app_to_uvicorn(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_uvicorn_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("scripts.run_web.uvicorn.run", fake_uvicorn_run)

    exit_code = run_web_script.main(
        ["--host", "127.0.0.1", "--port", "9000"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["app"].title == "Stage 1 AI Triage MVP"
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 9000,
        "reload": False,
        "log_config": None,
        "access_log": False,
    }


def test_run_worker_script_passes_once_flag_to_worker_loop(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_worker_loop(*, settings, session_factory, once):
        captured["settings"] = settings
        captured["session_factory"] = session_factory
        captured["once"] = once

    monkeypatch.setattr("scripts.run_worker.run_worker_loop", fake_run_worker_loop)

    exit_code = run_worker_script.main(
        ["--once"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["settings"] == settings
    assert captured["session_factory"] is session_factory
    assert captured["once"] is True
