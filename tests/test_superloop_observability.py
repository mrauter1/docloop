from __future__ import annotations

import json
from pathlib import Path

import superloop

from superloop import (
    EventRecorder,
    append_raw_phase_log,
    append_run_log,
    create_run_paths,
    derive_intent_task_id,
    ensure_workspace,
    latest_run_id,
    latest_task_id,
    load_resume_checkpoint,
    open_existing_run_paths,
    latest_run_status,
    resolve_task_id,
    task_id_for_run,
    write_run_summary,
)


def test_create_run_paths_creates_per_run_artifacts(tmp_path: Path):
    run_paths = create_run_paths(tmp_path, "run-test-123")

    assert run_paths["run_dir"].is_dir()
    assert run_paths["run_log"].exists()
    assert run_paths["raw_phase_log"].exists()
    assert run_paths["events_file"].exists()
    assert run_paths["summary_file"].parent == run_paths["run_dir"]


def test_open_existing_run_paths_reuses_existing_artifacts(tmp_path: Path):
    create_run_paths(tmp_path, "run-test-123")
    opened = open_existing_run_paths(tmp_path, "run-test-123")
    assert opened["run_dir"].name == "run-test-123"
    assert opened["events_file"].exists()


def test_raw_phase_log_includes_run_cycle_attempt(tmp_path: Path):
    raw_log = tmp_path / "raw_phase_log.md"
    raw_log.write_text("# Raw\n", encoding="utf-8")

    append_raw_phase_log(
        raw_log,
        pair="implement",
        phase="producer",
        cycle=2,
        attempt=3,
        process_name="codex-agent",
        stdout="hello",
        run_id="run-xyz",
    )

    text = raw_log.read_text(encoding="utf-8")
    assert "run_id=run-xyz" in text
    assert "pair=implement" in text
    assert "cycle=2" in text
    assert "attempt=3" in text


def test_event_recorder_and_summary_counts(tmp_path: Path):
    run_paths = create_run_paths(tmp_path, "run-abc")
    recorder = EventRecorder(run_id="run-abc", events_file=run_paths["events_file"])

    recorder.emit("pair_started", pair="plan")
    recorder.emit("phase_output_empty", pair="plan", phase="producer", cycle=1, attempt=1)
    recorder.emit("missing_promise_default", pair="plan", cycle=1, attempt=1)
    recorder.emit("pair_completed", pair="plan", cycle=1, attempt=1)
    recorder.emit("run_finished", status="success")

    events = [json.loads(line) for line in run_paths["events_file"].read_text(encoding="utf-8").splitlines() if line]
    assert [e["seq"] for e in events] == [1, 2, 3, 4, 5]

    write_run_summary(run_paths["summary_file"], "run-abc", run_paths["events_file"])
    summary = run_paths["summary_file"].read_text(encoding="utf-8")
    assert "phase_output_empty: 1" in summary
    assert "missing_promise_default: 1" in summary
    assert "pair_completed events: 1" in summary


def test_load_resume_checkpoint_skips_completed_pairs_and_continues_cycle(tmp_path: Path):
    run_paths = create_run_paths(tmp_path, "run-abc")
    recorder = EventRecorder(run_id="run-abc", events_file=run_paths["events_file"])
    recorder.emit("pair_completed", pair="plan", cycle=1, attempt=1)
    recorder.emit("phase_finished", pair="implement", phase="producer", cycle=2, attempt=3)

    checkpoint = load_resume_checkpoint(run_paths["events_file"], ["plan", "implement", "test"])
    assert checkpoint.pair_start_index == 1
    assert checkpoint.cycle_by_pair["implement"] == 1
    assert checkpoint.attempts_by_pair_cycle[("implement", 2)] == 3


def test_append_run_log_scopes_entries(tmp_path: Path):
    run_log = tmp_path / "run_log.md"
    run_log.write_text("# Run\n", encoding="utf-8")

    append_run_log(run_log, "Started pair `plan`", run_id="run-1", pair="plan", cycle=1, attempt=2)

    text = run_log.read_text(encoding="utf-8")
    assert "run_id=run-1" in text
    assert "pair=plan" in text
    assert "cycle=1" in text
    assert "attempt=2" in text


