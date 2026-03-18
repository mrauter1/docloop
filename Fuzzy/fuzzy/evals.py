from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .core import DEFAULT_MAX_ATTEMPTS, _UNSET, classify, dispatch, extract
from .errors import FrameworkError
from .schema import deterministic_json_dumps, ensure_json_compatible
from .trace import TraceRecord, TraceResult, serialize_trace
from .types import Command, Message


@dataclass(frozen=True)
class EvalCase:
    name: str
    expected: Any
    context: Any = _UNSET
    messages: Sequence[Message] | Any = _UNSET
    note: str | None = None
    tags: tuple[str, ...] = ()
    system_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "expected": _json_safe(self.expected),
            "note": self.note,
            "tags": list(self.tags),
        }
        if self.context is not _UNSET:
            payload["context"] = _json_safe(self.context)
        if self.messages is not _UNSET:
            payload["messages"] = _json_safe(self.messages)
        if self.system_prompt is not None:
            payload["system_prompt"] = self.system_prompt
        return payload


@dataclass(frozen=True)
class EvalSuite:
    task: str
    cases: tuple[EvalCase, ...]
    name: str = "suite"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task": self.task,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass(frozen=True)
class EvalCaseResult:
    name: str
    passed: bool
    expected: Any
    actual: Any = None
    trace: TraceRecord | None = None
    error_category: str | None = None
    error_message: str | None = None
    note: str | None = None
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "passed": self.passed,
            "expected": _json_safe(self.expected),
            "actual": _json_safe(self.actual),
            "error_category": self.error_category,
            "error_message": self.error_message,
            "note": self.note,
            "tags": list(self.tags),
        }
        if self.trace is not None:
            payload["trace"] = serialize_trace(self.trace)
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class EvalSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    retry_rate: float
    validation_exhausted_count: int
    accuracy: float | None = None
    schema_validity_rate: float | None = None
    confusion_matrix: dict[str, dict[str, int]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": self.pass_rate,
            "retry_rate": self.retry_rate,
            "validation_exhausted_count": self.validation_exhausted_count,
            "accuracy": self.accuracy,
            "schema_validity_rate": self.schema_validity_rate,
            "confusion_matrix": self.confusion_matrix,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class EvalReport:
    task: str
    model: str
    case_results: tuple[EvalCaseResult, ...]
    summary: EvalSummary
    suite_name: str = "suite"
    variant_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "suite_name": self.suite_name,
            "task": self.task,
            "model": self.model,
            "variant_name": self.variant_name,
            "metadata": _json_safe(self.metadata) if self.metadata else None,
            "summary": self.summary.to_dict(),
            "case_results": [result.to_dict() for result in self.case_results],
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class EvalVariant:
    name: str
    model: str | None = None
    system_prompt: str | None = None


async def run_classification_eval(
    *,
    adapter: Any,
    model: str,
    labels: Sequence[str],
    cases: Sequence[EvalCase],
    suite_name: str = "classification",
    system_prompt: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EvalReport:
    return await _run_cases(
        task="classification",
        suite_name=suite_name,
        model=model,
        cases=cases,
        invoke=lambda case: classify(
            adapter=adapter,
            model=model,
            labels=labels,
            context=case.context,
            messages=case.messages,
            max_attempts=max_attempts,
            system_prompt=system_prompt if case.system_prompt is None else case.system_prompt,
            return_trace=True,
        ),
        compute_accuracy=True,
    )


async def run_extraction_eval(
    *,
    adapter: Any,
    model: str,
    schema: Any,
    cases: Sequence[EvalCase],
    suite_name: str = "extraction",
    system_prompt: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EvalReport:
    return await _run_cases(
        task="extraction",
        suite_name=suite_name,
        model=model,
        cases=cases,
        invoke=lambda case: extract(
            adapter=adapter,
            model=model,
            schema=schema,
            context=case.context,
            messages=case.messages,
            max_attempts=max_attempts,
            system_prompt=system_prompt if case.system_prompt is None else case.system_prompt,
            return_trace=True,
        ),
        schema_validity=True,
    )


async def run_dispatch_eval(
    *,
    adapter: Any,
    model: str,
    cases: Sequence[EvalCase],
    labels: Sequence[str] | None = None,
    commands: Sequence[Command | Mapping[str, Any]] | None = None,
    auto_execute: bool = False,
    suite_name: str = "dispatch",
    system_prompt: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EvalReport:
    return await _run_cases(
        task="dispatch",
        suite_name=suite_name,
        model=model,
        cases=cases,
        invoke=lambda case: dispatch(
            adapter=adapter,
            model=model,
            labels=labels,
            commands=commands,
            context=case.context,
            messages=case.messages,
            auto_execute=auto_execute,
            max_attempts=max_attempts,
            system_prompt=system_prompt if case.system_prompt is None else case.system_prompt,
            return_trace=True,
        ),
        compute_accuracy=labels is not None,
    )


async def run_eval_matrix(
    *,
    variants: Sequence[EvalVariant],
    runner: Callable[[EvalVariant], Awaitable[EvalReport]],
) -> dict[str, EvalReport]:
    reports: dict[str, EvalReport] = {}
    for variant in variants:
        report = await runner(variant)
        reports[variant.name] = EvalReport(
            task=report.task,
            model=report.model,
            suite_name=report.suite_name,
            case_results=report.case_results,
            summary=report.summary,
            variant_name=variant.name,
            metadata=report.metadata,
        )
    return reports


def assert_eval_thresholds(
    report: EvalReport,
    *,
    min_pass_rate: float | None = None,
    max_retry_rate: float | None = None,
    max_validation_exhausted_count: int | None = None,
    min_accuracy: float | None = None,
    min_schema_validity_rate: float | None = None,
) -> None:
    failures: list[str] = []
    summary = report.summary
    if min_pass_rate is not None and summary.pass_rate < min_pass_rate:
        failures.append(f"pass_rate {summary.pass_rate:.3f} is below {min_pass_rate:.3f}")
    if max_retry_rate is not None and summary.retry_rate > max_retry_rate:
        failures.append(f"retry_rate {summary.retry_rate:.3f} exceeds {max_retry_rate:.3f}")
    if max_validation_exhausted_count is not None and summary.validation_exhausted_count > max_validation_exhausted_count:
        failures.append(
            f"validation_exhausted_count {summary.validation_exhausted_count} exceeds {max_validation_exhausted_count}"
        )
    if min_accuracy is not None:
        accuracy = summary.accuracy or 0.0
        if accuracy < min_accuracy:
            failures.append(f"accuracy {accuracy:.3f} is below {min_accuracy:.3f}")
    if min_schema_validity_rate is not None:
        validity_rate = summary.schema_validity_rate or 0.0
        if validity_rate < min_schema_validity_rate:
            failures.append(f"schema_validity_rate {validity_rate:.3f} is below {min_schema_validity_rate:.3f}")
    if failures:
        raise AssertionError("; ".join(failures))


def load_eval_suite(path: str | Path) -> EvalSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Eval suite file must be a JSON object")
    raw_cases = payload.get("cases", [])
    if not isinstance(raw_cases, list):
        raise ValueError("Eval suite cases must be a list")
    cases: list[EvalCase] = []
    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, Mapping):
            raise ValueError(f"Eval suite case {index} must be an object")
        cases.append(
            EvalCase(
                name=str(raw_case["name"]),
                expected=raw_case.get("expected"),
                context=raw_case["context"] if "context" in raw_case else _UNSET,
                messages=raw_case["messages"] if "messages" in raw_case else _UNSET,
                note=raw_case.get("note"),
                tags=tuple(str(tag) for tag in raw_case.get("tags", [])),
                system_prompt=raw_case.get("system_prompt"),
            )
        )
    return EvalSuite(
        name=str(payload.get("name", "suite")),
        task=str(payload.get("task", "unknown")),
        cases=tuple(cases),
    )


def write_eval_report(report: EvalReport, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".md":
        target.write_text(_render_report_markdown(report), encoding="utf-8")
        return target
    target.write_text(deterministic_json_dumps(report.to_dict()) + "\n", encoding="utf-8")
    return target


async def _run_cases(
    *,
    task: str,
    suite_name: str,
    model: str,
    cases: Sequence[EvalCase],
    invoke: Callable[[EvalCase], Awaitable[TraceResult[Any]]],
    compute_accuracy: bool = False,
    schema_validity: bool = False,
) -> EvalReport:
    results: list[EvalCaseResult] = []
    retry_count = 0
    validation_exhausted_count = 0
    confusion_matrix: dict[str, dict[str, int]] = {}
    successful_cases = 0

    for case in cases:
        try:
            trace_result = await invoke(case)
            trace = trace_result.trace
            actual = trace_result.value
            passed = actual == case.expected
            successful_cases += 1
            retry_count += 1 if trace.attempt_count > 1 else 0
            if compute_accuracy and isinstance(case.expected, str) and isinstance(actual, str):
                confusion_matrix.setdefault(case.expected, {})
                confusion_matrix[case.expected][actual] = confusion_matrix[case.expected].get(actual, 0) + 1
            results.append(
                EvalCaseResult(
                    name=case.name,
                    passed=passed,
                    expected=case.expected,
                    actual=actual,
                    trace=trace,
                    note=case.note,
                    tags=case.tags,
                )
            )
        except FrameworkError as exc:
            trace = getattr(exc, "trace", None)
            if trace is not None and trace.attempt_count > 1:
                retry_count += 1
            if exc.category == "validation_exhausted":
                validation_exhausted_count += 1
            results.append(
                EvalCaseResult(
                    name=case.name,
                    passed=False,
                    expected=case.expected,
                    actual={"error_category": exc.category},
                    trace=trace,
                    error_category=exc.category,
                    error_message=exc.message,
                    note=case.note,
                    tags=case.tags,
                )
            )

    total_cases = len(results)
    passed_cases = sum(1 for result in results if result.passed)
    failed_cases = total_cases - passed_cases
    summary = EvalSummary(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=_rate(passed_cases, total_cases),
        retry_rate=_rate(retry_count, total_cases),
        validation_exhausted_count=validation_exhausted_count,
        accuracy=_rate(passed_cases, total_cases) if compute_accuracy else None,
        schema_validity_rate=_rate(successful_cases, total_cases) if schema_validity else None,
        confusion_matrix=confusion_matrix or None,
    )
    return EvalReport(
        suite_name=suite_name,
        task=task,
        model=model,
        case_results=tuple(results),
        summary=summary,
    )


def _render_report_markdown(report: EvalReport) -> str:
    lines = [
        f"# Eval Report: {report.suite_name}",
        "",
        f"- task: `{report.task}`",
        f"- model: `{report.model}`",
        f"- pass_rate: `{report.summary.pass_rate:.3f}`",
        f"- retry_rate: `{report.summary.retry_rate:.3f}`",
        f"- validation_exhausted_count: `{report.summary.validation_exhausted_count}`",
        "",
        "## Cases",
        "",
    ]
    for result in report.case_results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- `{result.name}`: {status}")
    return "\n".join(lines) + "\n"


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        ensure_json_compatible(value)
    except Exception:
        if isinstance(value, Mapping):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return {"repr": repr(value), "type": type(value).__name__}
    return json.loads(deterministic_json_dumps(value))
