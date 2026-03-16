from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from .models import (
    AgentStep,
    AgentTransitions,
    ConfigError,
    ContextEntry,
    DEFAULT_MAX_AUTO_ROUNDS,
    DEFAULT_PROVIDER_TIMEOUT_SEC,
    PolicySpec,
    ProducesEntry,
    ProviderProfile,
    ReflowConfig,
    RESERVED_TRANSITIONS,
    ShellStep,
    Step,
    Workflow,
    WorkflowOperatorInput,
)

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised via dedicated test
    yaml = None


CONFIG_TOP_LEVEL_FIELDS = {"version", "default_provider", "providers"}
PROVIDER_FIELDS = {"kind", "command", "model", "timeout_sec", "args", "env"}
WORKFLOW_TOP_LEVEL_FIELDS = {
    "version",
    "name",
    "task",
    "entry",
    "steps",
    "default_provider",
    "budgets",
    "operator_input",
}
AGENT_STEP_FIELDS = {
    "kind",
    "instructions",
    "provider",
    "max_loops",
    "count_toward_cycles",
    "transitions",
    "policy",
    "context",
    "produces",
}
SHELL_STEP_FIELDS = {
    "kind",
    "cmd",
    "max_loops",
    "on_success",
    "on_failure",
    "count_toward_cycles",
    "policy",
}

RESERVED_PROVIDER_ARGS = {
    "codex": {"exec", "--cd", "--output-last-message"},
    "claude": {"-p", "--print", "--output-format"},
}


def require_yaml() -> None:
    return None


def load_config(workspace: Path) -> ReflowConfig:
    require_yaml()
    config_path = workspace / ".reflow" / "config.yaml"
    payload = _load_yaml_mapping(config_path, ".reflow/config.yaml")

    _validate_allowed_fields(payload, CONFIG_TOP_LEVEL_FIELDS, ".reflow/config.yaml")
    _require_exact_int(payload.get("version"), 1, ".reflow/config.yaml version must be 1.")

    providers_payload = payload.get("providers")
    if not isinstance(providers_payload, dict) or not providers_payload:
        raise ConfigError(".reflow/config.yaml providers must be a non-empty mapping.")

    providers: dict[str, ProviderProfile] = {}
    for name, provider_payload in providers_payload.items():
        if not isinstance(name, str) or not name.strip():
            raise ConfigError("Provider names must be non-empty strings.")
        if not isinstance(provider_payload, dict):
            raise ConfigError(f"Provider {name!r} must be a mapping.")
        _validate_allowed_fields(provider_payload, PROVIDER_FIELDS, f"provider {name!r}")
        kind = _require_choice(provider_payload.get("kind"), {"codex", "claude"}, f"provider {name!r} kind")
        command = _require_non_empty_string(provider_payload.get("command"), f"provider {name!r} command")
        model = provider_payload.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ConfigError(f"provider {name!r} model must be a non-empty string when provided.")
        timeout_sec = provider_payload.get("timeout_sec", DEFAULT_PROVIDER_TIMEOUT_SEC)
        if not isinstance(timeout_sec, int) or timeout_sec < 1:
            raise ConfigError(f"provider {name!r} timeout_sec must be a positive integer.")
        args = provider_payload.get("args", [])
        if not isinstance(args, list) or any(not isinstance(item, str) or not item for item in args):
            raise ConfigError(f"provider {name!r} args must be a list of non-empty strings.")
        reserved = RESERVED_PROVIDER_ARGS[kind].intersection(args)
        if reserved:
            reserved_display = ", ".join(sorted(reserved))
            raise ConfigError(f"provider {name!r} args contain reserved flags: {reserved_display}.")
        env = provider_payload.get("env", {})
        if not isinstance(env, dict) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            for key, value in env.items()
        ):
            raise ConfigError(f"provider {name!r} env must be a string-to-string mapping.")

        providers[name] = ProviderProfile(
            name=name,
            kind=kind,
            command=command,
            model=model.strip() if isinstance(model, str) else None,
            timeout_sec=timeout_sec,
            args=list(args),
            env=dict(env),
        )

    default_provider = payload.get("default_provider")
    if default_provider is not None:
        default_provider = _require_non_empty_string(default_provider, "default_provider")
        if default_provider not in providers:
            raise ConfigError("default_provider must reference a configured provider.")

    return ReflowConfig(workspace=workspace, default_provider=default_provider, providers=providers)


