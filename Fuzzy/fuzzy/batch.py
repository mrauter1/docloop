from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from .core import DEFAULT_MAX_ATTEMPTS, _UNSET, classify, dispatch, eval_bool, extract
from .execution import CommandPolicy
from .errors import FrameworkError
from .policy import BatchPolicy, ModelPricing, RuntimeCost, UsageAccounting, add_runtime_cost, extract_usage_accounting, is_budget_exhausted, normalize_batch_policy, normalize_pricing
from .trace import TraceRecord, TraceResult
from .types import Command, Message

BatchOperation = Literal["eval_bool", "classify", "extract", "dispatch"]


@dataclass(frozen=True)
class BatchCall:
    operation: BatchOperation
    name: str | None = None
    context: Any = _UNSET
    messages: Sequence[Message] | Any = _UNSET
    expression: str | None = None
    labels: Sequence[str] | None = None
    schema: Any = None
    commands: Sequence[Command | Mapping[str, Any]] | None = None
    auto_execute: bool = False
    model: str | None = None
    max_attempts: int | None = None
    system_prompt: str | None = None
    fallback_models: Sequence[Any] | None = None
    command_policy: CommandPolicy | None = None


@dataclass(frozen=True)
class BatchError:
    category: str
    message: str
    attempt_count: int
    final_validation_category: str | None = None


@dataclass(frozen=True)
class BatchResult:
    index: int
    operation: BatchOperation
    name: str | None
    success: bool
    value: Any = None
    trace: TraceRecord | None = None
    error: BatchError | None = None
    skipped: bool = False


@dataclass(frozen=True)
class BatchReport:
    total_calls: int
    completed_calls: int
    succeeded_calls: int
    failed_calls: int
    skipped_calls: int
    results: tuple[BatchResult, ...]
    cost: RuntimeCost | None = None
    budget_exhausted: bool = False


@dataclass(frozen=True)
class _BatchExecutionOutcome:
    public_result: BatchResult
    trace: TraceRecord | None = None


async def run_batch(
    calls: Sequence[BatchCall],
    *,
    adapter: Any,
    model: str | None = None,
    concurrency: int = 4,
    return_traces: bool = False,
    stop_on_error: bool = False,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    system_prompt: str | None = None,
    batch_policy: BatchPolicy | None = None,
    pricing: Sequence[ModelPricing] | None = None,
) -> BatchReport:
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1:
        raise FrameworkError(
            operation="batch",
            category="invalid_configuration",
            message="concurrency must be a positive integer",
            attempt_count=0,
        )
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise FrameworkError(
            operation="batch",
            category="invalid_configuration",
            message="max_attempts must be a positive integer",
            attempt_count=0,
        )
    try:
        normalized_batch_policy = normalize_batch_policy(batch_policy)
        pricing_map = normalize_pricing(pricing)
    except (TypeError, ValueError) as exc:
        raise FrameworkError(
            operation="batch",
            category="invalid_configuration",
            message=str(exc),
            attempt_count=0,
            cause=exc,
        ) from exc

    semaphore = asyncio.Semaphore(concurrency)
    stop_state = {"failed": False, "budget_exhausted": False}
    cost_state = {"cost": None}
    results: list[BatchResult | None] = [None] * len(calls)

    async def worker(index: int, call: BatchCall) -> None:
        if stop_on_error and stop_state["failed"]:
            results[index] = _skipped_result(index, call)
            return
        if stop_state["budget_exhausted"]:
            results[index] = _skipped_result(index, call)
            return

        async with semaphore:
            if stop_on_error and stop_state["failed"]:
                results[index] = _skipped_result(index, call)
                return
            if stop_state["budget_exhausted"]:
                results[index] = _skipped_result(index, call)
                return
            outcome = await _execute_call(
                call,
                index=index,
                adapter=adapter,
                default_model=model,
                default_max_attempts=max_attempts,
                default_system_prompt=system_prompt,
                fallback_models=normalized_batch_policy.fallback_models if normalized_batch_policy else (),
                return_traces=return_traces,
            )
            results[index] = outcome.public_result
            if outcome.trace is not None:
                result_model = _result_model(outcome.trace, fallback_default=call.model or model or "")
                cost_state["cost"] = add_runtime_cost(
                    cost_state["cost"],
                    usage=_trace_usage(outcome.trace),
                    pricing=pricing_map.get(result_model),
                    request_count=outcome.trace.attempt_count,
                )
            if stop_on_error and not outcome.public_result.success:
                stop_state["failed"] = True
            if normalized_batch_policy is not None and is_budget_exhausted(cost_state["cost"], normalized_batch_policy.budget):
                stop_state["budget_exhausted"] = True

    await asyncio.gather(*(worker(index, call) for index, call in enumerate(calls)))
    finalized = tuple(result for result in results if result is not None)
    succeeded_calls = sum(1 for result in finalized if result.success)
    skipped_calls = sum(1 for result in finalized if result.skipped)
    failed_calls = len(finalized) - succeeded_calls
    completed_calls = len(finalized) - skipped_calls
    return BatchReport(
        total_calls=len(calls),
        completed_calls=completed_calls,
        succeeded_calls=succeeded_calls,
        failed_calls=failed_calls,
        skipped_calls=skipped_calls,
        results=finalized,
        cost=cost_state["cost"],
        budget_exhausted=stop_state["budget_exhausted"],
    )


