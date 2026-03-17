from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import Draft3Validator, Draft4Validator, Draft6Validator, Draft7Validator
from jsonschema import FormatChecker, exceptions as jsonschema_exceptions

from .errors import SchemaValidationError

_FORMAT_CHECKER = FormatChecker()
_DEFAULT_VALIDATOR = Draft7Validator

try:
    from jsonschema import Draft201909Validator
except ImportError:  # pragma: no cover - only relevant on older jsonschema versions
    Draft201909Validator = None

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - only relevant on older jsonschema versions
    Draft202012Validator = None

_LATEST_KNOWN_VALIDATOR = Draft202012Validator or Draft201909Validator or Draft7Validator


def _build_validator_lookup() -> dict[str, type[Any]]:
    validators_by_uri: dict[str, type[Any]] = {}
    aliases = [
        (
            _LATEST_KNOWN_VALIDATOR,
            (
                "http://json-schema.org/schema",
                "https://json-schema.org/schema",
            ),
        ),
        (
            Draft3Validator,
            (
                "http://json-schema.org/draft-03/schema",
                "https://json-schema.org/draft-03/schema",
            ),
        ),
        (
            Draft4Validator,
            (
                "http://json-schema.org/draft-04/schema",
                "https://json-schema.org/draft-04/schema",
            ),
        ),
        (
            Draft6Validator,
            (
                "http://json-schema.org/draft-06/schema",
                "https://json-schema.org/draft-06/schema",
            ),
        ),
        (
            Draft7Validator,
            (
                "http://json-schema.org/draft-07/schema",
                "https://json-schema.org/draft-07/schema",
            ),
        ),
        (
            Draft201909Validator,
            (
                "http://json-schema.org/draft/2019-09/schema",
                "https://json-schema.org/draft/2019-09/schema",
            ),
        ),
        (
            Draft202012Validator,
            (
                "http://json-schema.org/draft/2020-12/schema",
                "https://json-schema.org/draft/2020-12/schema",
            ),
        ),
    ]
    for validator_cls, uris in aliases:
        if validator_cls is None:
            continue
        for uri in uris:
            validators_by_uri[uri.strip().rstrip("#")] = validator_cls
    return validators_by_uri


_KNOWN_VALIDATORS = _build_validator_lookup()


def ensure_json_schema(schema: Mapping[str, Any], *, label: str = "schema") -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        raise SchemaValidationError(f"{label} must be a mapping")

    ensure_json_compatible(schema, label=label)
    try:
        normalized = json.loads(deterministic_json_dumps(schema))
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(f"{label} must be JSON-serializable") from exc

    _ensure_pattern_keywords_compile(normalized, label=label)

    validator_cls = _resolve_validator_class(normalized)
    try:
        validator_cls.check_schema(normalized)
    except jsonschema_exceptions.SchemaError as exc:
        raise SchemaValidationError(_format_schema_error(exc, label=label)) from exc
    return normalized


def validate_json(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    validator_cls = _resolve_validator_class(schema)
    validator = validator_cls(schema, format_checker=_FORMAT_CHECKER)
    error = jsonschema_exceptions.best_match(validator.iter_errors(value))
    if error is None:
        return
    raise SchemaValidationError(_format_validation_error(error, root_path=path))


def deterministic_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def is_supported_model_type(candidate: Any) -> bool:
    return isinstance(candidate, type) and callable(getattr(candidate, "model_json_schema", None)) and callable(
        getattr(candidate, "model_validate", None)
    )


def ensure_json_compatible(value: Any, *, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool)) or _is_number(value):
        return

    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SchemaValidationError(f"{label} keys must be strings")
            ensure_json_compatible(item, label=f"{label}.{key}")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_json_compatible(item, label=f"{label}[{index}]")
        return

    raise SchemaValidationError(f"{label} must contain only JSON-compatible values")


def _resolve_validator_class(schema: Mapping[str, Any]) -> type[Any]:
    schema_uri = schema.get("$schema")
    if not isinstance(schema_uri, str) or not schema_uri.strip():
        return _DEFAULT_VALIDATOR
    return _KNOWN_VALIDATORS.get(_normalize_schema_uri(schema_uri), _DEFAULT_VALIDATOR)


def _normalize_schema_uri(uri: str) -> str:
    return uri.strip().rstrip("#")