def load_workflow(workspace: Path, workflow_name: str, config: ReflowConfig) -> Workflow:
    require_yaml()
    workflow_root = workspace / ".reflow" / "workflows" / workflow_name
    workflow_path = workflow_root / "workflow.yaml"
    payload = _load_yaml_mapping(workflow_path, f"workflow {workflow_name!r}")

    _validate_allowed_fields(payload, WORKFLOW_TOP_LEVEL_FIELDS, f"workflow {workflow_name!r}")
    _require_exact_int(payload.get("version"), 1, f"workflow {workflow_name!r} version must be 1.")

    name = _require_non_empty_string(payload.get("name"), "workflow name")
    if name != workflow_name:
        raise ConfigError("workflow name must exactly match the workflow directory name.")

    steps_payload = payload.get("steps")
    if not isinstance(steps_payload, dict) or not steps_payload:
        raise ConfigError("workflow steps must be a non-empty mapping.")

    task_mode = payload.get("task", "optional")
    task_mode = _require_choice(task_mode, {"required", "optional", "none"}, "workflow task")

    entry_value = payload.get("entry")
    if entry_value is None:
        entry = next(iter(steps_payload.keys()))
    else:
        entry = _require_non_empty_string(entry_value, "workflow entry")
    if entry.startswith("@"):
        raise ConfigError("workflow entry must not begin with '@'.")

    default_provider = payload.get("default_provider")
    if default_provider is not None:
        default_provider = _require_non_empty_string(default_provider, "workflow default_provider")
        if default_provider not in config.providers:
            raise ConfigError("workflow default_provider must reference a configured provider.")

    budgets = payload.get("budgets", {})
    if not isinstance(budgets, dict):
        raise ConfigError("workflow budgets must be a mapping when provided.")
    _validate_allowed_fields(budgets, {"max_cycles"}, "workflow budgets")
    max_cycles = budgets.get("max_cycles")
    if max_cycles is not None and (not isinstance(max_cycles, int) or max_cycles < 1):
        raise ConfigError("workflow budgets.max_cycles must be a positive integer.")

    operator_input_payload = payload.get("operator_input", {})
    if not isinstance(operator_input_payload, dict):
        raise ConfigError("workflow operator_input must be a mapping when provided.")
    _validate_allowed_fields(
        operator_input_payload,
        {"full_auto_instructions", "max_auto_rounds"},
        "workflow operator_input",
    )
    full_auto_instructions = operator_input_payload.get("full_auto_instructions")
    if full_auto_instructions is not None:
        full_auto_instructions = _validate_workflow_relative_file(
            workflow_root,
            full_auto_instructions,
            "workflow operator_input.full_auto_instructions",
        )
    max_auto_rounds = operator_input_payload.get("max_auto_rounds", DEFAULT_MAX_AUTO_ROUNDS)
    if not isinstance(max_auto_rounds, int) or max_auto_rounds < 1:
        raise ConfigError("workflow operator_input.max_auto_rounds must be a positive integer.")

    steps: dict[str, Step] = {}
    for step_name, step_payload in steps_payload.items():
        steps[step_name] = _parse_step(
            workspace=workspace,
            workflow_root=workflow_root,
            workflow_name=workflow_name,
            step_name=step_name,
            payload=step_payload,
            config=config,
            workflow_default_provider=default_provider,
            declared_steps=set(steps_payload.keys()),
        )

    if entry not in steps:
        raise ConfigError("workflow entry must reference a declared step.")

    return Workflow(
        name=name,
        root=workflow_root,
        entry=entry,
        steps=steps,
        task_mode=task_mode,
        default_provider=default_provider,
        max_cycles=max_cycles,
        operator_input=WorkflowOperatorInput(
            full_auto_instructions=full_auto_instructions,
            max_auto_rounds=max_auto_rounds,
        ),
    )