def test_main_fatal_error_still_writes_terminal_event_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(superloop, "check_dependencies", lambda require_git=True: None)
    monkeypatch.setattr(superloop, "resolve_codex_exec_command", lambda model: ["codex", "exec"])
    monkeypatch.setattr(
        superloop,
        "run_codex_phase",
        lambda *args, **kwargs: "<loop-control>{not-json}</loop-control>",
    )

    monkeypatch.setattr(
        superloop.sys,
        "argv",
        [
            "superloop.py",
            "--workspace",
            str(tmp_path),
            "--pairs",
            "plan",
            "--task-id",
            "fatal-test",
            "--max-iterations",
            "1",
            "--no-git",
        ],
    )

    exit_code = superloop.main()
    assert exit_code == 1

    task_root = tmp_path / ".superloop" / "tasks" / "fatal-test"
    runs_root = task_root / "runs"
    run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1

    events = [
        json.loads(line)
        for line in (run_dirs[0] / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert events[-1]["event_type"] == "run_finished"
    assert events[-1]["status"] == "fatal_error"

    summary_text = (run_dirs[0] / "summary.md").read_text(encoding="utf-8")
    assert "Superloop Run Summary" in summary_text


def test_resolve_task_id_uses_task_id_or_intent():
    assert resolve_task_id("Custom Task", None) == "custom-task"
    assert resolve_task_id(None, "Implement refined reflow v1.2") == derive_intent_task_id("Implement refined reflow v1.2")


def test_latest_task_and_run_helpers(tmp_path: Path):
    task_a = tmp_path / "tasks" / "a"
    task_b = tmp_path / "tasks" / "b"
    task_a.mkdir(parents=True)
    task_b.mkdir(parents=True)
    assert latest_task_id(tmp_path / "tasks") in {"a", "b"}

    runs = tmp_path / "runs"
    (runs / "run-1").mkdir(parents=True)
    (runs / "run-2").mkdir(parents=True)
    assert latest_run_id(runs) in {"run-1", "run-2"}




def test_latest_task_id_prefers_created_at_over_mtime(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    task_old = tasks_dir / "task-old"
    task_new = tasks_dir / "task-new"
    task_old.mkdir(parents=True)
    task_new.mkdir(parents=True)

    (task_old / "task.json").write_text('{"created_at":"2026-01-01T00:00:00Z"}\n', encoding="utf-8")
    (task_new / "task.json").write_text('{"created_at":"2026-01-02T00:00:00Z"}\n', encoding="utf-8")

    # Make filesystem mtime misleading on purpose.
    import os
    os.utime(task_old, (2000000000, 2000000000))
    os.utime(task_new, (1000000000, 1000000000))

    assert latest_task_id(tasks_dir) == "task-new"


def test_latest_run_id_prefers_run_timestamp_over_mtime(tmp_path: Path):
    run_new = tmp_path / "run-20260316T110008Z-aaaaaaaa"
    run_old = tmp_path / "run-20260316T103559Z-bbbbbbbb"
    run_new.mkdir(parents=True)
    run_old.mkdir(parents=True)

    import os
    os.utime(run_new, (1000000000, 1000000000))
    os.utime(run_old, (2000000000, 2000000000))

    assert latest_run_id(tmp_path) == "run-20260316T110008Z-aaaaaaaa"


def test_latest_run_status_reads_last_run_finished(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        '{"event_type":"run_finished","status":"failed"}\n'
        '{"event_type":"run_started"}\n'
        '{"event_type":"run_finished","status":"success"}\n',
        encoding="utf-8",
    )
    assert latest_run_status(events) == "success"

def test_main_resume_refuses_terminal_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(superloop, "check_dependencies", lambda require_git=True: None)
    monkeypatch.setattr(superloop, "resolve_codex_exec_command", lambda model: ["codex", "exec"])

    paths = ensure_workspace(
        root=tmp_path,
        task_id="resume-task",
        product_intent=None,
        intent_mode="preserve",
    )
    run_paths = create_run_paths(paths["runs_dir"], "run-20260316T120000Z-abcdef12")
    recorder = EventRecorder(run_id="run-20260316T120000Z-abcdef12", events_file=run_paths["events_file"])
    recorder.emit("run_finished", status="success")

    monkeypatch.setattr(
        superloop.sys,
        "argv",
        [
            "superloop.py",
            "--workspace",
            str(tmp_path),
            "--pairs",
            "plan",
            "--task-id",
            "resume-task",
            "--resume",
            "--run-id",
            "run-20260316T120000Z-abcdef12",
            "--no-git",
        ],
    )

    import pytest
    with pytest.raises(SystemExit):
        superloop.main()

def test_task_id_for_run_finds_task_containing_run(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    (tasks_dir / "task-x" / "runs" / "run-1").mkdir(parents=True)
    (tasks_dir / "task-y" / "runs" / "run-2").mkdir(parents=True)
    assert task_id_for_run(tasks_dir, "run-2") == "task-y"


def test_resolve_task_id_preserves_long_explicit_task_ids():
    intent_a = "Implement refined reflow v1.2 with strict verification and artifact scoping alpha"
    intent_b = "Implement refined reflow v1.2 with strict verification and artifact scoping beta"
    assert resolve_task_id(intent_a, None) == superloop.slugify_task(intent_a)
    assert resolve_task_id(intent_b, None) == superloop.slugify_task(intent_b)
    assert resolve_task_id(intent_a, None) != resolve_task_id(intent_b, None)


def test_derive_intent_task_id_truncates_long_slug_but_keeps_hash_uniqueness():
    intent_a = "x " * 300
    intent_b = "x " * 299 + "y"

    task_id_a = derive_intent_task_id(intent_a)
    task_id_b = derive_intent_task_id(intent_b)

    assert len(task_id_a.split("-")[-1]) == 8
    assert len(task_id_a) <= 57
    assert task_id_a != task_id_b


def test_derive_intent_task_id_strips_trailing_hyphen_from_truncated_slug():
    intent = ("abc-" * 20) + "tail"

    task_id = derive_intent_task_id(intent)
    slug, digest = task_id.rsplit("-", 1)

    assert not slug.endswith("-")
    assert len(digest) == 8


def test_ensure_workspace_accepts_long_intent_derived_task_ids(tmp_path: Path):
    intent = "x " * 300

    task_id = derive_intent_task_id(intent)
    paths = ensure_workspace(
        root=tmp_path,
        task_id=task_id,
        product_intent=intent,
        intent_mode="preserve",
    )

    assert paths["task_dir"].name == task_id
    assert paths["task_dir"].is_dir()
    assert (paths["task_dir"] / "task.json").exists()


def test_resume_accepts_long_explicit_task_id(tmp_path: Path, monkeypatch):
    task_id = "implement-refined-reflow-v1-2-sad-md-as-function-d391842d"
    paths = ensure_workspace(
        root=tmp_path,
        task_id=task_id,
        product_intent=None,
        intent_mode="preserve",
    )
    create_run_paths(paths["runs_dir"], "run-20260316T120000Z-abcdef12")
    control = superloop.LoopControl(
        question=None,
        promise=superloop.PROMISE_COMPLETE,
        source="canonical",
        raw_payload=None,
    )

    monkeypatch.setattr(superloop, "check_dependencies", lambda require_git=True: None)
    monkeypatch.setattr(superloop, "resolve_codex_exec_command", lambda model: ["codex", "exec"])
    monkeypatch.setattr(superloop, "run_codex_phase", lambda *args, **kwargs: "<loop-control></loop-control>")
    monkeypatch.setattr(superloop, "parse_phase_control", lambda *args, **kwargs: control)
    monkeypatch.setattr(superloop, "criteria_all_checked", lambda *_args, **_kwargs: True)

    monkeypatch.setattr(
        superloop.sys,
        "argv",
        [
            "superloop.py",
            "--workspace",
            str(tmp_path),
            "--pairs",
            "plan",
            "--task-id",
            task_id,
            "--resume",
            "--run-id",
            "run-20260316T120000Z-abcdef12",
            "--max-iterations",
            "1",
            "--no-git",
        ],
    )

    exit_code = superloop.main()
    assert exit_code == 0


def test_ensure_workspace_creates_task_scoped_paths_and_task_prompts(tmp_path: Path):
    paths = ensure_workspace(
        root=tmp_path,
        task_id="my-task",
        product_intent="Implement feature X",
        intent_mode="replace",
    )

    task_dir = tmp_path / ".superloop" / "tasks" / "my-task"
    assert paths["task_dir"] == task_dir
    assert (task_dir / "task.json").exists()
    assert (task_dir / "context.md").exists()
    assert (task_dir / "plan" / "prompt.md").exists()

    plan_prompt = (task_dir / "plan" / "prompt.md").read_text(encoding="utf-8")
    assert ".superloop/tasks/my-task/plan/plan.md" in plan_prompt
    assert ".superloop/plan/plan.md" not in plan_prompt


def test_ensure_workspace_preserve_mode_keeps_existing_context(tmp_path: Path):
    ensure_workspace(
        root=tmp_path,
        task_id="same-task",
        product_intent="Intent A",
        intent_mode="replace",
    )
    ensure_workspace(
        root=tmp_path,
        task_id="same-task",
        product_intent="Intent B",
        intent_mode="preserve",
    )

    context_text = (tmp_path / ".superloop" / "tasks" / "same-task" / "context.md").read_text(encoding="utf-8")
    assert "Intent A" in context_text
    assert "Intent B" not in context_text
