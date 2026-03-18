from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    reason: str | None = None


@dataclass(frozen=True)
class ExecutionContext:
    operation: str
    model: str
    command_name: str
    attempt_count: int


@dataclass(frozen=True)
class AuditRecord:
    operation: str
    model: str
    decision: dict[str, Any]
    approved: bool | None
    executed: bool
    simulated: bool
    result: Any = None
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}


ApprovalHook = Callable[[dict[str, Any], ExecutionContext], ApprovalDecision]
AuditSink = Callable[[AuditRecord], Any]


@dataclass(frozen=True)
class CommandPolicy:
    allow_commands: tuple[str, ...] | None = None
    deny_commands: tuple[str, ...] | None = None
    timeout_seconds: float | None = None
    simulator_mode: bool = False
    approval_hook: ApprovalHook | None = None
    audit_sink: AuditSink | None = None


def normalize_command_policy(command_policy: CommandPolicy | None) -> CommandPolicy | None:
    if command_policy is None:
        return None
    if not isinstance(command_policy, CommandPolicy):
        raise TypeError("command_policy must be a CommandPolicy or None")
    allow = _normalize_name_list(command_policy.allow_commands, "allow_commands")
    deny = _normalize_name_list(command_policy.deny_commands, "deny_commands")
    timeout_seconds = _normalize_timeout(command_policy.timeout_seconds)
    if command_policy.approval_hook is not None and not callable(command_policy.approval_hook):
        raise TypeError("approval_hook must be callable or None")
    if command_policy.audit_sink is not None and not callable(command_policy.audit_sink):
        raise TypeError("audit_sink must be callable or None")
    return CommandPolicy(
        allow_commands=allow,
        deny_commands=deny,
        timeout_seconds=timeout_seconds,
        simulator_mode=bool(command_policy.simulator_mode),
        approval_hook=command_policy.approval_hook,
        audit_sink=command_policy.audit_sink,
    )


def command_allowed(command_name: str, command_policy: CommandPolicy | None) -> tuple[bool, str | None]:
    if command_policy is None:
        return True, None
    if command_policy.allow_commands is not None and command_name not in command_policy.allow_commands:
        return False, f"Command {command_name!r} is not in the allow-list"
    if command_policy.deny_commands is not None and command_name in command_policy.deny_commands:
        return False, f"Command {command_name!r} is in the deny-list"
    return True, None


def run_approval_hook(
    *,
    decision: dict[str, Any],
    context: ExecutionContext,
    command_policy: CommandPolicy | None,
) -> ApprovalDecision | None:
    if command_policy is None or command_policy.approval_hook is None:
        return None
    outcome = command_policy.approval_hook(decision, context)
    if isinstance(outcome, ApprovalDecision):
        return outcome
    if isinstance(outcome, Mapping):
        approved = bool(outcome.get("approved"))
        reason = outcome.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise TypeError("approval_hook reason must be a string or None")
        return ApprovalDecision(approved=approved, reason=reason)
    raise TypeError("approval_hook must return ApprovalDecision or a mapping with approved/reason")


def emit_audit_record(command_policy: CommandPolicy | None, record: AuditRecord) -> None:
    if command_policy is None or command_policy.audit_sink is None:
        return
    command_policy.audit_sink(record)


def save_audit_record(record: AuditRecord, path_or_dir: str | Path) -> Path:
    target = Path(path_or_dir)
    if target.suffix.lower() != ".json":
        target = target / f"audit-{record.operation}-{record.model}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _normalize_name_list(values: Sequence[str] | None, label: str) -> tuple[str, ...] | None:
    if values is None:
        return None
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        normalized.append(value.strip())
    return tuple(normalized)


def _normalize_timeout(value: float | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError("timeout_seconds must be a positive number or None")
    return float(value)