def load_instruction_body(workflow: Workflow, relative_paths: list[str]) -> str:
    bodies: list[str] = []
    for relative_path in relative_paths:
        target = workflow.root / relative_path
        if target.is_dir():
            target = target / "SKILL.md"
        bodies.append(target.read_text(encoding="utf-8").rstrip())
    return "\n\n".join(bodies)


def resolve_provider_for_step(config: ReflowConfig, workflow: Workflow, step: AgentStep) -> ProviderProfile:
    provider_name = step.provider or workflow.default_provider or config.default_provider
    if not provider_name:
        raise ConfigError(f"agent step {step.name!r} cannot resolve a provider.")
    try:
        return config.providers[provider_name]
    except KeyError as exc:
        raise ConfigError(f"agent step {step.name!r} resolved unknown provider {provider_name!r}.") from exc


def _parse_step(
    *,
    workspace: Path,
    workflow_root: Path,
    workflow_name: str,
    step_name: str,
    payload: object,
    config: ReflowConfig,
    workflow_default_provider: str | None,
    declared_steps: set[str],
) -> Step:
    if not isinstance(step_name, str) or not step_name:
        raise ConfigError("step names must be non-empty strings.")
    if step_name.startswith("@"):
        raise ConfigError(f"step {step_name!r} must not begin with '@'.")
    if not isinstance(payload, dict):
        raise ConfigError(f"step {step_name!r} must be a mapping.")

    kind = _require_choice(payload.get("kind"), {"agent", "shell"}, f"step {step_name!r} kind")
    if kind == "agent":
        _validate_allowed_fields(payload, AGENT_STEP_FIELDS, f"agent step {step_name!r}")
        raw_instructions = payload.get("instructions")
        if isinstance(raw_instructions, list):
            if not raw_instructions:
                raise ConfigError(f"agent step {step_name!r} instructions list must not be empty.")
            instructions = [
                _validate_workflow_relative_instruction(
                    workflow_root,
                    entry,
                    f"agent step {step_name!r} instructions[{index}]",
                )
                for index, entry in enumerate(raw_instructions)
            ]
        elif isinstance(raw_instructions, str):
            instructions = [
                _validate_workflow_relative_instruction(
                    workflow_root,
                    raw_instructions,
                    f"agent step {step_name!r} instructions",
                )
            ]
        else:
            raise ConfigError(f"agent step {step_name!r} instructions must be a string or list of strings.")
        max_loops = _require_positive_int(payload.get("max_loops"), f"agent step {step_name!r} max_loops")
        count_toward_cycles = _require_bool_default(
            payload.get("count_toward_cycles", False),
            f"agent step {step_name!r} count_toward_cycles",
        )
        provider_name = payload.get("provider")
        if provider_name is not None:
            provider_name = _require_non_empty_string(provider_name, f"agent step {step_name!r} provider")
            if provider_name not in config.providers:
                raise ConfigError(f"agent step {step_name!r} references unknown provider {provider_name!r}.")
        elif workflow_default_provider is None and config.default_provider is None:
            raise ConfigError(f"agent step {step_name!r} cannot resolve a provider.")
        transitions = _parse_transitions(payload.get("transitions"), declared_steps, step_name)
        policy = _parse_policy(workspace, payload.get("policy"), f"agent step {step_name!r}")
        context = _parse_declared_entries(
            workflow_root,
            payload.get("context", []),
            f"agent step {step_name!r} context",
            ContextEntry,
        )
        produces = _parse_declared_entries(
            workflow_root,
            payload.get("produces", []),
            f"agent step {step_name!r} produces",
            ProducesEntry,
        )
        return AgentStep(
            name=step_name,
            instructions=instructions,
            max_loops=max_loops,
            transitions=transitions,
            provider=provider_name,
            count_toward_cycles=count_toward_cycles,
            policy=policy,
            context=context,
            produces=produces,
        )

    _validate_allowed_fields(payload, SHELL_STEP_FIELDS, f"shell step {step_name!r}")
    cmd = _require_non_empty_string(payload.get("cmd"), f"shell step {step_name!r} cmd")
    max_loops = _require_positive_int(payload.get("max_loops"), f"shell step {step_name!r} max_loops")
    count_toward_cycles = _require_bool_default(
        payload.get("count_toward_cycles", False),
        f"shell step {step_name!r} count_toward_cycles",
    )
    on_success = _validate_transition_target(
        payload.get("on_success"),
        declared_steps,
        f"shell step {step_name!r} on_success",
    )
    on_failure = _validate_transition_target(
        payload.get("on_failure"),
        declared_steps,
        f"shell step {step_name!r} on_failure",
    )
    policy = _parse_policy(workspace, payload.get("policy"), f"shell step {step_name!r}")
    return ShellStep(
        name=step_name,
        cmd=cmd,
        max_loops=max_loops,
        on_success=on_success,
        on_failure=on_failure,
        count_toward_cycles=count_toward_cycles,
        policy=policy,
    )


