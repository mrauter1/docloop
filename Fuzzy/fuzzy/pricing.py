from __future__ import annotations

from dataclasses import dataclass

from .policy import ModelPricing


@dataclass(frozen=True)
class PricingCatalog:
    name: str
    source: str
    updated_at: str
    entries: tuple[ModelPricing, ...]


_DEFAULT_CATALOG = PricingCatalog(
    name="default",
    source="Checked-in first-party catalog. Review and update before relying on price-sensitive budgets.",
    updated_at="2026-03-18",
    entries=(
        ModelPricing(model="gpt-4o-mini", input_cost_per_1k_tokens=0.00015, output_cost_per_1k_tokens=0.0006),
        ModelPricing(model="claude-3-5-haiku-latest", input_cost_per_1k_tokens=0.0008, output_cost_per_1k_tokens=0.004),
        ModelPricing(model="gemini-2.0-flash", input_cost_per_1k_tokens=0.0001, output_cost_per_1k_tokens=0.0004),
    ),
)

_CATALOGS = {_DEFAULT_CATALOG.name: _DEFAULT_CATALOG}


def get_pricing_catalog(name: str = "default") -> PricingCatalog:
    try:
        return _CATALOGS[name]
    except KeyError as exc:
        available = ", ".join(sorted(_CATALOGS))
        raise KeyError(f"Unknown pricing catalog {name!r}; expected one of {available}") from exc


def list_pricing_models(name: str = "default") -> tuple[str, ...]:
    catalog = get_pricing_catalog(name)
    return tuple(entry.model for entry in catalog.entries)


def find_model_pricing(model: str, *, catalog: str = "default") -> ModelPricing | None:
    normalized_model = _normalize_model_name(model)
    for entry in get_pricing_catalog(catalog).entries:
        if entry.model == normalized_model:
            return entry
    return None


def get_model_pricing(model: str, *, catalog: str = "default") -> ModelPricing:
    pricing = find_model_pricing(model, catalog=catalog)
    if pricing is None:
        available = ", ".join(list_pricing_models(catalog))
        raise KeyError(f"Model {model!r} is not present in pricing catalog {catalog!r}. Available models: {available}")
    return pricing


def pricing_for_models(models: list[str] | tuple[str, ...], *, catalog: str = "default") -> list[ModelPricing]:
    return [get_model_pricing(model, catalog=catalog) for model in models]


def _normalize_model_name(model: str) -> str:
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    return model.strip()
