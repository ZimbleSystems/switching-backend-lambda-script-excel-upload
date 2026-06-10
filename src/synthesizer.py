"""Convert per-page parsed dicts into orchestrator-ready records (entity-shaped)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from nested_builders import (
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
from defaults import auto_id, coerce_int, fill_missing_required, normalize_demographic_id
from schemas import SHEETS
from transformers import strict_transform_demographic, transform_all, transform_workbook_pages


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _str_or_none(v: Any) -> str | None:
    """String ids for Mongo (merchant_id, store_id, …); Excel numbers become \"113\"."""
    if _is_blank(v):
        return None
    return str(v).strip()


def _optional_criteria_id(*candidates: Any) -> int | None:
    """Return int criteria id from Excel, or None if not provided."""
    for value in candidates:
        parsed = coerce_int(value)
        if parsed is not None:
            return parsed
    return None


def _resolve_merchant_criteria_id(
    merchant_pg: Dict[str, Any],
    store_pg: Dict[str, Any],
    mcrit_pg: Dict[str, Any],
) -> int | None:
    """One optional merchant criteria id per tab (shared by merchant + store)."""
    return _optional_criteria_id(
        mcrit_pg.get("criteria"),
        merchant_pg.get("criteria_table_id"),
        store_pg.get("merchant_criteria_table_id"),
    )


def _sync_merchant_criteria_refs(
    merchant_crit_id: int,
    merchant_pg: Dict[str, Any],
    store_pg: Dict[str, Any],
    mcrit_pg: Dict[str, Any],
) -> None:
    mcrit_pg["criteria"] = merchant_crit_id
    merchant_pg["criteria_table_id"] = merchant_crit_id
    store_pg["merchant_criteria_table_id"] = merchant_crit_id


def _apply_optional_criteria_fks(
    rec: Dict[str, Any],
    *,
    merchant_crit_id: int | None,
    instrument_crit_id: int | None,
) -> None:
    """Only set criteria FK fields when Excel supplied a numeric id."""
    rec.pop("criteria", None)
    rec.pop("instrument_criteria", None)
    if merchant_crit_id is not None:
        rec["criteria"] = merchant_crit_id
    if instrument_crit_id is not None:
        rec["instrument_criteria"] = instrument_crit_id


def _s(v: Any) -> Any:
    if _is_blank(v):
        return None
    return str(v).strip()


def _is_real_table_id(v: Any) -> bool:
    if _is_blank(v):
        return False
    if _is_placeholder_text(v):
        return False
    lower = str(v).strip().lower()
    return "to be provided" not in lower and "when applicable" not in lower


def _first_table_fk(page: Dict[str, Any]) -> tuple:
    for type_, key in (
        ("IVA", "iva_table_id"),
        ("SKU", "sku_table_id"),
        ("COUPON", "coupon_table_id"),
        ("CONNECTOR", "connector_table_id"),
    ):
        v = page.get(key)
        if _is_real_table_id(v):
            return type_, str(v)
    return None, None


def _ensure_demographic_id(page: Dict[str, Any], key: str, prefix: str) -> str:
    if _is_blank(page.get(key)):
        page[key] = auto_id(prefix)
    normalized = normalize_demographic_id(page[key])
    page[key] = normalized
    return normalized


def _page_has_entity(page: Dict[str, Any], anchor_key: str) -> bool:
    return not _is_blank(page.get(anchor_key))


_INVALID_CHAIN_IDS = frozenset({"0", "00", ""})


def _is_placeholder_text(v: Any) -> bool:
    if _is_blank(v):
        return True
    text = str(v).strip().upper()
    if text in ("NA", "N/A", "NONE", "-"):
        return True
    lower = str(v).strip().lower()
    return lower.startswith("the chain id") or "to be linked" in lower


def _is_real_chain_id(v: Any) -> bool:
    if _is_blank(v):
        return False
    chain_id = str(v).strip()
    return chain_id not in _INVALID_CHAIN_IDS


def _effective_chain_link(page: Dict[str, Any]) -> str | None:
    """Return a real chain id from chain_id_link, or None for template / sentinel values."""
    link = page.get("chain_id_link")
    if _is_placeholder_text(link):
        return None
    if _is_real_chain_id(link):
        return _str_or_none(link)
    return None


def _should_synthesize_chain(chain_pg: Dict[str, Any]) -> bool:
    return _is_real_chain_id(chain_pg.get("chain_id"))


