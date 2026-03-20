from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.db import session_scope
from shared.models import SystemState
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD


DEFAULT_BOOTSTRAP_VERSION = "1.2-custom-final"


class WorkspaceBootstrapError(RuntimeError):
    """Raised when the workspace bootstrap contract cannot be satisfied."""


@dataclass(frozen=True)
class WorkspaceBootstrapResult:
    uploads_dir: str
    workspace_dir: str
    repo_mount_dir: str
    manuals_mount_dir: str
    git_initialized: bool
    initial_commit_created: bool
    agents_written: bool
    skill_written: bool
    bootstrap_version_written: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def workspace_agents_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "AGENTS.md"


def workspace_skill_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"


def workspace_runs_dir(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "runs"


def _write_if_changed(path: Path, content: str) -> bool:
    existing = None
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def ensure_workspace_files(settings: Settings) -> tuple[bool, bool]:
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
    workspace_runs_dir(settings).mkdir(parents=True, exist_ok=True)
    agents_written = _write_if_changed(workspace_agents_path(settings), EXACT_AGENTS_MD)
    skill_written = _write_if_changed(workspace_skill_path(settings), EXACT_SKILL_MD)
    return agents_written, skill_written


def _run_git(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_workspace_git_repository(settings: Settings) -> tuple[bool, bool]:
    git_dir = settings.triage_workspace_dir / ".git"
    git_initialized = False
    initial_commit_created = False

    if not git_dir.exists():
        settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
        completed = _run_git(settings, "init")
        if completed.returncode != 0:
            raise WorkspaceBootstrapError(completed.stderr.strip() or "git init failed")
        git_initialized = True

    head_check = _run_git(settings, "rev-parse", "--verify", "HEAD")
    if head_check.returncode != 0:
        commit = _run_git(
            settings,
            "-c",
            "user.name=Stage 1 Bootstrap",
            "-c",
            "user.email=stage1-triage@local",
            "commit",
            "--allow-empty",
            "-m",
            "Initialize workspace",
        )
        if commit.returncode != 0:
            raise WorkspaceBootstrapError(commit.stderr.strip() or "git commit --allow-empty failed")
        initial_commit_created = True

    return git_initialized, initial_commit_created


def verify_required_path(path: Path, *, label: str, must_be_directory: bool = True) -> None:
    if not path.exists():
        raise WorkspaceBootstrapError(f"{label} is missing: {path}")
    if must_be_directory and not path.is_dir():
        raise WorkspaceBootstrapError(f"{label} is not a directory: {path}")
    if not os.access(path, os.R_OK):
        raise WorkspaceBootstrapError(f"{label} is not readable: {path}")


def workspace_readiness_issues(settings: Settings) -> list[str]:
    issues: list[str] = []

    def check(path: Path, *, label: str, must_be_directory: bool = True, exact_text: str | None = None) -> None:
        if not path.exists():
            issues.append(f"{label} missing: {path}")
            return
        if must_be_directory and not path.is_dir():
            issues.append(f"{label} not a directory: {path}")
            return
        if not os.access(path, os.R_OK):
            issues.append(f"{label} not readable: {path}")
            return
        if exact_text is not None and path.read_text(encoding="utf-8") != exact_text:
            issues.append(f"{label} content mismatch: {path}")

    check(settings.uploads_dir, label="uploads_dir")
    check(settings.triage_workspace_dir, label="triage_workspace_dir")
    check(settings.repo_mount_dir, label="repo_mount_dir")
    check(settings.manuals_mount_dir, label="manuals_mount_dir")
    check(workspace_runs_dir(settings), label="workspace_runs_dir")
    check(workspace_agents_path(settings), label="agents_md", must_be_directory=False, exact_text=EXACT_AGENTS_MD)
    check(workspace_skill_path(settings), label="skill_md", must_be_directory=False, exact_text=EXACT_SKILL_MD)
    return issues


def check_database_readiness(session_factory: sessionmaker[Session]) -> str | None:
    try:
        with session_scope(session_factory) as session:
            session.execute(sa.text("SELECT 1"))
        return None
    except Exception as exc:  # pragma: no cover - error path exercised in app tests via monkeypatch
        return str(exc)


def write_bootstrap_version(
    session_factory: sessionmaker[Session],
    *,
    version: str = DEFAULT_BOOTSTRAP_VERSION,
    updated_at: datetime | None = None,
) -> bool:
    updated_at = updated_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, "bootstrap_version")
        payload = {"version": version, "updated_at": updated_at.isoformat()}
        if row is None:
            session.add(SystemState(key="bootstrap_version", value_json=payload, updated_at=updated_at))
            return True
        row.value_json = payload
        row.updated_at = updated_at
        return True


def bootstrap_workspace(
    settings: Settings,
    *,
    session_factory: sessionmaker[Session] | None = None,
    bootstrap_version: str = DEFAULT_BOOTSTRAP_VERSION,
) -> WorkspaceBootstrapResult:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)

    git_initialized, initial_commit_created = ensure_workspace_git_repository(settings)
    verify_required_path(settings.repo_mount_dir, label="repo mount")
    verify_required_path(settings.manuals_mount_dir, label="manuals mount")
    agents_written, skill_written = ensure_workspace_files(settings)

    bootstrap_version_written = False
    if session_factory is not None:
        bootstrap_version_written = write_bootstrap_version(
            session_factory,
            version=bootstrap_version,
        )

    return WorkspaceBootstrapResult(
        uploads_dir=str(settings.uploads_dir),
        workspace_dir=str(settings.triage_workspace_dir),
        repo_mount_dir=str(settings.repo_mount_dir),
        manuals_mount_dir=str(settings.manuals_mount_dir),
        git_initialized=git_initialized,
        initial_commit_created=initial_commit_created,
        agents_written=agents_written,
        skill_written=skill_written,
        bootstrap_version_written=bootstrap_version_written,
    )
