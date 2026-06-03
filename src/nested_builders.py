"""Build nested Mongo documents matching Quarkus entity BSON shapes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from transformers import transform


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _s(v: Any) -> Optional[str]:
    if _blank(v):
        return None
    return str(v).strip()


def _address_lines(raw: Any) -> List[str]:
    """address_line in Mongo is List<String> (AddressBlock.addressLineList)."""
    if _blank(raw):
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if not _blank(x)]
    text = str(raw).strip()
    lines: List[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        for part in line.split(";"):
            part = part.strip()
            if part:
                lines.append(part)
    return lines


def _ie_and_list(raw: Any) -> Tuple[str, List[str]]:
    """Parse 'Include: US,MX' or plain 'US,MX' -> (I|E|N, [codes])."""
    if _blank(raw):
        return "N", []
    text = str(raw).strip()
    ie = "N"
    body = text
    lower = text.lower()
    if lower.startswith("include"):
        ie, body = "I", text.split(":", 1)[-1]
    elif lower.startswith("exclude"):
        ie, body = "E", text.split(":", 1)[-1]
    vals = [p.strip() for p in body.replace(";", ",").split(",") if p.strip()]
    return ie, vals


def _blocking_pair(intl: Any, value: Any) -> Optional[Dict[str, str]]:
    if _blank(value):
        return None
    ie = "N"
    if not _blank(intl):
        ie = transform("block_x", str(intl)) if isinstance(transform("x", str(intl)), str) else "N"
        if ie not in ("I", "E", "N"):
            ie = "N"
    return {"international": ie, "value": str(value).strip()}


def block_flag_to_bool(v: Any) -> bool:
    if v in (True, False):
        return bool(v)
    if _blank(v):
        return False
    s = str(v).upper()
    return s in ("E", "I", "YES", "Y", "TRUE", "1")


def build_address(page: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if _blank(page.get("address_line1")) and _blank(page.get("city")):
        return None
    block: Dict[str, Any] = {}
    address_lines = _address_lines(page.get("address_line1"))
    if address_lines:
        block["address_line"] = address_lines
    if not _blank(page.get("city")):
        block["city"] = _s(page.get("city"))
    if not _blank(page.get("state")):
        block["state"] = _s(page.get("state"))
    if not _blank(page.get("postal_code")):
        block["postal_code"] = _s(page.get("postal_code"))
    if not _blank(page.get("country")):
        block["country_code"] = _s(page.get("country"))
    if not _blank(page.get("language")):
        block["language"] = _s(page.get("language"))

    loc: Dict[str, Any] = {}
    if not _blank(page.get("latitude")):
        loc["latitude"] = _s(page.get("latitude"))
    if not _blank(page.get("longitude")):
        loc["longitude"] = _s(page.get("longitude"))
    if not _blank(page.get("latitude_direction")):
        loc["latitude_direction"] = _s(page.get("latitude_direction"))
    if not _blank(page.get("longitude_direction")):
        loc["longitude_direction"] = _s(page.get("longitude_direction"))

    loc_ids = {}
    if not _blank(page.get("location_identifier_type")):
        loc_ids[_s(page.get("location_identifier_type"))] = _s(page.get("location_identifier_value")) or ""

    addr: Dict[str, Any] = {"primary": True, "address_blocks": [block]}
    at = transform("address_type", page.get("address_type"))
    if at:
        addr["address_type"] = at
    if loc:
        addr["location"] = loc
    if loc_ids:
        addr["location_identifiers"] = loc_ids
    return [addr]


def build_phones(page: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if _blank(page.get("phone_number")):
        return None
    return [{
        "phone_type": transform("phone_type", page.get("phone_type")),
        "phone_country": _s(page.get("phone_country")),
        "phone": _s(page.get("phone_number")),
        "primary": True,
    }]


def build_emails(page: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if _blank(page.get("email")):
        return None
    return [{
        "email_type": transform("email_type", page.get("email_type")),
        "email": _s(page.get("email")),
        "primary": True,
    }]


def build_social_media(page: Dict[str, Any]) -> Optional[Dict[str, str]]:
    sm = {}
    for key, bson in (
        ("facebook_url", "facebook_id"),
        ("instagram_url", "instagram_id"),
        ("twitter_url", "x_id"),
        ("google_id", "google_id"),
    ):
        v = _s(page.get(key))
        if v:
            sm[bson] = v
    return sm or None


def build_channels(page: Dict[str, Any]) -> Optional[List[Dict[str, str]]]:
    ch = _s(page.get("channel_name"))
    ident = _s(page.get("channel_identifier"))
    if not ch and not ident:
        return None
    return [{"channel": ch or "", "identifier": ident or ""}]


def build_merchant_tables(page: Dict[str, Any]) -> List[Dict[str, str]]:
    out = []
    for type_, key in (
        ("IVA", "iva_table_id"),
        ("SKU", "sku_table_id"),
        ("COUPON", "coupon_table_id"),
        ("CONNECTOR", "connector_table_id"),
    ):
        v = page.get(key)
        if not _blank(v):
            out.append({"merchant_table_type": type_, "merchant_table_id": str(v)})
    return out


def build_store_tables(page: Dict[str, Any]) -> List[Dict[str, str]]:
    out = []
    for type_, key in (
        ("IVA", "iva_table_id"),
        ("SKU", "sku_table_id"),
        ("COUPON", "coupon_table_id"),
        ("CONNECTOR", "connector_table_id"),
    ):
        v = page.get(key)
        if not _blank(v):
            out.append({"store_table_type": type_, "store_table_id": str(v)})
    return out


def build_merchant_chain_list(chain_id: Any, chain_name: str = "NA", status: str = "A") -> Optional[List[Dict[str, str]]]:
    if _blank(chain_id):
        return None
    return [{
        "merchant_chain_id": str(chain_id),
        "merchant_chain_name": chain_name,
        "merchant_chain_status": status,
    }]


def build_store_chain_list(chain_id: Any, chain_name: str = "NA", status: str = "A") -> Optional[List[Dict[str, str]]]:
    if _blank(chain_id):
        return None
    return [{
        "store_chain_id": str(chain_id),
        "store_chain_name": chain_name,
        "store_chain_status": status,
    }]


def build_merchant_criteria_extras(page: Dict[str, Any]) -> Dict[str, Any]:
    ie_c, countries = _ie_and_list(page.get("countries_list"))
    ie_s, states = _ie_and_list(page.get("states_list"))
    ie_cur, currencies = _ie_and_list(page.get("currencies_list"))
    ie_mcc, _mcc_vals = _ie_and_list(page.get("mcc_list"))

    purchase = _blocking_pair(page.get("purchase_international_type"), page.get("purchase_type"))
    entry = _blocking_pair(page.get("entry_international_type"), page.get("entry_type"))
    limit = _blocking_pair(page.get("limit_international_type"), page.get("limit_type"))

    tx_map = {}
    if not _blank(page.get("tx_limit_type")):
        tx_map[str(page.get("tx_limit_type"))] = {
            "limit_type": _s(page.get("tx_limit_type")),
            "transaction_amt": page.get("tx_amount"),
            "transaction_nbr": page.get("tx_limit"),
        }

    return {
        "ie_blocked_countries": ie_c,
        "blocked_countries": countries,
        "ie_block_states": ie_s,
        "blocked_states": states,
        "ie_blocked_currency": ie_cur,
        "blocked_currencies": currencies,
        "ie_block_mcc": ie_mcc,
        "ie_block_purchase_type": purchase["international"] if purchase else "N",
        "blocked_purchase_types": [purchase] if purchase else [],
        "ie_block_entry_type": entry["international"] if entry else "N",
        "blocked_entry_types": [entry] if entry else [],
        "ie_block_limit_type": limit["international"] if limit else "N",
        "block_limit_types": [limit] if limit else [],
        "ie_block_transaction_type": "N",
        "blocked_transaction_types": [],
        "ie_block_terminal_type": "N",
        "blocked_terminal_types": [],
        "transaction_limits_map": tx_map,
    }


def build_instrument_criteria_extras(page: Dict[str, Any]) -> Dict[str, Any]:
    timed = []
    if not _blank(page.get("timed_limit_type")):
        timed.append({
            "limit_type": _s(page.get("timed_limit_type")),
            "transaction_amt": page.get("timed_tx_amount"),
            "transaction_count": page.get("timed_tx_count"),
            "time_limit": page.get("timed_time_limit"),
            "time_unit": transform("timed_time_unit", page.get("timed_time_unit")),
        })
    daily = []
    if not _blank(page.get("daily_limit_type")):
        daily.append({
            "limit_type": _s(page.get("daily_limit_type")),
            "transaction_amt": page.get("daily_tx_amount"),
            "transaction_count": page.get("daily_tx_count"),
        })
    susp = []
    if not _blank(page.get("susp_channel")) or not _blank(page.get("susp_no_declines")):
        susp.append({
            "channel": _s(page.get("susp_channel")),
            "response_code": _s(page.get("susp_response_code")),
            "no_declines": page.get("susp_no_declines"),
            "tracking_timeframe": page.get("susp_tracking_duration"),
            "tracking_timeunit": transform("susp_tracking_time_unit", page.get("susp_tracking_time_unit")),
            "temp_perm": transform("susp_type", page.get("susp_type")),
            "susp_duration": page.get("susp_duration"),
            "susp_timeunit": transform("susp_time_unit", page.get("susp_time_unit")),
        })
    out: Dict[str, Any] = {}
    if timed:
        out["timed_transaction_limits"] = timed
    if daily:
        out["transaction_limits"] = daily
    if susp:
        out["susp_criterias"] = susp
    if not _blank(page.get("check_for_expiry")):
        out["check_expiry"] = transform("check_for_expiry", page.get("check_for_expiry"))
    if not _blank(page.get("validate_instrument")):
        out["validate_instr_id"] = transform("validate_instrument", page.get("validate_instrument"))
    return out
