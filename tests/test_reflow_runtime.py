from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

import reflow
import reflow_runtime.controller as controller_module
from reflow_runtime.controller import (
    init_workflow,
    list_runs,
    reply_to_run,
    resume_run,
    run_new_workflow,
    status_run,
    stop_run,
    validate_workflow,
)
from reflow_runtime.loaders import load_config, load_instruction_body, load_workflow
from reflow_runtime.models import ConfigError, EXIT_CODE_AWAITING_INPUT, InvocationResult
from reflow_runtime.policy import evaluate_policy, snapshot_workspace
from reflow_runtime.protocol import parse_agent_outcome, parse_full_auto_answers, render_agent_request
from reflow_runtime.providers import build_provider_argv, invoke_shell
from reflow_runtime.storage import RunStore, atomic_write_json


FAKE_CODEX = """#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

args = sys.argv[1:]
request = args[-1]
final_path = Path(args[args.index("--output-last-message") + 1])
state_path = Path(os.environ["FAKE_STATE"])
scenario = os.environ["FAKE_SCENARIO"]
state = {}
if state_path.exists():
    state = json.loads(state_path.read_text())

def parse_operator_inputs_path(text):
    match = re.search(r"^- operator_inputs: (.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None

def step_name(text):
    match = re.search(r"^- step: (.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "unknown"

operator_inputs = parse_operator_inputs_path(request)
operator_inputs_text = ""
if operator_inputs:
    path = Path(operator_inputs)
    if not path.is_absolute():
        path = Path.cwd() / operator_inputs
    if path.exists():
        operator_inputs_text = path.read_text(encoding="utf-8")

is_full_auto = "Emit exactly one final <answers> block" in request
step = step_name(request)
state[step] = state.get(step, 0) + (0 if is_full_auto else 1)
state_path.write_text(json.dumps(state), encoding="utf-8")

if scenario == "simple_complete":
    final = "<promise>COMPLETE</promise>\\n"
elif scenario in {"question_then_complete", "full_auto_success"}:
    if is_full_auto:
        final = "<answers>\\n<answer>Auto answer</answer>\\n</answers>\\n"
    elif operator_inputs_text:
        final = "<promise>COMPLETE</promise>\\n"
    else:
        final = "<questions>\\n<question>Need operator input?</question>\\n</questions>\\n"
elif scenario == "full_auto_failure":
    if is_full_auto:
        final = "<answers>broken</answers>\\n"
    else:
        final = "<questions>\\n<question>Need operator input?</question>\\n</questions>\\n"
elif scenario == "incomplete_then_complete":
    final = "<promise>INCOMPLETE</promise>\\n" if state[step] == 1 else "<promise>COMPLETE</promise>\\n"
elif scenario == "malformed_then_complete":
    final = "<questions>\\n<question>Broken\\n</questions>\\n" if state[step] == 1 else "<promise>COMPLETE</promise>\\n"
else:
    final = "<promise>COMPLETE</promise>\\n"

final_path.write_text(final, encoding="utf-8")
sys.stdout.write("fake-codex-stdout\\n")
"""