def _should_synthesize_merchant_demographic(merchant_pg: Dict[str, Any]) -> bool:
    """Merchant demographic row only when Excel id is set or merchant page has address/contact."""
    if not _is_blank(merchant_pg.get("merchant_demographics_id")):
        return True
    if not _is_blank(merchant_pg.get("address_line1")):
        return True
    if not _is_blank(merchant_pg.get("city")):
        return True
    if not _is_blank(merchant_pg.get("phone_number")):
        return True
    if not _is_blank(merchant_pg.get("email")):
        return True
    return False


def _stamp_bundle_metadata(
    records: Dict[str, List[Dict[str, Any]]],
    worksheet: Optional[str],
) -> None:
    if not worksheet:
        return
    for rows in records.values():
        for row in rows:
            row["_source_worksheet"] = worksheet


def _build_demographic(page: Dict[str, Any], demographic_id: str, demographic_type: str) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "demographic_id": _str_or_none(normalize_demographic_id(demographic_id)),
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
    rec["social_media"] = build_social_media(page)
    return strict_transform_demographic(rec)


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

    parsed = transform_workbook_pages(parsed)

    merchant_pg = parsed.get("merchant", {})
    store_pg = parsed.get("store", {})
    chain_pg = parsed.get("chain", {})
    mcrit_pg = parsed.get("merchant_criteria", {})
    icrit_pg = parsed.get("instrument_criteria", {})

    if _is_blank(merchant_pg.get("merchant_org")):
        merchant_pg["merchant_org"] = 6032
    org_default = merchant_pg.get("merchant_org", 6032)
    chain_status = transform_all({"chain_status": chain_pg.get("chain_status")}).get("chain_status", "A")
    merchant_crit_id = _resolve_merchant_criteria_id(merchant_pg, store_pg, mcrit_pg)
    instrument_crit_id = _optional_criteria_id(
        icrit_pg.get("criteria_id"),
        icrit_pg.get("criteria"),
        merchant_pg.get("instrument_criteria_table_id"),
        store_pg.get("instrument_criteria_table_id"),
    )
    if merchant_crit_id is not None:
        _sync_merchant_criteria_refs(merchant_crit_id, merchant_pg, store_pg, mcrit_pg)

    merchant_id_for_tab: str | None = None

    merchant_id_val = _str_or_none(merchant_pg.get("merchant_id")) if _page_has_entity(
        merchant_pg, "merchant_id"
    ) else None

    if _page_has_entity(merchant_pg, "merchant_id") and _should_synthesize_merchant_demographic(
        merchant_pg
    ):
        mid = _ensure_demographic_id(merchant_pg, "merchant_demographics_id", "dm")
        demo = _build_demographic(merchant_pg, mid, "M")
        if merchant_id_val:
            demo["_linked_merchant_id"] = merchant_id_val
        out["demographic"].append(demo)
    if _page_has_entity(store_pg, "store_id"):
        sid = _ensure_demographic_id(store_pg, "store_demographics_id", "ds")
        out["demographic"].append(_build_demographic(store_pg, sid, "S"))
    if _should_synthesize_chain(chain_pg):
        demo_id = chain_pg.get("chain_demographics_id")
        if not _is_placeholder_text(demo_id):
            cid = _ensure_demographic_id(chain_pg, "chain_demographics_id", "dc")
            demo = _build_demographic(chain_pg, cid, "C")
            demo["_linked_chain_id"] = _str_or_none(chain_pg.get("chain_id"))
            out["demographic"].append(demo)

    if merchant_crit_id is not None:
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

    if instrument_crit_id is not None:
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

    if _should_synthesize_chain(chain_pg):
        if _is_blank(chain_pg.get("chain_id")):
            chain_pg["chain_id"] = auto_id("ch")
        if _is_blank(chain_pg.get("chain_name")):
            chain_pg["chain_name"] = "AUTO_CHAIN"
        if _is_blank(chain_pg.get("chain_governing_state")):
            chain_pg["chain_governing_state"] = "NA"
        chain_demo_id = chain_pg.get("chain_demographics_id")
        rec = transform_all({
            "chain_id": _str_or_none(chain_pg.get("chain_id")),
            "chain_org": org_default,
            "chain_name": chain_pg.get("chain_name"),
            "chain_status": chain_pg.get("chain_status") or "A",
            "chain_governing_state": chain_pg.get("chain_governing_state"),
            "chain_demographics_id": (
                None
                if _is_placeholder_text(chain_demo_id)
                else _str_or_none(normalize_demographic_id(chain_demo_id))
            ),
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
        chain_id = _effective_chain_link(merchant_pg)
        has_merchant_demo = _should_synthesize_merchant_demographic(merchant_pg)
        merchant_fields: Dict[str, Any] = {
            "merchant_id": _str_or_none(merchant_pg.get("merchant_id")),
            "merchant_org": merchant_pg.get("merchant_org"),
            "merchant_name": merchant_pg.get("merchant_name"),
            "merchant_status": merchant_pg.get("merchant_status"),
            "merchant_governing_state": merchant_pg.get("merchant_governing_state"),
            "merchant_chain_id": chain_id,
            "merchant_table_type": ttype,
            "merchant_table_id": tid,
            "time_zone": _s(merchant_pg.get("merchant_time_zone")),
        }
        if has_merchant_demo:
            merchant_fields["merchant_demographics_id"] = _str_or_none(
                normalize_demographic_id(merchant_pg.get("merchant_demographics_id"))
            )
        rec = transform_all(merchant_fields)
        if not has_merchant_demo:
            rec["_no_merchant_demographic"] = True
        rec["merchant_tables"] = build_merchant_tables(merchant_pg)
        chains = build_merchant_chain_list(chain_id, chain_name="NA", status=chain_status or "A")
        if chains:
            rec["merchant_chain_list"] = chains
        channels = build_channels(merchant_pg)
        if channels:
            rec["channels_and_identifiers"] = channels
        fill_missing_required(rec, SHEETS["merchant"]["schema"])
        out["merchant"].append(rec)
        merchant_id_for_tab = rec.get("merchant_id")

    if _page_has_entity(store_pg, "store_id"):
        if _is_blank(store_pg.get("store_id")):
            store_pg["store_id"] = auto_id("s")
        if _is_blank(store_pg.get("store_name")):
            store_pg["store_name"] = "AUTO_STORE"
        if _is_blank(store_pg.get("store_governing_state")):
            store_pg["store_governing_state"] = "NA"
        if _is_blank(store_pg.get("store_merchant_id")):
            store_pg["store_merchant_id"] = (
                merchant_id_for_tab
                or _str_or_none(merchant_pg.get("merchant_id"))
                or auto_id("m")
            )
        else:
            store_pg["store_merchant_id"] = _str_or_none(store_pg.get("store_merchant_id"))
        ttype, tid = _first_table_fk(store_pg)
        chain_id = _effective_chain_link(store_pg)
        rec = transform_all({
            "store_id": _str_or_none(store_pg.get("store_id")),
            "store_org": org_default,
            "store_name": store_pg.get("store_name"),
            "store_status": store_pg.get("store_status"),
            "store_governing_state": store_pg.get("store_governing_state"),
            "store_merchant_id": _str_or_none(store_pg.get("store_merchant_id")),
            "store_demographics_id": _str_or_none(
                normalize_demographic_id(store_pg.get("store_demographics_id"))
            ),
            "store_chain_id": chain_id,
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
        _apply_optional_criteria_fks(
            rec,
            merchant_crit_id=merchant_crit_id,
            instrument_crit_id=instrument_crit_id,
        )
        fill_missing_required(rec, SHEETS["store"]["schema"])
        out["store"].append(rec)

    return out


def synthesize(
    parsed_workbooks: Union[Dict[str, Dict[str, Any]], List[Dict[str, Dict[str, Any]]]],
    *,
    worksheets: Optional[List[str]] = None,
    per_tab: bool = False,
) -> Union[Dict[str, List[Dict[str, Any]]], List[Dict[str, List[Dict[str, Any]]]]]:
    """
    Build orchestrator-ready records from one or more parsed worksheet bundles.

    Each worksheet tab is processed independently (its own merchant/store/chain set).

    When per_tab=True, returns a list of per-worksheet record dicts (for bundle-order ingest).
    Otherwise returns one merged dict (legacy).
    """
    if isinstance(parsed_workbooks, dict):
        pages_list = [parsed_workbooks]
    else:
        pages_list = parsed_workbooks

    tab_outputs: List[Dict[str, List[Dict[str, Any]]]] = []
    for i, pages in enumerate(pages_list):
        one = _synthesize_one(pages)
        ws = worksheets[i] if worksheets and i < len(worksheets) else None
        _stamp_bundle_metadata(one, ws)
        tab_outputs.append(one)

    if per_tab:
        return tab_outputs

    merged = _empty_output()
    for one in tab_outputs:
        for sheet, rows in one.items():
            merged[sheet].extend(rows)
    return merged
