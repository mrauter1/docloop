from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


STATUS_RUNNING = "running"
STATUS_AWAITING_INPUT = "awaiting_input"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_STOPPED = "stopped"

TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_BLOCKED, STATUS_STOPPED}

FAILURE_PROVIDER_UNAVAILABLE = "provider_unavailable"
FAILURE_STEP_FAILED = "step_failed"
FAILURE_MAX_LOOPS = "max_loops_exceeded"
FAILURE_MAX_CYCLES = "max_cycles_exceeded"
FAILURE_INTERNAL = "internal_error"

EXIT_CODE_SUCCESS = 0
EXIT_CODE_PROVIDER_UNAVAILABLE = 20
EXIT_CODE_STEP_FAILED = 21
EXIT_CODE_MAX_LOOPS = 22
EXIT_CODE_MAX_CYCLES = 23
EXIT_CODE_BLOCKED = 24
EXIT_CODE_INTERNAL = 25
EXIT_CODE_AWAITING_INPUT = 26
EXIT_CODE_STOPPED = 27

DEFAULT_PROVIDER_TIMEOUT_SEC = 1800
DEFAULT_MAX_AUTO_ROUNDS = 3

RESERVED_TRANSITIONS = {"@done", "@retry", "@blocked"}


class ReflowError(RuntimeError):
    exit_code = EXIT_CODE_INTERNAL


class ConfigError(ReflowError):
    pass


class ProviderUnavailableError(ReflowError):
    exit_code = EXIT_CODE_PROVIDER_UNAVAILABLE


class StepFailedError(ReflowError):
    exit_code = EXIT_CODE_STEP_FAILED


class MaxLoopsExceededError(ReflowError):
    exit_code = EXIT_CODE_MAX_LOOPS


class MaxCyclesExceededError(ReflowError):
    exit_code = EXIT_CODE_MAX_CYCLES


class BlockedRunError(ReflowError):
    exit_code = EXIT_CODE_BLOCKED


class AwaitingInputError(ReflowError):
    exit_code = EXIT_CODE_AWAITING_INPUT


class StoppedRunError(ReflowError):
    exit_code = EXIT_CODE_STOPPED


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    kind: Literal["codex", "claude"]
    command: str
    model: str | None
    timeout_sec: int
    args: list[str]
    env: dict[str, str]


@dataclass(frozen=True)
class PolicySpec:
    allow_write: list[str] = field(default_factory=list)
    forbid_write: list[str] = field(default_factory=list)
    required_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentTransitions:
    default_target: str | None
    tag: str | None
    default_decision: str | None
    mapping: dict[str, str]


@dataclass(frozen=True)
class ContextEntry:
    path: str
    as_description: str


@dataclass(frozen=True)
class ProducesEntry:
    path: str
    as_description: str


@dataclass(frozen=True)
class AgentStep:
    name: str
    instructions: list[str]
    max_loops: int
    transitions: AgentTransitions
    provider: str | None = None
    count_toward_cycles: bool = False
    policy: PolicySpec | None = None
    context: list[ContextEntry] = field(default_factory=list)
    produces: list[ProducesEntry] = field(default_factory=list)
    kind: Literal["agent"] = "agent"


@dataclass(frozen=True)
class ShellStep:
    name: str
    cmd: str
    max_loops: int
    on_success: str
    on_failure: str
    count_toward_cycles: bool = False
    policy: PolicySpec | None = None
    kind: Literal["shell"] = "shell"


Step = AgentStep | ShellStep


@dataclass(frozen=True)
class WorkflowOperatorInput:
    full_auto_instructions: str | None
    max_auto_rounds: int


@dataclass(frozen=True)
class Workflow:
    name: str
    root: Path
    entry: str
    steps: dict[str, Step]
    task_mode: Literal["required", "optional", "none"]
    default_provider: str | None
    max_cycles: int | None
    operator_input: WorkflowOperatorInput


@dataclass(frozen=True)
class ReflowConfig:
    workspace: Path
    default_provider: str | None
    providers: dict[str, ProviderProfile]


@dataclass
class PendingInput:
    requested_at: str
    step: str
    loop: int
    questions: list[str]
    auto_round: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_at": self.requested_at,
            "step": self.step,
            "loop": self.loop,
            "questions": list(self.questions),
            "auto_round": self.auto_round,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PendingInput":
        return cls(
            requested_at=str(payload["requested_at"]),
            step=str(payload["step"]),
            loop=int(payload["loop"]),
            questions=[str(item) for item in payload["questions"]],
            auto_round=int(payload["auto_round"]),
        )


@dataclass
class RunState:
    run_id: str
    workflow: str
    task: str | None
    status: str
    current_step: str
    step_loops: dict[str, int]
    cycle_count: int
    started_at: str
    updated_at: str
    failure_type: str | None = None
    failure_reason: str | None = None
    pending_input: PendingInput | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "task": self.task,
            "status": self.status,
            "current_step": self.current_step,
            "step_loops": dict(self.step_loops),
            "cycle_count": self.cycle_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "failure_type": self.failure_type,
            "failure_reason": self.failure_reason,
            "pending_input": self.pending_input.to_dict() if self.pending_input else None,
        }
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunState":
        pending_payload = payload.get("pending_input")
        pending_input = None
        if isinstance(pending_payload, dict):
            pending_input = PendingInput.from_dict(pending_payload)

        return cls(
            run_id=str(payload["run_id"]),
            workflow=str(payload["workflow"]),
            task=str(payload["task"]) if payload.get("task") is not None else None,
            status=str(payload["status"]),
            current_step=str(payload["current_step"]),
            step_loops={str(k): int(v) for k, v in dict(payload["step_loops"]).items()},
            cycle_count=int(payload["cycle_count"]),
            started_at=str(payload["started_at"]),
            updated_at=str(payload["updated_at"]),
            failure_type=payload.get("failure_type"),
            failure_reason=payload.get("failure_reason"),
            pending_input=pending_input,
        )


@dataclass(frozen=True)
class IterationContext:
    step_name: str
    loop: int
    kind: str
    iteration_dir: Path
    meta_path: Path
    request_path: Path | None
    command_path: Path | None
    stdout_path: Path
    stderr_path: Path
    final_path: Path


@dataclass(frozen=True)
class InvocationResult:
    command_argv: list[str]
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False
    unavailable: bool = False


@dataclass(frozen=True)
class AgentOutcome:
    transition_target: str | None
    decision_value: str | None
    questions: list[str]

    @property
    def input_requested(self) -> bool:
        return bool(self.questions)


@dataclass(frozen=True)
class WorkspaceSnapshot:
    entries: dict[str, tuple[str, str]]
    escape_paths: set[str]


@dataclass(frozen=True)
class PolicyResult:
    changed_paths: list[str]
    violations: list[str]
    required_files_missing: list[str]

    @property
    def ok(self) -> bool:
        return not self.violations and not self.required_files_missing


def dataclass_to_dict(value: object) -> dict[str, object]:
    return asdict(value)