def make_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def create_workspace(tmp_path: Path, *, scenario: str = "simple_complete") -> Path:
    workspace = tmp_path / "workspace"
    workflow_root = workspace / ".reflow" / "workflows" / "demo"
    prompt_root = workflow_root / "prompts"
    prompt_root.mkdir(parents=True)
    (prompt_root / "verify.md").write_text("# Verify\n", encoding="utf-8")
    (workflow_root / "prompts" / "full_auto.md").write_text("# Auto\n", encoding="utf-8")
    (workspace / "target.txt").write_text("seed\n", encoding="utf-8")

    config = {
        "version": 1,
        "default_provider": "codex",
        "providers": {
            "codex": {
                "kind": "codex",
                "command": "codex",
                "model": "fake-model",
                "timeout_sec": 5,
                "args": [],
                "env": {
                    "FAKE_SCENARIO": scenario,
                    "FAKE_STATE": str(workspace / "fake_state.json"),
                },
            }
        },
    }
    workflow = {
        "version": 1,
        "name": "demo",
        "task": "optional",
        "entry": "verify",
        "operator_input": {
            "full_auto_instructions": "prompts/full_auto.md",
            "max_auto_rounds": 2,
        },
        "steps": {
            "verify": {
                "kind": "agent",
                "instructions": "prompts/verify.md",
                "max_loops": 3,
                "count_toward_cycles": True,
                "context": [{"path": "target.txt", "as": "current draft"}],
                "produces": [{"path": "target.txt", "as": "updated draft"}],
                "transitions": {
                    "tag": "promise",
                    "default": "INCOMPLETE",
                    "map": {
                        "COMPLETE": "@done",
                        "INCOMPLETE": "@retry",
                        "BLOCKED": "@blocked",
                    },
                },
            }
        },
    }
    (workspace / ".reflow").mkdir(parents=True, exist_ok=True)
    (workspace / ".reflow" / "config.yaml").write_text(_yaml_dump(config), encoding="utf-8")
    (workspace / ".reflow" / "context.md").write_text("workspace context\n", encoding="utf-8")
    (workflow_root / "workflow.yaml").write_text(_yaml_dump(workflow), encoding="utf-8")

    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    make_executable(bin_dir / "codex", FAKE_CODEX)
    return workspace


def _yaml_dump(value: object) -> str:
    return json.dumps(value, indent=2)


