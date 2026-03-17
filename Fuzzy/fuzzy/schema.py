from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

from .errors import SchemaValidationError

_TYPE_NAMES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def ensure_json_schema(schema: Mapping[str, Any], *, label: str = "schema") -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        raise SchemaValidationError(f"{label} must be a mapping")
    normalized = dict(schema)
    ensure_json_compatible(normalized, label=label)
    try:
        deterministic_json_dumps(normalized)
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(f"{label} must be JSON-serializable") from exc
    _validate_schema_document(normalized, label=label)
    return normalized


def validate_json(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    _validate_value(value, schema, path)


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


def _validate_schema_document(schema: Mapping[str, Any], *, label: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None:
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
        if not allowed_types or any(item not in _TYPE_NAMES for item in allowed_types):
            raise SchemaValidationError(f"{label} has unsupported type declaration")

    if "enum" in schema and not isinstance(schema["enum"], list):
        raise SchemaValidationError(f"{label}.enum must be a list")

    for key in ("properties", "patternProperties"):
        if key in schema and not isinstance(schema[key], Mapping):
            raise SchemaValidationError(f"{label}.{key} must be a mapping")

    if "required" in schema and (
        not isinstance(schema["required"], list) or any(not isinstance(item, str) for item in schema["required"])
    ):
        raise SchemaValidationError(f"{label}.required must be a list of strings")

    if "items" in schema and not isinstance(schema["items"], Mapping):
        raise SchemaValidationError(f"{label}.items must be a mapping")

    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], (bool, Mapping)):
        raise SchemaValidationError(f"{label}.additionalProperties must be a boolean or mapping")

    _validate_number_keyword(schema, key="minimum", label=label)
    _validate_number_keyword(schema, key="maximum", label=label)
    _validate_non_negative_integer_keyword(schema, key="minLength", label=label)
    _validate_non_negative_integer_keyword(schema, key="maxLength", label=label)
    _validate_non_negative_integer_keyword(schema, key="minItems", label=label)
    _validate_non_negative_integer_keyword(schema, key="maxItems", label=label)
    _validate_pattern_keyword(schema, key="pattern", label=label)
    _validate_min_max_pair(schema, minimum_key="minimum", maximum_key="maximum", label=label)
    _validate_min_max_pair(schema, minimum_key="minLength", maximum_key="maxLength", label=label)
    _validate_min_max_pair(schema, minimum_key="minItems", maximum_key="maxItems", label=label)

    for combiner in ("oneOf", "anyOf", "allOf"):
        if combiner in schema:
            variants = schema[combiner]
            if not isinstance(variants, list) or not variants or any(not isinstance(item, Mapping) for item in variants):
                raise SchemaValidationError(f"{label}.{combiner} must be a non-empty list of mappings")
            for index, variant in enumerate(variants):
                _validate_schema_document(variant, label=f"{label}.{combiner}[{index}]")

    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            if not isinstance(prop_name, str) or not isinstance(prop_schema, Mapping):
                raise SchemaValidationError(f"{label}.properties entries must map string keys to mappings")
            _validate_schema_document(prop_schema, label=f"{label}.properties.{prop_name}")

    if "patternProperties" in schema:
        for pattern, prop_schema in schema["patternProperties"].items():
            if not isinstance(pattern, str):
                raise SchemaValidationError(f"{label}.patternProperties keys must be strings")
            _compile_pattern(pattern, f"{label}.patternProperties[{pattern!r}]")
            if not isinstance(prop_schema, Mapping):
                raise SchemaValidationError(f"{label}.patternProperties entries must map string keys to mappings")
            _validate_schema_document(prop_schema, label=f"{label}.patternProperties[{pattern!r}]")

    if isinstance(schema.get("additionalProperties"), Mapping):
        _validate_schema_document(schema["additionalProperties"], label=f"{label}.additionalProperties")

    if "items" in schema:
        _validate_schema_document(schema["items"], label=f"{label}.items")


def _validate_number_keyword(schema: Mapping[str, Any], *, key: str, label: str) -> None:
    value = schema.get(key)
    if value is not None and not _is_number(value):
        raise SchemaValidationError(f"{label}.{key} must be a number")


def _validate_non_negative_integer_keyword(schema: Mapping[str, Any], *, key: str, label: str) -> None:
    value = schema.get(key)
    if value is None:
        return
    if not _is_integer(value) or value < 0:
        raise SchemaValidationError(f"{label}.{key} must be a non-negative integer")