async def _execute_call(
    call: BatchCall,
    *,
    index: int,
    adapter: Any,
    default_model: str | None,
    default_max_attempts: int,
    default_system_prompt: str | None,
    fallback_models: Sequence[Any],
    return_traces: bool,
) -> _BatchExecutionOutcome:
    try:
        value = await _invoke_call(
            call,
            adapter=adapter,
            default_model=default_model,
            default_max_attempts=default_max_attempts,
            default_system_prompt=default_system_prompt,
            fallback_models=fallback_models,
        )
    except FrameworkError as exc:
        return _BatchExecutionOutcome(
            public_result=BatchResult(
                index=index,
                operation=call.operation,
                name=call.name,
                success=False,
                trace=exc.trace,
                error=BatchError(
                    category=exc.category,
                    message=exc.message,
                    attempt_count=exc.attempt_count,
                    final_validation_category=exc.final_validation_category,
                ),
            ),
            trace=exc.trace,
        )
    except Exception as exc:
        return _BatchExecutionOutcome(
            public_result=BatchResult(
                index=index,
                operation=call.operation,
                name=call.name,
                success=False,
                error=BatchError(
                    category="unexpected_error",
                    message=str(exc),
                    attempt_count=0,
                ),
            )
        )

    traced = value
    if not isinstance(traced, TraceResult):
        raise AssertionError("batch execution requires TraceResult values")
    if return_traces:
        return _BatchExecutionOutcome(
            public_result=BatchResult(
                index=index,
                operation=call.operation,
                name=call.name,
                success=True,
                value=traced.value,
                trace=traced.trace,
            ),
            trace=traced.trace,
        )

    return _BatchExecutionOutcome(
        public_result=BatchResult(
            index=index,
            operation=call.operation,
            name=call.name,
            success=True,
            value=traced.value,
        ),
        trace=traced.trace,
    )


async def _invoke_call(
    call: BatchCall,
    *,
    adapter: Any,
    default_model: str | None,
    default_max_attempts: int,
    default_system_prompt: str | None,
    fallback_models: Sequence[Any],
) -> Any:
    resolved_model = default_model if call.model is None else call.model
    if not isinstance(resolved_model, str) or not resolved_model.strip():
        raise FrameworkError(
            operation="batch",
            category="invalid_configuration",
            message="model must be provided either at the batch level or per call",
            attempt_count=0,
        )

    resolved_max_attempts = default_max_attempts if call.max_attempts is None else call.max_attempts
    resolved_system_prompt = default_system_prompt if call.system_prompt is None else call.system_prompt
    kwargs = {
        "adapter": adapter,
        "model": resolved_model,
        "context": call.context,
        "messages": call.messages,
        "max_attempts": resolved_max_attempts,
        "system_prompt": resolved_system_prompt,
        "fallback_models": fallback_models if call.fallback_models is None else call.fallback_models,
        "return_trace": True,
    }

    if call.operation == "eval_bool":
        if call.expression is None:
            raise FrameworkError(
                operation="eval_bool",
                category="invalid_configuration",
                message="expression is required for eval_bool batch calls",
                attempt_count=0,
            )
        return await eval_bool(expression=call.expression, **kwargs)
    if call.operation == "classify":
        if call.labels is None:
            raise FrameworkError(
                operation="classify",
                category="invalid_configuration",
                message="labels are required for classify batch calls",
                attempt_count=0,
            )
        return await classify(labels=call.labels, **kwargs)
    if call.operation == "extract":
        if call.schema is None:
            raise FrameworkError(
                operation="extract",
                category="invalid_configuration",
                message="schema is required for extract batch calls",
                attempt_count=0,
            )
        return await extract(schema=call.schema, **kwargs)
    if call.operation == "dispatch":
        return await dispatch(
            labels=call.labels,
            commands=call.commands,
            auto_execute=call.auto_execute,
            command_policy=call.command_policy,
            **kwargs,
        )
    raise FrameworkError(
        operation="batch",
        category="invalid_configuration",
        message=f"unsupported batch operation {call.operation!r}",
        attempt_count=0,
    )


def _result_model(trace: TraceRecord, *, fallback_default: str) -> str:
    if trace.attempts:
        return trace.attempts[-1].model
    return fallback_default


def _trace_usage(trace: TraceRecord) -> Any:
    aggregate = UsageAccounting()
    seen = False
    for attempt in trace.attempts:
        usage = extract_usage_accounting(attempt.provider_metadata)
        if usage is None:
            continue
        seen = True
        aggregate = UsageAccounting(
            input_tokens=_sum_optional(aggregate.input_tokens, usage.input_tokens),
            output_tokens=_sum_optional(aggregate.output_tokens, usage.output_tokens),
            total_tokens=_sum_optional(aggregate.total_tokens, usage.total_tokens),
        )
    return aggregate if seen else None


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return left + right


def _skipped_result(index: int, call: BatchCall) -> BatchResult:
    return BatchResult(
        index=index,
        operation=call.operation,
        name=call.name,
        success=False,
        skipped=True,
        error=BatchError(
            category="batch_stopped",
            message="Skipped because a previous batch call failed",
            attempt_count=0,
        ),
    )