def test_load_config_rejects_reserved_flags(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    config_path = workspace / ".reflow" / "config.yaml"
    config = _load_yaml(config_path)
    config["providers"]["codex"]["args"] = ["--cd"]
    config_path.write_text(_yaml_dump(config), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(workspace)


def test_load_workflow_rejects_unknown_step_fields(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow_path = workspace / ".reflow" / "workflows" / "demo" / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow["steps"]["verify"]["unexpected"] = True
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_workflow(workspace, "demo", load_config(workspace))


def test_parse_agent_outcome_questions_take_precedence():
    from reflow_runtime.models import AgentTransitions

    transitions = AgentTransitions(
        default_target=None,
        tag="promise",
        default_decision="INCOMPLETE",
        mapping={"COMPLETE": "@done", "INCOMPLETE": "@retry"},
    )
    with pytest.raises(Exception):
        parse_agent_outcome(
            "<promise>COMPLETE</promise>\n<questions>\n<question>A?</question>\n</questions>\n",
            transitions,
        )


def test_parse_full_auto_answers_requires_exact_answer_count():
    with pytest.raises(Exception):
        parse_full_auto_answers("<answers>\n<answer>only</answer>\n</answers>\n", 2)


def test_provider_argv_matches_codex_contract(tmp_path: Path):
    from reflow_runtime.models import ProviderProfile

    profile = ProviderProfile(
        name="codex",
        kind="codex",
        command="codex",
        model="gpt-test",
        timeout_sec=30,
        args=["--foo"],
        env={},
    )
    argv = build_provider_argv(profile, "hello", tmp_path, tmp_path / "final.txt")
    assert argv == [
        "codex",
        "exec",
        "--cd",
        str(tmp_path),
        "--model",
        "gpt-test",
        "--foo",
        "--output-last-message",
        str(tmp_path / "final.txt"),
        "hello",
    ]


def test_evaluate_policy_detects_forbidden_and_required_files(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "allowed.txt").write_text("before", encoding="utf-8")
    before = snapshot_workspace(workspace)
    (workspace / "forbidden.txt").write_text("after", encoding="utf-8")
    after = snapshot_workspace(workspace)
    from reflow_runtime.models import PolicySpec

    result = evaluate_policy(
        before,
        after,
        PolicySpec(allow_write=["allowed.txt"], forbid_write=["forbidden.txt"], required_files=["missing.txt"]),
        workspace,
    )
    assert "forbidden.txt: matches forbid_write" in result.violations
    assert result.required_files_missing == ["missing.txt"]


def test_evaluate_policy_ignores_unchanged_escape_symlink(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    escape_target = tmp_path / "outside.txt"
    escape_target.write_text("seed", encoding="utf-8")
    (workspace / "escape").symlink_to(escape_target)

    before = snapshot_workspace(workspace)
    after = snapshot_workspace(workspace)

    result = evaluate_policy(before, after, None, workspace)
    assert result.violations == []


def test_snapshot_workspace_ignores_configured_paths_and_nested_entries(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "kept.txt").write_text("keep", encoding="utf-8")
    ignored_dir = workspace / "ignored"
    ignored_dir.mkdir()
    (ignored_dir / "nested.txt").write_text("skip", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("seed", encoding="utf-8")
    (ignored_dir / "escape").symlink_to(outside)

    snapshot = snapshot_workspace(workspace, ignored_paths={"ignored"})

    assert snapshot.entries == {"kept.txt": ("file", snapshot.entries["kept.txt"][1])}
    assert snapshot.escape_paths == set()


def test_evaluate_policy_flags_changed_escape_symlink(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    escape_target = tmp_path / "outside.txt"
    escape_target.write_text("seed", encoding="utf-8")
    (workspace / "escape").write_text("before", encoding="utf-8")

    before = snapshot_workspace(workspace)
    (workspace / "escape").unlink()
    (workspace / "escape").symlink_to(escape_target)
    after = snapshot_workspace(workspace)

    result = evaluate_policy(before, after, None, workspace)
    assert result.violations == ["escape: resolves outside workspace"]


def test_run_status_and_list_cover_required_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    workspace = create_workspace(tmp_path)
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    exit_code = run_new_workflow(workspace, "demo", full_auto=False)
    assert exit_code == 0

    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    assert status_run(workspace, run_id) == 0
    status_output = capsys.readouterr().out
    assert "run_id:" in status_output
    assert "workflow: demo" in status_output
    assert "status: completed" in status_output
    assert "cycle_count:" in status_output

    assert list_runs(workspace) == 0
    list_output = capsys.readouterr().out
    assert run_id in list_output
    assert "\tdemo\tcompleted\t" in list_output


def test_shell_step_persists_runtime_env_and_command_artifacts(tmp_path: Path):
    workspace = tmp_path / "workspace"
    script_dir = workspace / "scripts"
    workflow_root = workspace / ".reflow" / "workflows" / "shellflow"
    script_dir.mkdir(parents=True)
    workflow_root.mkdir(parents=True)
    (workspace / ".reflow").mkdir(exist_ok=True)
    (workspace / ".reflow" / "config.yaml").write_text(
        _yaml_dump(
            {
                "version": 1,
                "providers": {"codex": {"kind": "codex", "command": "codex"}},
                "default_provider": "codex",
            }
        ),
        encoding="utf-8",
    )
    (script_dir / "capture_env.py").write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {key: os.environ[key] for key in [\n"
        "    'REFLOW_RUN_ID','REFLOW_WORKFLOW','REFLOW_STEP','REFLOW_LOOP','REFLOW_WORKSPACE','REFLOW_ITERATION_DIR']}\n"
        "Path('shell_env.json').write_text(json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    workflow = {
        "version": 1,
        "name": "shellflow",
        "entry": "check",
        "steps": {
            "check": {
                "kind": "shell",
                "cmd": "python3 -c 'from pathlib import Path; import os; Path(\"shell_cmdline.txt\").write_bytes(open(f\"/proc/{os.getppid()}/cmdline\", \"rb\").read())' && python3 scripts/capture_env.py",
                "max_loops": 1,
                "on_success": "@done",
                "on_failure": "@blocked",
                "policy": {"required_files": ["shell_env.json", "shell_cmdline.txt"]},
            }
        },
    }
    (workflow_root / "workflow.yaml").write_text(_yaml_dump(workflow), encoding="utf-8")

    def fake_invoke_shell(
        cmd: str,
        current_workspace: Path,
        env: dict[str, str],
        *,
        child_pid_callback=None,
    ) -> InvocationResult:
        env_payload = {
            key: env[key]
            for key in [
                "REFLOW_RUN_ID",
                "REFLOW_WORKFLOW",
                "REFLOW_STEP",
                "REFLOW_LOOP",
                "REFLOW_WORKSPACE",
                "REFLOW_ITERATION_DIR",
            ]
        }
        (current_workspace / "shell_env.json").write_text(json.dumps(env_payload), encoding="utf-8")
        (current_workspace / "shell_cmdline.txt").write_text("/bin/sh\n-lc\n" + cmd, encoding="utf-8")
        return InvocationResult(
            command_argv=["/bin/sh", "-lc", cmd],
            stdout="ok\n",
            stderr="",
            exit_code=0,
        )

    original_invoke_shell = controller_module.invoke_shell
    controller_module.invoke_shell = fake_invoke_shell
    try:
        assert run_new_workflow(workspace, "shellflow", full_auto=False) == 0
    finally:
        controller_module.invoke_shell = original_invoke_shell

    env_payload = json.loads((workspace / "shell_env.json").read_text(encoding="utf-8"))
    assert env_payload["REFLOW_WORKFLOW"] == "shellflow"
    assert env_payload["REFLOW_STEP"] == "check"

    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    iteration_dir = store.run_dir(run_id) / "steps" / "check" / "001"
    shell_cmdline = (workspace / "shell_cmdline.txt").read_bytes().replace(b"\x00", b"\n").decode("utf-8")
    assert shell_cmdline.splitlines()[1] == "-lc"
    assert (iteration_dir / "command.txt").read_text(encoding="utf-8") == "python3 -c 'from pathlib import Path; import os; Path(\"shell_cmdline.txt\").write_bytes(open(f\"/proc/{os.getppid()}/cmdline\", \"rb\").read())' && python3 scripts/capture_env.py"
    meta = json.loads((iteration_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["command_argv"] == [
        "/bin/sh",
        "-lc",
        "python3 -c 'from pathlib import Path; import os; Path(\"shell_cmdline.txt\").write_bytes(open(f\"/proc/{os.getppid()}/cmdline\", \"rb\").read())' && python3 scripts/capture_env.py",
    ]
    assert meta["command_text"] == "python3 -c 'from pathlib import Path; import os; Path(\"shell_cmdline.txt\").write_bytes(open(f\"/proc/{os.getppid()}/cmdline\", \"rb\").read())' && python3 scripts/capture_env.py"


def test_invoke_shell_executes_the_same_argv_it_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    observed: dict[str, object] = {}

    class FakeProcess:
        def __init__(self, argv, **kwargs):
            observed["argv"] = argv
            observed["cwd"] = kwargs["cwd"]
            self.pid = 4321
            self.returncode = 0

        def communicate(self, timeout=None):
            observed["timeout"] = timeout
            return ("stdout\n", "")

        def poll(self):
            return self.returncode

    def fake_popen(argv, **kwargs):
        observed["argv"] = argv
        return FakeProcess(argv, **kwargs)

    seen_pids: list[int | None] = []
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    result = invoke_shell("echo hi", tmp_path, {"REFLOW_STEP": "check"})

    assert result.command_argv == ["/bin/sh", "-lc", "echo hi"]
    assert observed["argv"] == result.command_argv
    assert observed["cwd"] == tmp_path
    assert observed["timeout"] is None

    result = invoke_shell("echo hi", tmp_path, {"REFLOW_STEP": "check"}, child_pid_callback=seen_pids.append)
    assert seen_pids == [4321, None]


def test_reply_resolves_awaiting_input_and_restarts_same_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="question_then_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    exit_code = run_new_workflow(workspace, "demo", full_auto=False)
    assert exit_code == EXIT_CODE_AWAITING_INPUT
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name

    monkeypatch.setattr("builtins.input", lambda _prompt="": "Human answer")
    monkeypatch.setattr("reflow_runtime.controller._can_prompt_inline", lambda: True)
    assert reply_to_run(workspace, run_id, full_auto=False) == 0

    run = store.load_run(run_id)
    assert run.status == "completed"
    operator_inputs = store.operator_inputs_path(run_id).read_text(encoding="utf-8")
    assert "| human" in operator_inputs
    assert "A1: Human answer" in operator_inputs


def test_reply_keyboard_interrupt_stops_run_and_clears_pending_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="question_then_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False) == EXIT_CODE_AWAITING_INPUT
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name

    def raise_interrupt(_prompt=""):
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_interrupt)
    monkeypatch.setattr("reflow_runtime.controller._can_prompt_inline", lambda: True)

    assert reply_to_run(workspace, run_id, full_auto=False) == 27
    persisted = store.load_run(run_id)
    assert persisted.status == "stopped"
    assert persisted.pending_input is None
    assert not store.active_path.exists()


def test_reply_full_auto_keyboard_interrupt_stops_run_and_clears_pending_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="question_then_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False) == EXIT_CODE_AWAITING_INPUT
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name

    def raise_interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(controller_module, "invoke_provider", raise_interrupt)

    assert reply_to_run(workspace, run_id, full_auto=True) == 27
    persisted = store.load_run(run_id)
    assert persisted.status == "stopped"
    assert persisted.pending_input is None
    assert not store.active_path.exists()


def test_full_auto_answer_success_does_not_create_extra_iteration_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="full_auto_success")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=True) == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    step_dir = store.run_dir(run_id) / "steps" / "verify"
    assert sorted(path.name for path in step_dir.iterdir()) == ["001", "002"]
    run = store.load_run(run_id)
    assert run.step_loops["verify"] == 2
    operator_inputs = store.operator_inputs_path(run_id).read_text(encoding="utf-8")
    assert "| auto" in operator_inputs


def test_full_auto_failure_leaves_run_awaiting_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="full_auto_failure")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=True) == EXIT_CODE_AWAITING_INPUT
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    assert run.status == "awaiting_input"
    history = store.history_path(run_id).read_text(encoding="utf-8")
    assert '"type": "input_auto_failed"' in history


def test_pending_input_is_persisted_under_awaiting_input_before_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="question_then_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")
    observed: list[tuple[str, bool]] = []
    original = controller_module._resolve_pending_input

    def capture(*args, **kwargs):
        run = args[3]
        observed.append((run.status, run.pending_input is not None))
        return None

    monkeypatch.setattr(controller_module, "_resolve_pending_input", capture)
    assert run_new_workflow(workspace, "demo", full_auto=False) == EXIT_CODE_AWAITING_INPUT
    assert observed == [("awaiting_input", True)]
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    assert run.status == "awaiting_input"
    assert run.pending_input is not None

    monkeypatch.setattr(controller_module, "_resolve_pending_input", original)


def test_full_auto_auto_round_updates_only_while_awaiting_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="full_auto_failure")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")
    config = load_config(workspace)
    workflow = load_workflow(workspace, "demo", config)
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify")
    run.status = "awaiting_input"
    run.pending_input = controller_module._new_pending_input("verify", 1, ["Need operator input?"])
    store.save_run(run)

    saved_states: list[tuple[str, int | None]] = []
    original_save_run = store.save_run

    def recording_save_run(current_run):
        auto_round = current_run.pending_input.auto_round if current_run.pending_input else None
        saved_states.append((current_run.status, auto_round))
        original_save_run(current_run)

    monkeypatch.setattr(store, "save_run", recording_save_run)
    controller_module._run_full_auto_answers(store, config, workflow, run, workflow.steps["verify"])

    assert ("awaiting_input", 1) in saved_states
    assert all(status == "awaiting_input" for status, auto_round in saved_states if auto_round)
    persisted = store.load_run(run.run_id)
    assert persisted.status == "awaiting_input"
    assert persisted.pending_input is not None
    assert persisted.pending_input.auto_round == 1


def test_malformed_control_retries_with_warning_until_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="malformed_then_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False) == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    assert run.status == "completed"
    assert run.step_loops["verify"] == 2

    first_meta = json.loads((store.run_dir(run_id) / "steps" / "verify" / "001" / "meta.json").read_text(encoding="utf-8"))
    first_request = (store.run_dir(run_id) / "steps" / "verify" / "001" / "request.txt").read_text(encoding="utf-8")
    second_request = (store.run_dir(run_id) / "steps" / "verify" / "002" / "request.txt").read_text(encoding="utf-8")
    assert first_meta["status"] == "failed"
    assert "- loop: 1" in first_request
    assert "- loop: 2" in second_request
    assert "Previous iteration emitted malformed control output." in second_request


def test_keyboard_interrupt_stops_run_and_reconciles_reserved_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path)
    config = load_config(workspace)
    workflow = load_workflow(workspace, "demo", config)
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify")
    store.write_active(run, os.getpid())

    def raise_interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(controller_module, "invoke_provider", raise_interrupt)
    assert controller_module._drive_run(store, config, workflow, run, full_auto=False) == 27

    persisted = store.load_run(run.run_id)
    assert persisted.status == "stopped"
    meta = json.loads((store.run_dir(run.run_id) / "steps" / "verify" / "001" / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "interrupted"


def test_sigterm_uses_the_same_stop_terminalization_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = create_workspace(tmp_path)

    def raise_sigterm(*_args, **_kwargs):
        os.kill(os.getpid(), controller_module.signal.SIGTERM)
        raise AssertionError("unreachable")

    monkeypatch.setattr(controller_module, "invoke_provider", raise_sigterm)
    assert run_new_workflow(workspace, "demo", full_auto=False) == 27

    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    persisted = store.load_run(run_id)
    meta = json.loads((store.run_dir(run_id) / "steps" / "verify" / "001" / "meta.json").read_text(encoding="utf-8"))
    assert persisted.status == "stopped"
    assert meta["status"] == "interrupted"
    assert not store.active_path.exists()


def test_cli_maps_keyboard_interrupt_to_stopped_exit_code(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch):
    def raise_interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(reflow, "run_new_workflow", raise_interrupt)
    exit_code = reflow.main(["run", "demo"])
    assert exit_code == 27
    assert "Interrupted." in capsys.readouterr().err


def test_resume_reconciles_reserved_iteration_before_restarting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="simple_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")
    config = load_config(workspace)
    workflow = load_workflow(workspace, "demo", config)
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify")
    ctx = store.reserve_iteration(run, "verify", "agent", request_text="partial", command_argv=["codex"])
    store.write_active(run, 999999)

    assert resume_run(workspace, run.run_id, full_auto=False) == 0
    meta = json.loads(ctx.meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "interrupted"
    assert meta["ended_at"] is not None


def test_stop_marks_running_run_stopped_and_reconciles_reserved_iteration(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    config = load_config(workspace)
    workflow = load_workflow(workspace, "demo", config)
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify")
    ctx = store.reserve_iteration(run, "verify", "agent", request_text="partial", command_argv=["codex"])
    atomic_write_json(
        store.active_path,
        {
            "run_id": run.run_id,
            "workflow": run.workflow,
            "status": "running",
            "started_at": run.started_at,
            "updated_at": run.updated_at,
            "controller_pid": 999999,
        },
    )

    assert stop_run(workspace, run.run_id) == 0
    run = store.load_run(run.run_id)
    assert run.status == "stopped"
    meta = json.loads(ctx.meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "interrupted"


def test_stop_signals_recorded_child_pid_before_terminalizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path)
    config = load_config(workspace)
    workflow = load_workflow(workspace, "demo", config)
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify")
    atomic_write_json(
        store.active_path,
        {
            "run_id": run.run_id,
            "workflow": run.workflow,
            "status": "running",
            "started_at": run.started_at,
            "updated_at": run.updated_at,
            "controller_pid": 1111,
            "child_pid": 2222,
        },
    )
    recorded: list[tuple[int, int]] = []

    monkeypatch.setattr(controller_module, "is_pid_alive", lambda pid: True)
    monkeypatch.setattr(controller_module.os, "kill", lambda pid, sig: recorded.append((pid, sig)))

    assert stop_run(workspace, run.run_id) == 0
    assert recorded == [(2222, controller_module.signal.SIGTERM), (1111, controller_module.signal.SIGTERM)]


def test_shell_policy_detects_child_tampering_under_reflow(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workflow_root = workspace / ".reflow" / "workflows" / "tamper"
    workflow_root.mkdir(parents=True)
    (workspace / ".reflow" / "config.yaml").write_text(
        _yaml_dump(
            {
                "version": 1,
                "providers": {"codex": {"kind": "codex", "command": "codex"}},
                "default_provider": "codex",
            }
        ),
        encoding="utf-8",
    )
    workflow = {
        "version": 1,
        "name": "tamper",
        "entry": "mutate",
        "steps": {
            "mutate": {
                "kind": "shell",
                "cmd": "python3 -c 'from pathlib import Path; Path(\".reflow/config.yaml\").write_text(\"tampered\\n\", encoding=\"utf-8\")'",
                "max_loops": 1,
                "on_success": "@done",
                "on_failure": "@done",
                "policy": {"allow_write": ["target.txt"]},
            }
        },
    }
    (workspace / "target.txt").write_text("seed\n", encoding="utf-8")
    (workflow_root / "workflow.yaml").write_text(_yaml_dump(workflow), encoding="utf-8")

    assert run_new_workflow(workspace, "tamper", full_auto=False) == 21
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    assert run.status == "failed"
    assert run.failure_reason == ".reflow/config.yaml: not allowed by allow_write"


def test_shell_policy_ignores_reserved_iteration_transport_artifacts(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workflow_root = workspace / ".reflow" / "workflows" / "shellsafe"
    workflow_root.mkdir(parents=True)
    (workspace / ".reflow" / "config.yaml").write_text(
        _yaml_dump(
            {
                "version": 1,
                "providers": {"codex": {"kind": "codex", "command": "codex"}},
                "default_provider": "codex",
            }
        ),
        encoding="utf-8",
    )
    workflow = {
        "version": 1,
        "name": "shellsafe",
        "entry": "mutate",
        "steps": {
            "mutate": {
                "kind": "shell",
                "cmd": "python3 -c 'from pathlib import Path; Path(\"target.txt\").write_text(\"updated\\n\", encoding=\"utf-8\")'",
                "max_loops": 1,
                "on_success": "@done",
                "on_failure": "@done",
                "policy": {"allow_write": ["target.txt"]},
            }
        },
    }
    (workspace / "target.txt").write_text("seed\n", encoding="utf-8")
    (workflow_root / "workflow.yaml").write_text(_yaml_dump(workflow), encoding="utf-8")

    assert run_new_workflow(workspace, "shellsafe", full_auto=False) == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    iteration_dir = store.run_dir(run_id) / "steps" / "mutate" / "001"
    assert run.status == "completed"
    assert (workspace / "target.txt").read_text(encoding="utf-8") == "updated\n"
    assert json.loads((iteration_dir / "meta.json").read_text(encoding="utf-8"))["status"] == "ok"


def test_agent_policy_ignores_reserved_iteration_transport_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path, scenario="simple_complete")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    workflow_path = workspace / ".reflow" / "workflows" / "demo" / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow["steps"]["verify"]["policy"] = {"allow_write": ["fake_state.json"]}
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")

    assert run_new_workflow(workspace, "demo", full_auto=False) == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    assert run.status == "completed"


def test_cli_returns_internal_error_for_invalid_command_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    workspace = create_workspace(tmp_path)
    exit_code = reflow.main(["status", "missing-run", "--workspace", str(workspace)])
    assert exit_code == 25
    assert "does not exist" in capsys.readouterr().err


def test_load_workflow_normalizes_instruction_lists_and_defaults(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow_root = workspace / ".reflow" / "workflows" / "demo"
    shared_dir = workflow_root / "shared_skill"
    shared_dir.mkdir()
    (shared_dir / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

    workflow_path = workflow_root / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow.pop("entry")
    workflow["task"] = "required"
    workflow["steps"]["verify"]["instructions"] = ["shared_skill", "prompts/verify.md"]
    workflow["steps"]["verify"]["transitions"] = {
        "default": "done",
        "map": {"done": "@done", "retry": "@retry"},
    }
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")

    loaded = load_workflow(workspace, "demo", load_config(workspace))
    step = loaded.steps["verify"]
    assert loaded.entry == "verify"
    assert loaded.task_mode == "required"
    assert step.instructions == ["shared_skill", "prompts/verify.md"]
    assert step.transitions.tag == "route"


def test_load_workflow_rejects_empty_instruction_list(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow_path = workspace / ".reflow" / "workflows" / "demo" / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow["steps"]["verify"]["instructions"] = []
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_workflow(workspace, "demo", load_config(workspace))


def test_load_instruction_body_concatenates_multiple_sources(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow_root = workspace / ".reflow" / "workflows" / "demo"
    (workflow_root / "prompts" / "extra.md").write_text("Extra\n", encoding="utf-8")

    workflow = load_workflow(workspace, "demo", load_config(workspace))
    body = load_instruction_body(workflow, ["prompts/verify.md", "prompts/extra.md"])
    assert body == "# Verify\n\nExtra"


def test_render_agent_request_includes_task_context_and_expected_output(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow = load_workflow(workspace, "demo", load_config(workspace))
    step = workflow.steps["verify"]
    store = RunStore(workspace)
    run = store.create_run("demo", list(workflow.steps), "verify", task="Refine the draft")

    request = render_agent_request(
        workflow,
        run,
        step,
        1,
        None,
        workspace,
        {"target.txt": True},
    )
    assert "- task: Refine the draft" in request
    assert "- context: target.txt as current draft" in request
    assert "- expected output: target.txt as updated draft" in request


def test_run_persists_task_and_context_presence_in_iteration_meta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = create_workspace(tmp_path)
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False, task="Tighten the document") == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    run = store.load_run(run_id)
    meta = json.loads((store.run_dir(run_id) / "steps" / "verify" / "001" / "meta.json").read_text(encoding="utf-8"))
    request = (store.run_dir(run_id) / "steps" / "verify" / "001" / "request.txt").read_text(encoding="utf-8")

    assert run.task == "Tighten the document"
    assert meta["context_present"] == {"target.txt": True}
    assert "- task: Tighten the document" in request


def test_status_verbose_includes_context_and_expected_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    workspace = create_workspace(tmp_path)
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False, task="Review task") == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name

    assert status_run(workspace, run_id, verbose=True) == 0
    output = capsys.readouterr().out
    assert "task: Review task" in output
    assert "context: target.txt | current draft | present" in output
    assert "expected_output: target.txt | updated draft" in output


def test_task_required_without_input_fails_with_usage_message(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    workflow_path = workspace / ".reflow" / "workflows" / "demo" / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow["task"] = "required"
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")

    with pytest.raises(ValueError, match='requires a task'):
        run_new_workflow(workspace, "demo", full_auto=False)


def test_task_none_ignores_supplied_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = create_workspace(tmp_path)
    workflow_path = workspace / ".reflow" / "workflows" / "demo" / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    workflow["task"] = "none"
    workflow_path.write_text(_yaml_dump(workflow), encoding="utf-8")
    monkeypatch.setenv("PATH", f"{workspace / 'bin'}:{os.environ['PATH']}")

    assert run_new_workflow(workspace, "demo", full_auto=False, task="ignored task") == 0
    store = RunStore(workspace)
    run_id = next(store.runs_dir.iterdir()).name
    assert store.load_run(run_id).task is None


def test_cli_rejects_positional_task_and_task_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    task_file = tmp_path / "task.txt"
    task_file.write_text("task from file\n", encoding="utf-8")

    exit_code = reflow.main(["run", "demo", "inline task", "--task-file", str(task_file)])
    assert exit_code == 25
    assert "mutually exclusive" in capsys.readouterr().err


def test_validate_command_reports_success_and_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    workspace = create_workspace(tmp_path)

    assert validate_workflow(workspace, "demo") == 0
    assert "Workflow 'demo' is valid." in capsys.readouterr().out

    exit_code = reflow.main(["validate", "missing", "--workspace", str(workspace)])
    assert exit_code == 25
    assert "missing" in capsys.readouterr().err


def test_init_creates_scaffold_and_refuses_existing_workflow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert init_workflow(
        workspace,
        "draft",
        template_name="write-verify",
        provider_kind="codex",
        target="docs/draft.md",
    ) == 0
    output = capsys.readouterr().out
    assert "Workflow 'draft' is valid." in output
    assert "Created:" in output
    assert (workspace / ".reflow" / "workflows" / "draft" / "workflow.yaml").exists()
    assert (workspace / ".reflow" / "context.md").exists()
    assert (workspace / "docs" / "draft.md").exists()

    with pytest.raises(ValueError):
        init_workflow(
            workspace,
            "draft",
            template_name="write-verify",
            provider_kind="codex",
            target="docs/draft.md",
        )


def _load_yaml(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