def _validate_pattern_keyword(schema: Mapping[str, Any], *, key: str, label: str) -> None:
    value = schema.get(key)
    if value is None:
        return
    if not isinstance(value, str):
        raise SchemaValidationError(f"{label}.{key} must be a string")
    _compile_pattern(value, f"{label}.{key}")


def _validate_min_max_pair(
    schema: Mapping[str, Any], *, minimum_key: str, maximum_key: str, label: str
) -> None:
    minimum = schema.get(minimum_key)
    maximum = schema.get(maximum_key)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SchemaValidationError(f"{label}.{minimum_key} must be <= {maximum_key}")


def _compile_pattern(pattern: str, label: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise SchemaValidationError(f"{label} must be a valid regex: {exc}") from exc


def _validate_value(value: Any, schema: Mapping[str, Any], path: str) -> None:
    if "const" in schema and value != schema["const"]:
        raise SchemaValidationError(f"{path} must equal {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path} must be one of {schema['enum']!r}")

    if "allOf" in schema:
        for variant in schema["allOf"]:
            _validate_value(value, variant, path)

    if "anyOf" in schema:
        errors: list[str] = []
        for variant in schema["anyOf"]:
            try:
                _validate_value(value, variant, path)
                break
            except SchemaValidationError as exc:
                errors.append(exc.message)
        else:
            raise SchemaValidationError(f"{path} failed anyOf validation: {errors[-1] if errors else 'no variants'}")

    if "oneOf" in schema:
        matches = 0
        last_error = "no variants"
        for variant in schema["oneOf"]:
            try:
                _validate_value(value, variant, path)
                matches += 1
            except SchemaValidationError as exc:
                last_error = exc.message
        if matches != 1:
            raise SchemaValidationError(f"{path} must match exactly one variant: {last_error}")

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
        if not any(_matches_type(value, item) for item in allowed_types):
            raise SchemaValidationError(f"{path} must be of type {allowed_types!r}")

    if isinstance(value, str):
        _validate_string(value, schema, path)
    elif _is_integer(value):
        _validate_number(value, schema, path)
    elif _is_number(value):
        _validate_number(value, schema, path)
    elif isinstance(value, list):
        _validate_array(value, schema, path)
    elif isinstance(value, Mapping):
        _validate_object(value, schema, path)


def _validate_string(value: str, schema: Mapping[str, Any], path: str) -> None:
    min_length = schema.get("minLength")
    if min_length is not None and len(value) < min_length:
        raise SchemaValidationError(f"{path} must have length >= {min_length}")

    max_length = schema.get("maxLength")
    if max_length is not None and len(value) > max_length:
        raise SchemaValidationError(f"{path} must have length <= {max_length}")

    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, value) is None:
        raise SchemaValidationError(f"{path} must match pattern {pattern!r}")


def _validate_number(value: int | float, schema: Mapping[str, Any], path: str) -> None:
    minimum = schema.get("minimum")
    if minimum is not None and value < minimum:
        raise SchemaValidationError(f"{path} must be >= {minimum}")

    maximum = schema.get("maximum")
    if maximum is not None and value > maximum:
        raise SchemaValidationError(f"{path} must be <= {maximum}")


def _validate_array(value: list[Any], schema: Mapping[str, Any], path: str) -> None:
    min_items = schema.get("minItems")
    if min_items is not None and len(value) < min_items:
        raise SchemaValidationError(f"{path} must have at least {min_items} items")

    max_items = schema.get("maxItems")
    if max_items is not None and len(value) > max_items:
        raise SchemaValidationError(f"{path} must have at most {max_items} items")

    items_schema = schema.get("items")
    if isinstance(items_schema, Mapping):
        for index, item in enumerate(value):
            _validate_value(item, items_schema, f"{path}[{index}]")


def _validate_object(value: Mapping[str, Any], schema: Mapping[str, Any], path: str) -> None:
    required = schema.get("required", [])
    for field in required:
        if field not in value:
            raise SchemaValidationError(f"{path}.{field} is required")

    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for key, item in value.items():
        child_path = f"{path}.{key}"
        if key in properties:
            _validate_value(item, properties[key], child_path)
            continue
        if additional is False:
            raise SchemaValidationError(f"{child_path} is not allowed")
        if isinstance(additional, Mapping):
            _validate_value(item, additional, child_path)


def _matches_type(value: Any, schema_type: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": _is_number(value),
        "integer": _is_integer(value),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }[schema_type]


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return True
