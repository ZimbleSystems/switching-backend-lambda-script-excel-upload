"""Map Excel display values to canonical codes (config_metadata_maps.py)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from config_metadata_maps import map_element_value

# Excel canonical field -> metadata element name (application.yml)
FIELD_TO_ELEMENT: Dict[str, str] = {
    "merchant_governing_state": "state",
    "store_governing_state": "state",
    "chain_governing_state": "state",
    "merchant_status": "entity_status",
    "store_status": "entity_status",
    "chain_status": "entity_status",
    "state": "state",
    "address_type": "address_type",
    "language": "language",
    "email_type": "email_type",
    "phone_type": "phone_type",
    "phone_country": "phone_country",
    "longitude_direction": "longitude_direction",
    "latitude_direction": "latitude_direction",
    "location_identifier_type": "location_identifiers",
    "country": "country_code_all",
    "merchant_time_zone": "time_zone",
    "purchase_type": "purchase_type",
    "entry_type": "entry_type",
    "limit_type": "limit_type",
    "tx_limit_type": "limit_type",
    "timed_limit_type": "limit_type",
    "daily_limit_type": "limit_type",
    "timed_time_unit": "time_unit",
    "susp_tracking_time_unit": "time_unit",
    "susp_time_unit": "time_unit",
    "susp_type": "temp_perm",
}

# Criteria ie_* flags: Include/Exclude/None -> I|E|N (not international_applied).
BLOCK_MAP: Dict[str, str] = {
    "yes": "E",
    "y": "E",
    "true": "E",
    "maybe": "N",
    "no": "N",
    "n": "N",
    "false": "N",
    "include": "I",
    "included": "I",
    "exclude": "E",
    "excluded": "E",
    "none": "N",
    "international": "I",
    "domestic": "E",
    "both": "N",
}

BOOLEAN_MAP: Dict[str, bool] = {
    "yes": True,
    "y": True,
    "true": True,
    "1": True,
    "si": True,
    "sí": True,
    "no": False,
    "n": False,
    "false": False,
    "0": False,
}


def _try_map(value: Any, mapping: Dict[str, Any]) -> Any:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return mapping.get(s.lower(), value)


def _metadata_element(field: str) -> Optional[str]:
    if field in FIELD_TO_ELEMENT:
        return FIELD_TO_ELEMENT[field]
    f = field.lower()
    if f.endswith("_governing_state"):
        return "state"
    if f.endswith("_status"):
        return "entity_status"
    if f.endswith("time_unit") or f == "time_unit":
        return "time_unit"
    return None


def transform(field: str, value: Any) -> Any:
    """Map one field using config-metadata element tables when configured."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    element = _metadata_element(field)
    if element:
        mapped = map_element_value(element, value)
        if mapped is not None and str(mapped).strip():
            return mapped

    f = field.lower()
    if f.startswith("block_"):
        return _try_map(value, BLOCK_MAP)
    if f in ("check_for_expiry", "validate_instrument"):
        return _try_map(value, BOOLEAN_MAP)
    return value


def transform_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Apply metadata mapping to all scalar fields in a parsed Excel page."""
    return {key: transform(key, val) for key, val in page.items()}


def transform_workbook_pages(pages: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {name: transform_page(page) for name, page in pages.items()}


def transform_all(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: transform(k, v) for k, v in record.items()}
