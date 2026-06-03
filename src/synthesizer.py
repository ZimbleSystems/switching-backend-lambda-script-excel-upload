"""Convert per-page parsed dicts into orchestrator-ready records (entity-shaped)."""
from __future__ import annotations

from typing import Any, Dict, List, Union

from .nested_builders import (
    block_flag_to_bool,
    build_address,
    build_channels,
    build_emails,
    build_instrument_criteria_extras,
    build_merchant_chain_list,
    build_merchant_criteria_extras,
    build_merchant_tables,
    build_phones,
    build_social_media,
    build_store_chain_list,
    build_store_tables,
)
from defaults import auto_criteria_id, auto_id, coerce_int, fill_missing_required
from schemas import SHEETS
from transformers import transform_all


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _str_or_none(v: Any) -> Any:
    if _is_blank(v):
        return None
    return str(v).strip() if not isinstance(v, (int, float, bool)) else v


def _criteria_id(*candidates: Any) -> int:
    """Resolve criteria id from Excel values; must be int in Mongo (Java Integer)."""
    for value in candidates:
        parsed = coerce_int(value)
        if parsed is not None:
            return parsed
    return auto_criteria_id()


def _s(v: Any) -> Any:
    if _is_blank(v):
        return None
    return str(v).strip()


def _first_table_fk(page: Dict[str, Any]) -> tuple:
    for type_, key in (
        ("IVA", "iva_table_id"),
        ("SKU", "sku_table_id"),
        ("COUPON", "coupon_table_id"),
        ("CONNECTOR", "connector_table_id"),
    ):
        v = page.get(key)
        if not _is_blank(v):
            return type_, str(v)
    return None, None


def _ensure_demographic_id(page: Dict[str, Any], key: str, prefix: str) -> str:
    if _is_blank(page.get(key)):
        page[key] = auto_id(prefix)
    return str(page[key]).strip()


def _page_has_entity(page: Dict[str, Any], anchor_key: str) -> bool:
    return not _is_blank(page.get(anchor_key))


def _build_demographic(page: Dict[str, Any], demographic_id: str, demographic_type: str) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "demographic_id": _str_or_none(demographic_id),
        "demographic_type": demographic_type,
    }
    addresses = build_address(page)
    if addresses:
        rec["addresses"] = addresses
    phones = build_phones(page)
    if phones:
        rec["phone_numbers"] = phones
    emails = build_emails(page)
    if emails:
        rec["emails"] = emails
    sm = build_social_media(page)
    if sm:
        rec["social_media"] = sm
    return rec


def _empty_output() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "demographic": [],
        "merchant_criteria": [],
        "instrument_criteria": [],
        "connector": [],
        "connector_table": [],
        "chain": [],
        "merchant": [],
        "store": [],
    }


