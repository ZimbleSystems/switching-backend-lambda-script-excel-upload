"""Placeholder values for missing required fields (ingest continues instead of failing)."""
from __future__ import annotations

import uuid
from typing import Any, Dict


def auto_id(prefix: str = "auto") -> str:
    """Short unique id, similar spirit to demographic-services UUID (no hyphens)."""
    return f"{prefix}{uuid.uuid4().hex[:12]}".lower()


def normalize_demographic_id(value: Any) -> str:
    """Demographic API persists ids lowercased; align Excel FK refs and lookups."""
    if value is None:
        return ""
    return str(value).strip().lower()


def auto_criteria_id() -> int:
    """Numeric criteria id (MerchantCriteria / InstrumentCriteria use Integer)."""
    return (uuid.uuid4().int % 899_999) + 100_001


def coerce_int(value: Any) -> int | None:
    """Parse Excel / string values into int for Mongo Integer fields."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        return int(float(text))
    except ValueError:
        return None


def default_for_required(col: str, rule: Dict[str, Any]) -> Any:
    """Pick a valid dummy value for a required schema field that was left blank."""
    if "default" in rule:
        return rule["default"]

    if "enum" in rule and rule["enum"]:
        return rule["enum"][0]

    field_type = rule.get("type", "str")
    if field_type == "int":
        if col.endswith("_org"):
            return 6032
        return 0
    if field_type == "bool":
        return False

    # String placeholders by field name
    if col in ("merchant_name", "store_name", "chain_name"):
        return "AUTO_NAME"
    if col in (
        "merchant_governing_state",
        "store_governing_state",
        "chain_governing_state",
    ):
        return "NA"
    if col in ("criteria_description", "description"):
        return "AUTO_DESCRIPTION"
    if col == "demographic_type":
        return "M"
    if col.endswith("_id") or col in ("merchant_id", "store_id", "chain_id"):
        prefix = col.replace("_id", "").replace("_", "")[:4] or "id"
        return auto_id(prefix)

    return "NA"


def fill_missing_required(row: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> None:
    """Mutate row in place: set dummy values for blank required columns."""
    for col, rule in schema.items():
        if not rule.get("required", False):
            continue
        val = row.get(col)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            row[col] = default_for_required(col, rule)
