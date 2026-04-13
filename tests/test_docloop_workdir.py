from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from docloop import (
    assert_grounding_unchanged,
    build_prompt_payload,
    build_workspace,
    capture_grounding_snapshot,
    init_workspace,
    prompt_for_grounding_mode,
    resolve_grounding_workdir,
    select_run_mode,
)


def test_resolve_grounding_workdir_rejects_missing_directory(tmp_path: Path):
    missing_dir = tmp_path / "missing"

    with pytest.raises(SystemExit):
        resolve_grounding_workdir(str(missing_dir))


def test_prompt_for_grounding_mode_accepts_current_directory_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "1")

    assert prompt_for_grounding_mode() == tmp_path.resolve()


def test_prompt_for_grounding_mode_accepts_greenfield_choice(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "2")

    assert prompt_for_grounding_mode() is None


def test_prompt_for_grounding_mode_requires_explicit_flag_when_non_interactive(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(SystemExit):
        prompt_for_grounding_mode()


def test_build_workspace_keeps_artifact_root_grounding_workdir_and_exec_cwd_independent(tmp_path: Path):
    artifact_root = tmp_path / "plans"
    grounding_workdir = tmp_path / "service"
    exec_cwd = tmp_path / "exec"
    grounding_workdir.mkdir()
    exec_cwd.mkdir()

    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=grounding_workdir,
        exec_cwd=exec_cwd,
    )

    assert workspace.artifact_root == artifact_root.resolve()
    assert workspace.grounding_workdir == grounding_workdir.resolve()
    assert workspace.exec_cwd == exec_cwd.resolve()
    assert workspace.target_doc == (artifact_root / "PRD.md").resolve()
    assert workspace.docloop_dir == (artifact_root / ".docloop").resolve()


def test_init_workspace_creates_docloop_artifacts_next_to_output_not_grounding_workdir(tmp_path: Path):
    artifact_root = tmp_path / "plans"
    grounding_workdir = tmp_path / "service"
    exec_cwd = tmp_path / "exec"
    grounding_workdir.mkdir()
    exec_cwd.mkdir()
    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=grounding_workdir,
        exec_cwd=exec_cwd,
    )

    init_workspace(
        workspace,
        target_seed=None,
        run_mode=select_run_mode(workspace, update_mode=False),
        update_text=None,
        use_git=False,
    )

    assert workspace.target_doc.exists()
    assert workspace.docloop_dir.exists()
    assert not (grounding_workdir / ".docloop").exists()
    assert not (grounding_workdir / "PRD.md").exists()


def test_build_prompt_payload_includes_grounding_and_execution_context(tmp_path: Path):
    artifact_root = tmp_path / "plans"
    grounding_workdir = tmp_path / "service"
    exec_cwd = tmp_path / "exec"
    grounding_workdir.mkdir()
    exec_cwd.mkdir()
    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=grounding_workdir,
        exec_cwd=exec_cwd,
    )
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Writer instructions go here.", encoding="utf-8")

    payload = build_prompt_payload(workspace, prompt_file)

    assert str(workspace.grounding_workdir) in payload
    assert str(workspace.exec_cwd) in payload
    assert str(workspace.target_doc) in payload
    assert str(workspace.context_file) in payload
    assert str(workspace.criteria_file) in payload
    assert "Do not edit files under `GROUNDING WORKDIR`" in payload


def test_build_prompt_payload_marks_greenfield_runs(tmp_path: Path):
    artifact_root = tmp_path / "plans"
    exec_cwd = tmp_path / "exec"
    exec_cwd.mkdir()
    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=None,
        exec_cwd=exec_cwd,
    )
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Writer instructions go here.", encoding="utf-8")

    payload = build_prompt_payload(workspace, prompt_file)

    assert "GROUNDING WORKDIR: [none]" in payload
    assert "treat this as a greenfield project" in payload


def test_capture_grounding_snapshot_ignores_managed_artifact_changes_inside_grounding_tree(tmp_path: Path):
    grounding_workdir = tmp_path
    exec_cwd = tmp_path
    artifact_root = tmp_path
    code_file = tmp_path / "code.py"
    code_file.write_text("print('hello')\n", encoding="utf-8")
    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=grounding_workdir,
        exec_cwd=exec_cwd,
    )

    init_workspace(
        workspace,
        target_seed=None,
        run_mode=select_run_mode(workspace, update_mode=False),
        update_text=None,
        use_git=False,
    )
    before = capture_grounding_snapshot(workspace)

    workspace.target_doc.write_text("# Updated\n", encoding="utf-8")
    (workspace.docloop_dir / "progress.txt").write_text("updated\n", encoding="utf-8")

    assert capture_grounding_snapshot(workspace) == before


def test_assert_grounding_unchanged_rejects_unmanaged_changes(tmp_path: Path):
    grounding_workdir = tmp_path / "service"
    artifact_root = tmp_path / "plans"
    exec_cwd = grounding_workdir
    grounding_workdir.mkdir()
    (grounding_workdir / "code.py").write_text("print('hello')\n", encoding="utf-8")
    workspace = build_workspace(
        artifact_root / "PRD.md",
        grounding_workdir=grounding_workdir,
        exec_cwd=exec_cwd,
    )

    init_workspace(
        workspace,
        target_seed=None,
        run_mode=select_run_mode(workspace, update_mode=False),
        update_text=None,
        use_git=False,
    )
    before = capture_grounding_snapshot(workspace)

    (grounding_workdir / "code.py").write_text("print('changed')\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        assert_grounding_unchanged(before, workspace, "writer")


def test_greenfield_workspace_can_use_temporary_exec_cwd(tmp_path: Path):
    artifact_root = tmp_path / "plans"
    with tempfile.TemporaryDirectory(prefix="docloop-test-") as temp_dir:
        exec_cwd = Path(temp_dir)
        workspace = build_workspace(
            artifact_root / "PRD.md",
            grounding_workdir=None,
            exec_cwd=exec_cwd,
        )

        assert workspace.grounding_workdir is None
        assert workspace.exec_cwd == exec_cwd.resolve()
