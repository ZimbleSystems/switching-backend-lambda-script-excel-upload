"""Map Excel display values to canonical codes (config_metadata_maps.py, strict)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config_metadata_maps import map_element_value

# Excel field name -> application.yml metadata element
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

# Criteria ie_* on blocking rows use I|E|N (include/exclude/none), not international_applied.
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


def map_field(field: str, value: Any) -> Any:
    """Map one Excel field to canonical metadata code only (None if unknown)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    element = _metadata_element(field)
    if element:
        return map_element_value(element, value, strict=True)

    f = field.lower()
    if (
        f.startswith("block_")
        or field
        in (
            "purchase_international_type",
            "entry_international_type",
            "limit_international_type",
        )
    ):
        mapped = _try_map(value, BLOCK_MAP)
        return mapped if mapped in ("I", "E", "N") else None
    if f in ("check_for_expiry", "validate_instrument"):
        return _try_map(value, BOOLEAN_MAP)
    return value


def _try_map(value: Any, mapping: Dict[str, Any]) -> Any:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return mapping.get(s.lower(), value)


def transform(field: str, value: Any) -> Any:
    return map_field(field, value)


def transform_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Apply strict metadata mapping to every scalar field on a parsed page."""
    out: Dict[str, Any] = {}
    for key, val in page.items():
        if val is None:
            out[key] = None
        elif isinstance(val, (list, dict)):
            out[key] = val
        else:
            out[key] = map_field(key, val)
    return out


def transform_workbook_pages(pages: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {name: transform_page(page) for name, page in pages.items()}


def transform_all(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: map_field(k, v) for k, v in record.items()}


def strict_transform_demographic(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Re-apply metadata codes on nested demographic BSON (phones, emails, addresses)."""
    for phone in doc.get("phone_numbers") or []:
        if not isinstance(phone, dict):
            continue
        if phone.get("phone_type") is not None:
            phone["phone_type"] = map_element_value("phone_type", phone["phone_type"], strict=True)
        if phone.get("phone_country") is not None:
            phone["phone_country"] = map_element_value(
                "phone_country", phone["phone_country"], strict=True
            )

    for email in doc.get("emails") or []:
        if not isinstance(email, dict):
            continue
        if email.get("email_type") is not None:
            email["email_type"] = map_element_value("email_type", email["email_type"], strict=True)

    for addr in doc.get("addresses") or []:
        if not isinstance(addr, dict):
            continue
        if addr.get("address_type") is not None:
            addr["address_type"] = map_element_value(
                "address_type", addr["address_type"], strict=True
            )
        for block in addr.get("address_blocks") or []:
            if not isinstance(block, dict):
                continue
            if block.get("state"):
                block["state"] = map_element_value("state", block["state"], strict=True)
            if block.get("language"):
                block["language"] = map_element_value("language", block["language"], strict=True)
            if block.get("country_code"):
                block["country_code"] = map_element_value(
                    "country_code_all", block["country_code"], strict=True
                )
        loc = addr.get("location")
        if isinstance(loc, dict):
            if loc.get("latitude_direction"):
                loc["latitude_direction"] = map_element_value(
                    "latitude_direction", loc["latitude_direction"], strict=True
                )
            if loc.get("longitude_direction"):
                loc["longitude_direction"] = map_element_value(
                    "longitude_direction", loc["longitude_direction"], strict=True
                )
        loc_ids = addr.get("location_identifiers")
        if isinstance(loc_ids, dict):
            remapped: Dict[str, Any] = {}
            for key, val in loc_ids.items():
                mk = map_element_value("location_identifiers", key, strict=True)
                if mk:
                    remapped[mk] = val
            addr["location_identifiers"] = remapped

    return doc


def strict_transform_blocking_values(blocks: List[Dict[str, Any]], value_field: str) -> None:
    """Map blocking value codes (purchase_type, entry_type, limit_type) in place."""
    element = FIELD_TO_ELEMENT.get(value_field)
    if not element:
        return
    for item in blocks:
        if isinstance(item, dict) and item.get("value") is not None:
            item["value"] = map_element_value(element, item["value"], strict=True)
