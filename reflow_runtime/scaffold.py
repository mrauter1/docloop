from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PROVIDER_DEFAULTS = {
    "codex": {
        "provider_kind": "codex",
        "provider_command": "codex",
        "provider_model": "o4-mini",
        "extra_args": '["--full-auto"]',
    },
    "claude": {
        "provider_kind": "claude",
        "provider_command": "claude",
        "provider_model": "sonnet",
        "extra_args": "[]",
    },
}


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
    if template_name not in {"write-verify", "single-agent"}:
        raise ValueError("template must be one of: write-verify, single-agent")
    if provider_kind not in PROVIDER_DEFAULTS:
        raise ValueError("provider must be one of: codex, claude")

    reflow_dir = workspace / ".reflow"
    workflow_dir = reflow_dir / "workflows" / workflow_name
    template_dir = TEMPLATES_DIR / template_name
    if workflow_dir.exists():
        raise ValueError(f"workflow directory already exists: {workflow_dir.relative_to(workspace).as_posix()}")

    substitutions = {
        "workflow_name": workflow_name,
        "target": target,
        **PROVIDER_DEFAULTS[provider_kind],
    }
    created: list[str] = []
    skipped: list[str] = []

    config_path = reflow_dir / "config.yaml"
    if config_path.exists():
        skipped.append(_rel(workspace, config_path))
    else:
        _write_template(TEMPLATES_DIR / "_config.yaml", config_path, substitutions)
        created.append(_rel(workspace, config_path))

    context_path = reflow_dir / "context.md"
    if context_path.exists():
        skipped.append(_rel(workspace, context_path))
    else:
        _write_template(TEMPLATES_DIR / "_context.md", context_path, substitutions)
        created.append(_rel(workspace, context_path))

    workflow_dir.mkdir(parents=True, exist_ok=False)
    for source in sorted(template_dir.rglob("*")):
        if source.is_dir():
            continue
        destination = workflow_dir / source.relative_to(template_dir)
        _write_template(source, destination, substitutions)
        created.append(_rel(workspace, destination))

    target_path = workspace / target
    if target_path.exists():
        skipped.append(_rel(workspace, target_path))
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(f"# {target_path.stem}\n\nDraft.\n", encoding="utf-8")
        created.append(_rel(workspace, target_path))

    return ScaffoldResult(
        created=created,
        skipped=skipped,
        next_steps=[
            "Edit .reflow/context.md with your requirements",
            f"Edit {target} with initial content (or leave empty)",
            f'Run: reflow run {workflow_name} "describe what you want done"',
        ],
    )


def _write_template(source: Path, destination: Path, substitutions: dict[str, str]) -> None:
    text = source.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        text = text.replace("{" + key + "}", value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()
