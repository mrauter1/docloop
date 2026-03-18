from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class FallbackModel:
    model: str
    on_categories: tuple[str, ...] = ("provider_transport", "provider_rate_limit")


@dataclass(frozen=True)
class RuntimeBudget:
    max_requests: int | None = None
    max_estimated_total_tokens: int | None = None
    max_estimated_cost: float | None = None


@dataclass(frozen=True)
class RuntimeCost:
    request_count: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None


@dataclass(frozen=True)
class BatchPolicy:
    fallback_models: tuple[FallbackModel, ...] = ()
    budget: RuntimeBudget | None = None


@dataclass(frozen=True)
class UsageAccounting:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None


_FALLBACK_CATEGORIES = {
    "provider_transport",
    "provider_authentication",
    "provider_rate_limit",
    "provider_contract",
}


def normalize_fallback_models(fallback_models: Sequence[FallbackModel] | None) -> tuple[FallbackModel, ...]:
    if fallback_models is None:
        return ()
    normalized: list[FallbackModel] = []
    for index, fallback in enumerate(fallback_models):
        if not isinstance(fallback, FallbackModel):
            raise TypeError(f"fallback_models[{index}] must be a FallbackModel")
        if not isinstance(fallback.model, str) or not fallback.model.strip():
            raise ValueError(f"fallback_models[{index}].model must be a non-empty string")
        categories = tuple(_normalize_category(category, index=index) for category in fallback.on_categories)
        normalized.append(FallbackModel(model=fallback.model.strip(), on_categories=categories))
    return tuple(normalized)


def normalize_batch_policy(batch_policy: BatchPolicy | None) -> BatchPolicy | None:
    if batch_policy is None:
        return None
    if not isinstance(batch_policy, BatchPolicy):
        raise TypeError("batch_policy must be a BatchPolicy or None")
    budget = normalize_runtime_budget(batch_policy.budget)
    fallback_models = normalize_fallback_models(batch_policy.fallback_models)
    return BatchPolicy(fallback_models=fallback_models, budget=budget)


def normalize_runtime_budget(budget: RuntimeBudget | None) -> RuntimeBudget | None:
    if budget is None:
        return None
    if not isinstance(budget, RuntimeBudget):
        raise TypeError("budget must be a RuntimeBudget or None")
    max_requests = _normalize_optional_int(budget.max_requests, "budget.max_requests")
    max_tokens = _normalize_optional_int(budget.max_estimated_total_tokens, "budget.max_estimated_total_tokens")
    max_cost = _normalize_optional_float(budget.max_estimated_cost, "budget.max_estimated_cost")
    if max_requests is None and max_tokens is None and max_cost is None:
        raise ValueError("budget must set at least one limit")
    return RuntimeBudget(
        max_requests=max_requests,
        max_estimated_total_tokens=max_tokens,
        max_estimated_cost=max_cost,
    )


def normalize_pricing(pricing: Sequence[ModelPricing] | Mapping[str, ModelPricing] | None) -> dict[str, ModelPricing]:
    if pricing is None:
        return {}
    if isinstance(pricing, Mapping):
        values = pricing.values()
    else:
        values = pricing
    normalized: dict[str, ModelPricing] = {}
    for index, item in enumerate(values):
        if not isinstance(item, ModelPricing):
            raise TypeError(f"pricing[{index}] must be a ModelPricing")
        if not isinstance(item.model, str) or not item.model.strip():
            raise ValueError(f"pricing[{index}].model must be a non-empty string")
        normalized[item.model.strip()] = ModelPricing(
            model=item.model.strip(),
            input_cost_per_1k_tokens=_normalize_optional_float(item.input_cost_per_1k_tokens, f"pricing[{index}].input_cost_per_1k_tokens", allow_zero=True),
            output_cost_per_1k_tokens=_normalize_optional_float(item.output_cost_per_1k_tokens, f"pricing[{index}].output_cost_per_1k_tokens", allow_zero=True),
        )
    return normalized


def extract_usage_accounting(provider_metadata: Mapping[str, Any] | None) -> UsageAccounting | None:
    if not isinstance(provider_metadata, Mapping):
        return None
    prompt = _extract_int(provider_metadata, ("input_tokens", "prompt_tokens"))
    completion = _extract_int(provider_metadata, ("output_tokens", "completion_tokens"))
    total = _extract_int(provider_metadata, ("total_tokens",))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    if prompt is None and completion is None and total is None:
        return None
    return UsageAccounting(input_tokens=prompt, output_tokens=completion, total_tokens=total)


def add_runtime_cost(
    current: RuntimeCost | None,
    *,
    usage: UsageAccounting | None,
    pricing: ModelPricing | None,
    request_count: int = 1,
) -> RuntimeCost:
    base = current or RuntimeCost()
    input_tokens = _sum_optional(base.input_tokens, usage.input_tokens if usage else None)
    output_tokens = _sum_optional(base.output_tokens, usage.output_tokens if usage else None)
    total_tokens = _sum_optional(base.total_tokens, usage.total_tokens if usage else None)
    estimated_cost = base.estimated_cost
    estimated_addition = estimate_usage_cost(usage, pricing) if usage is not None else None
    if estimated_addition is not None:
        estimated_cost = (estimated_cost or 0.0) + estimated_addition
    return RuntimeCost(
        request_count=base.request_count + request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
    )


def estimate_usage_cost(usage: UsageAccounting | None, pricing: ModelPricing | None) -> float | None:
    if usage is None or pricing is None:
        return None
    total = 0.0
    seen = False
    if usage.input_tokens is not None and pricing.input_cost_per_1k_tokens is not None:
        total += (usage.input_tokens / 1000.0) * pricing.input_cost_per_1k_tokens
        seen = True
    if usage.output_tokens is not None and pricing.output_cost_per_1k_tokens is not None:
        total += (usage.output_tokens / 1000.0) * pricing.output_cost_per_1k_tokens
        seen = True
    return total if seen else None


def is_budget_exhausted(cost: RuntimeCost | None, budget: RuntimeBudget | None) -> bool:
    if cost is None or budget is None:
        return False
    if budget.max_requests is not None and cost.request_count >= budget.max_requests:
        return True
    if budget.max_estimated_total_tokens is not None and cost.total_tokens is not None:
        if cost.total_tokens >= budget.max_estimated_total_tokens:
            return True
    if budget.max_estimated_cost is not None and cost.estimated_cost is not None:
        if cost.estimated_cost >= budget.max_estimated_cost:
            return True
    return False


def next_fallback_model(
    *,
    fallback_models: Sequence[FallbackModel],
    used_models: Iterable[str],
    category: str,
) -> FallbackModel | None:
    seen = set(used_models)
    for fallback in fallback_models:
        if fallback.model in seen:
            continue
        if category in fallback.on_categories:
            return fallback
    return None


def _normalize_category(category: Any, *, index: int) -> str:
    if not isinstance(category, str):
        raise ValueError(f"fallback_models[{index}].on_categories must contain strings")
    value = category.strip()
    if value not in _FALLBACK_CATEGORIES:
        allowed = ", ".join(sorted(_FALLBACK_CATEGORIES))
        raise ValueError(f"fallback_models[{index}].on_categories contains unsupported category {value!r}; expected one of {allowed}")
    return value


def _normalize_optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer or None")
    return value


def _normalize_optional_float(value: Any, label: str, *, allow_zero: bool = False) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be a positive number or None")
    number = float(value)
    if allow_zero:
        if number < 0:
            raise ValueError(f"{label} must be zero or greater")
    elif number <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return number


def _extract_int(metadata: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return left + right