def _synthesize_one(parsed: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out = _empty_output()

    merchant_pg = parsed.get("merchant", {})
    store_pg = parsed.get("store", {})
    chain_pg = parsed.get("chain", {})
    mcrit_pg = parsed.get("merchant_criteria", {})
    icrit_pg = parsed.get("instrument_criteria", {})

    if _is_blank(merchant_pg.get("merchant_org")):
        merchant_pg["merchant_org"] = 6032
    org_default = merchant_pg.get("merchant_org", 6032)
    chain_status = transform_all({"chain_status": chain_pg.get("chain_status")}).get("chain_status", "A")
    merchant_crit_id: int | None = None
    instrument_crit_id: int | None = None

    if _page_has_entity(merchant_pg, "merchant_id"):
        mid = _ensure_demographic_id(merchant_pg, "merchant_demographics_id", "dm")
        out["demographic"].append(_build_demographic(merchant_pg, mid, "M"))
    if _page_has_entity(store_pg, "store_id"):
        sid = _ensure_demographic_id(store_pg, "store_demographics_id", "ds")
        out["demographic"].append(_build_demographic(store_pg, sid, "S"))
    if _page_has_entity(chain_pg, "chain_id"):
        cid = _ensure_demographic_id(chain_pg, "chain_demographics_id", "dc")
        out["demographic"].append(_build_demographic(chain_pg, cid, "C"))

    if _page_has_entity(merchant_pg, "merchant_id") or not _is_blank(mcrit_pg.get("criteria")):
        merchant_crit_id = _criteria_id(
            mcrit_pg.get("criteria"),
            merchant_pg.get("criteria_table_id"),
        )
        mcrit_pg["criteria"] = merchant_crit_id
        description = mcrit_pg.get("criteria_description")
        if _is_blank(description):
            description = "AUTO_CRITERIA"
        base = transform_all({
            "criteria": merchant_crit_id,
            "description": description,
            "block_installments": mcrit_pg.get("block_installments"),
            "block_cashback": mcrit_pg.get("block_cashback"),
            "block_international": mcrit_pg.get("block_international"),
        })
        for bk in ("block_installments", "block_cashback", "block_international"):
            base[bk] = block_flag_to_bool(base.get(bk) if not _is_blank(mcrit_pg.get(bk)) else "N")
        base.update(build_merchant_criteria_extras(mcrit_pg))
        fill_missing_required(base, SHEETS["merchant_criteria"]["schema"])
        out["merchant_criteria"].append(base)

    if _page_has_entity(merchant_pg, "merchant_id") or not _is_blank(icrit_pg.get("criteria")):
        instrument_crit_id = _criteria_id(
            icrit_pg.get("criteria"),
            store_pg.get("instrument_criteria_table_id"),
            merchant_pg.get("instrument_criteria_table_id"),
        )
        icrit_pg["criteria"] = instrument_crit_id
        description = icrit_pg.get("description")
        if _is_blank(description):
            description = "AUTO_INSTRUMENT_CRITERIA"
        base = transform_all({
            "criteria_id": instrument_crit_id,
            "description": description,
        })
        base.update(build_instrument_criteria_extras(icrit_pg))
        fill_missing_required(base, SHEETS["instrument_criteria"]["schema"])
        out["instrument_criteria"].append(base)

    if _page_has_entity(chain_pg, "chain_id"):
        if _is_blank(chain_pg.get("chain_id")):
            chain_pg["chain_id"] = auto_id("ch")
        if _is_blank(chain_pg.get("chain_name")):
            chain_pg["chain_name"] = "AUTO_CHAIN"
        if _is_blank(chain_pg.get("chain_governing_state")):
            chain_pg["chain_governing_state"] = "NA"
        rec = transform_all({
            "chain_id": _str_or_none(chain_pg.get("chain_id")),
            "chain_org": org_default,
            "chain_name": chain_pg.get("chain_name"),
            "chain_status": chain_pg.get("chain_status") or "A",
            "chain_governing_state": chain_pg.get("chain_governing_state"),
            "chain_demographics_id": _str_or_none(chain_pg.get("chain_demographics_id")),
        })
        fill_missing_required(rec, SHEETS["chain"]["schema"])
        out["chain"].append(rec)

    if _page_has_entity(merchant_pg, "merchant_id"):
        if _is_blank(merchant_pg.get("merchant_id")):
            merchant_pg["merchant_id"] = auto_id("m")
        if _is_blank(merchant_pg.get("merchant_name")):
            merchant_pg["merchant_name"] = "AUTO_MERCHANT"
        if _is_blank(merchant_pg.get("merchant_governing_state")):
            merchant_pg["merchant_governing_state"] = "NA"
        ttype, tid = _first_table_fk(merchant_pg)
        chain_id = merchant_pg.get("chain_id_link")
        rec = transform_all({
            "merchant_id": _str_or_none(merchant_pg.get("merchant_id")),
            "merchant_org": merchant_pg.get("merchant_org"),
            "merchant_name": merchant_pg.get("merchant_name"),
            "merchant_status": merchant_pg.get("merchant_status"),
            "merchant_governing_state": merchant_pg.get("merchant_governing_state"),
            "merchant_demographics_id": _str_or_none(merchant_pg.get("merchant_demographics_id")),
            "criteria": merchant_crit_id or coerce_int(merchant_pg.get("criteria_table_id")),
            "instrument_criteria": instrument_crit_id or coerce_int(
                merchant_pg.get("instrument_criteria_table_id"),
            ),
            "merchant_chain_id": _str_or_none(chain_id),
            "merchant_table_type": ttype,
            "merchant_table_id": tid,
            "time_zone": _s(merchant_pg.get("merchant_time_zone")),
        })
        tables = build_merchant_tables(merchant_pg)
        if tables:
            rec["merchant_tables"] = tables
        chains = build_merchant_chain_list(chain_id, chain_name="NA", status=chain_status or "A")
        if chains:
            rec["merchant_chain_list"] = chains
        channels = build_channels(merchant_pg)
        if channels:
            rec["channels_and_identifiers"] = channels
        fill_missing_required(rec, SHEETS["merchant"]["schema"])
        out["merchant"].append(rec)

    if _page_has_entity(store_pg, "store_id"):
        if _is_blank(store_pg.get("store_id")):
            store_pg["store_id"] = auto_id("s")
        if _is_blank(store_pg.get("store_name")):
            store_pg["store_name"] = "AUTO_STORE"
        if _is_blank(store_pg.get("store_governing_state")):
            store_pg["store_governing_state"] = "NA"
        if _is_blank(store_pg.get("store_merchant_id")):
            store_pg["store_merchant_id"] = merchant_pg.get("merchant_id") or auto_id("m")
        ttype, tid = _first_table_fk(store_pg)
        chain_id = store_pg.get("chain_id_link")
        rec = transform_all({
            "store_id": _str_or_none(store_pg.get("store_id")),
            "store_org": org_default,
            "store_name": store_pg.get("store_name"),
            "store_status": store_pg.get("store_status"),
            "store_governing_state": store_pg.get("store_governing_state"),
            "store_merchant_id": _str_or_none(store_pg.get("store_merchant_id")),
            "store_demographics_id": _str_or_none(store_pg.get("store_demographics_id")),
            "criteria": merchant_crit_id or coerce_int(store_pg.get("merchant_criteria_table_id")),
            "instrument_criteria": instrument_crit_id or coerce_int(
                store_pg.get("instrument_criteria_table_id"),
            ),
            "store_chain_id": _str_or_none(chain_id),
            "store_table_type": ttype,
            "store_table_id": tid,
        })
        tables = build_store_tables(store_pg)
        if tables:
            rec["store_table_list"] = tables
        chains = build_store_chain_list(chain_id, status=chain_status or "A")
        if chains:
            rec["store_chain_list"] = chains
        channels = build_channels(store_pg)
        if channels:
            rec["channels_and_identifiers"] = channels
        if not _is_blank(store_pg.get("printer")):
            rec["store_printer_terminals"] = _str_or_none(store_pg.get("printer"))
        if not _is_blank(store_pg.get("terminal_information")):
            rec["store_pos_terminals"] = [{"terminal_id": _str_or_none(store_pg.get("terminal_information"))}]
        fill_missing_required(rec, SHEETS["store"]["schema"])
        out["store"].append(rec)

    return out


def synthesize(
    parsed_workbooks: Union[Dict[str, Dict[str, Any]], List[Dict[str, Dict[str, Any]]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build orchestrator-ready records from one or more parsed worksheet bundles.

    Each worksheet tab is processed independently (its own merchant/store/chain set).
    """
    if isinstance(parsed_workbooks, dict):
        pages_list = [parsed_workbooks]
    else:
        pages_list = parsed_workbooks

    merged = _empty_output()
    for pages in pages_list:
        one = _synthesize_one(pages)
        for sheet, rows in one.items():
            merged[sheet].extend(rows)
    return merged
