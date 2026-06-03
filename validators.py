"""Generic field-level validator driven by schemas.py."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from defaults import default_for_required
from errors import ValidationError


_TYPE_COERCERS = {
    "str": lambda v: str(v).strip(),
    "int": lambda v: int(float(v)) if isinstance(v, str) and v.strip() != "" else int(v),
    "float": lambda v: float(v),
    "bool": lambda v: str(v).strip().lower() in ("1", "true", "yes", "y", "t"),
    "list": lambda v: v if isinstance(v, list) else [v],
    "dict": lambda v: v,
}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        # pandas NaN check without importing pandas
        return value != value  # noqa: PLR0124
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _coerce(value: Any, target_type: str, field: str) -> Any:
    try:
        return _TYPE_COERCERS[target_type](value)
    except Exception as exc:
        raise ValidationError(field, f"cannot convert to {target_type}: {exc}") from exc


def validate_row(
    row: Dict[str, Any],
    schema: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[ValidationError]]:
    """
    Validate one row against a schema.

    Returns (cleaned_doc_using_bson_keys, errors).
    """
    errors: List[ValidationError] = []
    cleaned: Dict[str, Any] = {}

    for col, rule in schema.items():
        bson_key = rule["bson"]
        raw_value = row.get(col)

        if _is_blank(raw_value):
            if rule.get("required", False):
                raw_value = default_for_required(col, rule)
            else:
                continue

        try:
            value = _coerce(raw_value, rule["type"], col)
        except ValidationError:
            if rule.get("type") == "bool":
                value = False
            elif "enum" in rule and rule["enum"]:
                value = rule["enum"][0]
            else:
                value = default_for_required(col, rule)

        if "enum" in rule and value not in rule["enum"]:
            value = rule["enum"][0]

        if "pattern" in rule:
            if not re.match(rule["pattern"], str(value)):
                errors.append(
                    ValidationError(col, f"does not match pattern {rule['pattern']}")
                )
                continue

        if rule["type"] in ("int", "float"):
            if "min" in rule and value < rule["min"]:
                errors.append(ValidationError(col, f"must be >= {rule['min']}"))
                continue
            if "max" in rule and value > rule["max"]:
                errors.append(ValidationError(col, f"must be <= {rule['max']}"))
                continue
        elif rule["type"] == "str":
            length = len(value)
            if "min" in rule and length < rule["min"]:
                errors.append(
                    ValidationError(col, f"length must be >= {rule['min']} (got {length})")
                )
                continue
            if "max" in rule and length > rule["max"]:
                errors.append(
                    ValidationError(col, f"length must be <= {rule['max']} (got {length})")
                )
                continue

        cleaned[bson_key] = value

    return cleaned, errors