def _parse_transitions(payload: object, declared_steps: set[str], label: str) -> AgentTransitions:
    if not isinstance(payload, dict):
        raise ConfigError(f"agent step {label!r} transitions must be a mapping.")
    allowed = {"default"} | {"tag", "map"}
    _validate_allowed_fields(payload, allowed, f"agent step {label!r} transitions")

    if "tag" not in payload and "map" not in payload:
        default_target = _validate_transition_target(payload.get("default"), declared_steps, f"{label} transitions default")
        return AgentTransitions(default_target=default_target, tag=None, default_decision=None, mapping={})

    tag_value = payload.get("tag", "route" if "map" in payload else None)
    tag = _require_non_empty_string(tag_value, f"agent step {label!r} transitions.tag")
    default_decision = _require_non_empty_string(
        payload.get("default"),
        f"agent step {label!r} transitions.default",
    )
    mapping_payload = payload.get("map")
    if not isinstance(mapping_payload, dict) or not mapping_payload:
        raise ConfigError(f"agent step {label!r} tagged transitions require a non-empty map.")
    mapping: dict[str, str] = {}
    for decision, target in mapping_payload.items():
        if not isinstance(decision, str) or not decision:
            raise ConfigError(f"agent step {label!r} transition decisions must be non-empty strings.")
        mapping[decision] = _validate_transition_target(target, declared_steps, f"{label} transitions map")
    if default_decision not in mapping:
        raise ConfigError(f"agent step {label!r} transitions.default must exist in transitions.map.")
    return AgentTransitions(default_target=None, tag=tag, default_decision=default_decision, mapping=mapping)


def _parse_declared_entries(workflow_root: Path, payload: object, label: str, entry_type):
    if not isinstance(payload, list):
        raise ConfigError(f"{label} must be a list when provided.")
    entries = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ConfigError(f"{label}[{index}] must be a mapping.")
        _validate_allowed_fields(item, {"path", "as"}, f"{label}[{index}]")
        path = _validate_workflow_relative_declared_path(workflow_root, item.get("path"), f"{label}[{index}].path")
        as_description = _require_non_empty_string(item.get("as"), f"{label}[{index}].as")
        entries.append(entry_type(path=path, as_description=as_description))
    return entries


