from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class ScaffoldResult:
    created: list[str]
    skipped: list[str]
    next_steps: list[str]


def write_scaffold(
    workspace: Path,
    workflow_name: str,
    *,
    template_name: str,
    provider_kind: str,
    target: str,
) -> ScaffoldResult:
    reflow_dir = workspace / ".reflow"
    workflow_dir = reflow_dir / "workflows" / workflow_name
    if workflow_dir.exists():
        raise ValueError(f"workflow directory already exists: {workflow_dir.relative_to(workspace).as_posix()}")

    created: list[str] = []
    skipped: list[str] = []

    config_path = reflow_dir / "config.yaml"
    context_path = reflow_dir / "context.md"
    target_path = workspace / target

    if config_path.exists():
        skipped.append(_rel(workspace, config_path))
    else:
        _write_json(config_path, _config_payload(provider_kind))
        created.append(_rel(workspace, config_path))

    if context_path.exists():
        skipped.append(_rel(workspace, context_path))
    else:
        _write_text(context_path, _load_template("context.md.tmpl"))
        created.append(_rel(workspace, context_path))

    workflow_dir.mkdir(parents=True, exist_ok=False)
    for relative_path, content in _workflow_files(workflow_name, template_name, target).items():
        path = workflow_dir / relative_path
        _write_text(path, content)
        created.append(_rel(workspace, path))

    if target_path.exists():
        skipped.append(_rel(workspace, target_path))
    else:
        _write_text(target_path, _load_template("target.md.tmpl").format(workflow_name=workflow_name))
        created.append(_rel(workspace, target_path))

    return ScaffoldResult(
        created=created,
        skipped=skipped,
        next_steps=[
            f"Review .reflow/workflows/{workflow_name}/workflow.yaml and prompts.",
            f"Run: reflow validate {workflow_name} --workspace {workspace}",
            f"Start a run: reflow run {workflow_name} \"your task\" --workspace {workspace}",
        ],
    )


def _workflow_files(workflow_name: str, template_name: str, target: str) -> dict[str, str]:
    if template_name not in {"write-verify", "single-agent"}:
        raise ValueError("template must be one of: write-verify, single-agent")

    shared_base = _load_template("shared/base_rules.md.tmpl")
    review_prompt = _load_template("prompts/review.md.tmpl").format(target=target)

    if template_name == "write-verify":
        workflow_payload = {
            "version": 1,
            "name": workflow_name,
            "task": "required",
            "default_provider": "default",
            "operator_input": {"full_auto_instructions": "prompts/full_auto.md", "max_auto_rounds": 2},
            "steps": {
                "write": {
                    "kind": "agent",
                    "instructions": ["shared/base_rules.md", "prompts/write.md"],
                    "max_loops": 4,
                    "count_toward_cycles": True,
                    "context": [{"path": target, "as": "current draft to improve"}],
                    "produces": [{"path": target, "as": "updated draft"}],
                    "transitions": {"default": "done", "map": {"revise": "review", "done": "review", "blocked": "review"}},
                },
                "review": {
                    "kind": "agent",
                    "instructions": ["shared/base_rules.md", "prompts/review.md"],
                    "max_loops": 4,
                    "transitions": {
                        "default": "revise",
                        "map": {"revise": "write", "done": "@done", "blocked": "@blocked"},
                    },
                    "context": [{"path": target, "as": "draft under review"}],
                    "produces": [{"path": "review_notes.md", "as": "review feedback or completion rationale"}],
                },
            },
        }
        write_prompt = _load_template("prompts/write.md.tmpl").format(target=target)
        return {
            "workflow.yaml": json.dumps(workflow_payload, indent=2) + "\n",
            "shared/base_rules.md": shared_base,
            "prompts/write.md": write_prompt,
            "prompts/review.md": review_prompt,
            "prompts/full_auto.md": _load_template("prompts/full_auto.md.tmpl"),
        }

    workflow_payload = {
        "version": 1,
        "name": workflow_name,
        "task": "required",
        "default_provider": "default",
        "steps": {
            "execute": {
                "kind": "agent",
                "instructions": ["shared/base_rules.md", "prompts/execute.md"],
                "max_loops": 4,
                "count_toward_cycles": True,
                "context": [{"path": target, "as": "primary file to update"}],
                "produces": [{"path": target, "as": "completed output"}],
                "transitions": {
                    "default": "retry",
                    "map": {"retry": "@retry", "done": "@done", "blocked": "@blocked"},
                },
            }
        },
    }
    return {
        "workflow.yaml": json.dumps(workflow_payload, indent=2) + "\n",
        "shared/base_rules.md": shared_base,
        "prompts/execute.md": _load_template("prompts/execute.md.tmpl").format(target=target),
    }


def _config_payload(provider_kind: str) -> dict[str, object]:
    if provider_kind not in {"codex", "claude"}:
        raise ValueError("provider must be one of: codex, claude")
    command = "codex" if provider_kind == "codex" else "claude"
    return {
        "version": 1,
        "default_provider": "default",
        "providers": {
            "default": {
                "kind": provider_kind,
                "command": command,
                "model": None,
                "timeout_sec": 1800,
                "args": [],
                "env": {},
            }
        },
    }


def _load_template(relative_path: str) -> str:
    return (TEMPLATES_DIR / relative_path).read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()