def _ensure_pattern_keywords_compile(value: Any, *, label: str) -> None:
    if not isinstance(value, Mapping):
        return

    pattern = value.get("pattern")
    if pattern is not None:
        _compile_pattern(pattern, f"{label}.pattern")

    pattern_properties = value.get("patternProperties")
    if isinstance(pattern_properties, Mapping):
        for pattern_key, subschema in pattern_properties.items():
            _compile_pattern(pattern_key, f"{label}.patternProperties[{pattern_key!r}]")
            _recurse_schema(subschema, label=f"{label}.patternProperties[{pattern_key!r}]")

    _recurse_schema_mapping(value.get("properties"), label=f"{label}.properties")
    _recurse_schema_mapping(value.get("definitions"), label=f"{label}.definitions")
    _recurse_schema_mapping(value.get("$defs"), label=f"{label}.$defs")
    _recurse_schema_mapping(value.get("dependentSchemas"), label=f"{label}.dependentSchemas")

    _recurse_schema(value.get("additionalProperties"), label=f"{label}.additionalProperties")
    _recurse_schema(value.get("additionalItems"), label=f"{label}.additionalItems")
    _recurse_schema(value.get("contains"), label=f"{label}.contains")
    _recurse_schema(value.get("contentSchema"), label=f"{label}.contentSchema")
    _recurse_schema(value.get("else"), label=f"{label}.else")
    _recurse_schema(value.get("if"), label=f"{label}.if")
    _recurse_schema(value.get("items"), label=f"{label}.items")
    _recurse_schema(value.get("not"), label=f"{label}.not")
    _recurse_schema(value.get("propertyNames"), label=f"{label}.propertyNames")
    _recurse_schema(value.get("then"), label=f"{label}.then")
    _recurse_schema(value.get("unevaluatedItems"), label=f"{label}.unevaluatedItems")
    _recurse_schema(value.get("unevaluatedProperties"), label=f"{label}.unevaluatedProperties")

    _recurse_schema_list(value.get("allOf"), label=f"{label}.allOf")
    _recurse_schema_list(value.get("anyOf"), label=f"{label}.anyOf")
    _recurse_schema_list(value.get("oneOf"), label=f"{label}.oneOf")
    _recurse_schema_list(value.get("prefixItems"), label=f"{label}.prefixItems")

    dependencies = value.get("dependencies")
    if isinstance(dependencies, Mapping):
        for dependency_key, dependency_value in dependencies.items():
            if isinstance(dependency_value, Mapping):
                _recurse_schema(
                    dependency_value,
                    label=f"{label}.dependencies.{dependency_key}",
                )


def _recurse_schema(value: Any, *, label: str) -> None:
    if isinstance(value, Mapping):
        _ensure_pattern_keywords_compile(value, label=label)
        return

    if isinstance(value, list):
        _recurse_schema_list(value, label=label)


def _recurse_schema_list(value: Any, *, label: str) -> None:
    if not isinstance(value, list):
        return
    for index, item in enumerate(value):
        _recurse_schema(item, label=f"{label}[{index}]")


def _recurse_schema_mapping(value: Any, *, label: str) -> None:
    if not isinstance(value, Mapping):
        return
    for key, item in value.items():
        _recurse_schema(item, label=f"{label}.{key}")


def _compile_pattern(pattern: Any, label: str) -> None:
    if not isinstance(pattern, str):
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise SchemaValidationError(f"{label} must be a valid regex: {exc}") from exc


def _format_schema_error(error: jsonschema_exceptions.SchemaError, *, label: str) -> str:
    location = _compose_path(label, error.path)
    return f"{location}: {error.message}"


def _format_validation_error(error: jsonschema_exceptions.ValidationError, *, root_path: str) -> str:
    if error.validator == "required":
        missing_property = _extract_required_property(error)
        if missing_property is not None:
            return f"{_compose_path(root_path, [*error.absolute_path, missing_property])} is required"

    if error.validator == "additionalProperties":
        unexpected_properties = _extract_additional_properties(error)
        if unexpected_properties:
            return "; ".join(
                f"{_compose_path(root_path, [*error.absolute_path, property_name])} is not allowed"
                for property_name in unexpected_properties
            )

    location = _compose_path(root_path, error.absolute_path)
    if location == root_path:
        return f"{location}: {error.message}"
    return f"{location} {error.message}"


def _extract_required_property(error: jsonschema_exceptions.ValidationError) -> str | None:
    if not isinstance(error.validator_value, Sequence):
        return None
    for field in error.validator_value:
        if field not in error.instance:
            return field if isinstance(field, str) else None
    return None


def _extract_additional_properties(error: jsonschema_exceptions.ValidationError) -> list[str] | None:
    if error.validator_value is not False:
        return None
    if not isinstance(error.instance, Mapping) or not isinstance(error.schema, Mapping):
        return None

    properties = error.schema.get("properties", {})
    property_names = set(properties) if isinstance(properties, Mapping) else set()

    pattern_properties = error.schema.get("patternProperties", {})
    patterns = list(pattern_properties) if isinstance(pattern_properties, Mapping) else []

    unexpected: list[str] = []
    for key in error.instance:
        if not isinstance(key, str):
            continue
        if key in property_names:
            continue
        if any(re.search(pattern, key) is not None for pattern in patterns):
            continue
        unexpected.append(key)

    return unexpected or None


def _compose_path(root: str, segments: Sequence[Any]) -> str:
    path = root
    for segment in segments:
        if isinstance(segment, int):
            path += f"[{segment}]"
            continue
        path += f".{segment}"
    return path


def _is_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return True