def _parse_policy(workspace: Path, payload: object, label: str) -> PolicySpec | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ConfigError(f"{label} policy must be a mapping.")
    _validate_allowed_fields(payload, {"allow_write", "forbid_write", "required_files"}, f"{label} policy")
    parsed: dict[str, list[str]] = {}
    for field in ("allow_write", "forbid_write", "required_files"):
        value = payload.get(field, [])
        if value == []:
            parsed[field] = []
            continue
        if not isinstance(value, list) or not value:
            raise ConfigError(f"{label} policy.{field} must be a non-empty list when present.")
        items: list[str] = []
        seen: set[str] = set()
        for raw_item in value:
            item = _normalize_repo_pattern(raw_item, f"{label} policy.{field}")
            if item in seen:
                raise ConfigError(f"{label} policy.{field} contains duplicates.")
            seen.add(item)
            items.append(item)
        parsed[field] = items
    return PolicySpec(
        allow_write=parsed["allow_write"],
        forbid_write=parsed["forbid_write"],
        required_files=parsed["required_files"],
    )


def _normalize_repo_pattern(value: object, label: str) -> str:
    raw = _require_non_empty_string(value, label)
    if raw.startswith("/"):
        raise ConfigError(f"{label} must be repo-relative.")
    pure = PurePosixPath(raw)
    if ".." in pure.parts:
        raise ConfigError(f"{label} must not escape the workspace.")
    normalized = pure.as_posix()
    if normalized in {"", "."}:
        raise ConfigError(f"{label} must not be empty.")
    return normalized


def _validate_transition_target(value: object, declared_steps: set[str], label: str) -> str:
    target = _require_non_empty_string(value, label)
    if target.startswith("@"):
        if target not in RESERVED_TRANSITIONS:
            raise ConfigError(f"{label} has invalid reserved transition target {target!r}.")
        return target
    if target not in declared_steps:
        raise ConfigError(f"{label} references unknown step {target!r}.")
    return target


def _validate_workflow_relative_instruction(workflow_root: Path, value: object, label: str) -> str:
    relative = _normalize_repo_pattern(value, label)
    target = workflow_root / relative
    _ensure_path_inside_root(workflow_root, target, label)
    if target.is_dir():
        skill_path = target / "SKILL.md"
        if not skill_path.is_file():
            raise ConfigError(f"{label} directory must contain SKILL.md.")
    elif not target.is_file():
        raise ConfigError(f"{label} must reference an existing file or a directory with SKILL.md.")
    return relative


def _validate_workflow_relative_file(workflow_root: Path, value: object, label: str) -> str:
    relative = _normalize_repo_pattern(value, label)
    target = workflow_root / relative
    _ensure_path_inside_root(workflow_root, target, label)
    if not target.is_file():
        raise ConfigError(f"{label} must reference an existing file.")
    return relative


def _validate_workflow_relative_declared_path(workflow_root: Path, value: object, label: str) -> str:
    relative = _normalize_repo_pattern(value, label)
    target = workflow_root / relative
    _ensure_path_inside_root(workflow_root, target, label)
    return relative


def _ensure_path_inside_root(root: Path, target: Path, label: str) -> None:
    root_real = root.resolve()
    target_real = target.resolve()
    try:
        target_real.relative_to(root_real)
    except ValueError as exc:
        raise ConfigError(f"{label} must remain inside the workflow directory.") from exc


def _load_yaml_mapping(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise ConfigError(f"{label} is missing.")
    text = path.read_text(encoding="utf-8")
    if yaml is None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"{label} cannot be parsed as YAML without PyYAML installed. Install dependencies from requirements.txt."
            ) from exc
    else:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{label} cannot be parsed as YAML.") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{label} must parse to a YAML mapping.")
    return payload


def _validate_allowed_fields(payload: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError(f"{label} contains unknown fields: {', '.join(unknown)}.")


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string.")
    return value.strip()


def _require_choice(value: object, allowed: set[str], label: str) -> str:
    raw = _require_non_empty_string(value, label)
    if raw not in allowed:
        raise ConfigError(f"{label} must be one of {', '.join(sorted(allowed))}.")
    return raw


def _require_positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise ConfigError(f"{label} must be a positive integer.")
    return value


def _require_bool_default(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be a boolean.")
    return value


def _require_exact_int(value: object, expected: int, message: str) -> None:
    if not isinstance(value, int) or value != expected:
        raise ConfigError(message)
