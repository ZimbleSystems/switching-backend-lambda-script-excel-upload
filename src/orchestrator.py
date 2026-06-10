"""
Dependency-aware ingestion orchestrator.

Processes each Excel worksheet tab as a bundle in tab order. Within a bundle,
sheets run in `order` ascending (demographic → criteria → chain → merchant → store).

For each row:
  1. validate field-level rules
  2. skip duplicate primary keys already written in this workbook run
  3. cascade-skip linked demographics when parent merchant/chain is duplicate
  4. resolve parent IDs (skip if parent missing)
  5. upsert into Mongo
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Union

from api_client import AlreadyPresentError, ApiGatewayClient
from schemas import SHEETS
from defaults import coerce_int, fill_missing_required
from validators import validate_row

_INGEST_META_KEYS = frozenset({
    "_source_worksheet",
    "_linked_merchant_id",
    "_linked_chain_id",
    "_no_merchant_demographic",
})


def _normalize_criteria_fields(cleaned: Dict[str, Any]) -> None:
    """Criteria FKs must be Integer in Mongo; drop blank or non-numeric values."""
    for key in ("criteria", "instrument_criteria"):
        if key not in cleaned:
            continue
        if cleaned[key] is None:
            del cleaned[key]
            continue
        parsed = coerce_int(cleaned[key])
        if parsed is not None:
            cleaned[key] = parsed
        else:
            del cleaned[key]


def _sheets_in_order() -> List[str]:
    return [
        name
        for name, _ in sorted(SHEETS.items(), key=lambda kv: kv[1]["order"])
    ]


class IngestReport:
    def __init__(self) -> None:
        self.summary: Dict[str, Dict[str, int]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.created_ids: Dict[str, Set[str]] = {}

    def _error_entry(
        self,
        sheet: str,
        row_idx: int,
        errors: List[str],
        worksheet: str | None = None,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {"sheet": sheet, "row": row_idx, "errors": errors}
        if worksheet:
            entry["worksheet"] = worksheet
        return entry

    def add_success(self, sheet: str, id_value: str) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["success"] += 1
        self.created_ids.setdefault(sheet, set()).add(str(id_value))

    def add_failure(
        self,
        sheet: str,
        row_idx: int,
        errors: List[str],
        worksheet: str | None = None,
    ) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["failed"] += 1
        self.errors.append(self._error_entry(sheet, row_idx, errors, worksheet))

    def add_skip(
        self,
        sheet: str,
        row_idx: int,
        reason: str,
        worksheet: str | None = None,
        *,
        register_id: Any = None,
    ) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["skipped"] += 1
        self.errors.append(self._error_entry(sheet, row_idx, [reason], worksheet))
        if register_id is not None:
            self.created_ids.setdefault(sheet, set()).add(str(register_id))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "errors": self.errors,
            "created_ids": {k: sorted(v) for k, v in self.created_ids.items()},
        }


def _parent_exists(
    client: ApiGatewayClient,
    parent_sheet: str,
    parent_id_value: Any,
    created_ids: Dict[str, Set[str]],
) -> bool:
    parent_cfg = SHEETS[parent_sheet]
    if str(parent_id_value) in created_ids.get(parent_sheet, set()):
        return True
    parent_id_field_bson = parent_cfg["schema"][parent_cfg["id_field"]]["bson"]
    return client.exists(parent_sheet, parent_id_field_bson, parent_id_value)


def _row_worksheet(row: Dict[str, Any]) -> str | None:
    ws = row.get("_source_worksheet")
    return str(ws) if ws else None


def _should_skip_duplicate_pk(
    sheet: str,
    id_value: Any,
    created_ids: Dict[str, Set[str]],
) -> bool:
    return str(id_value) in created_ids.get(sheet, set())


def _cascade_skip_demographic(row: Dict[str, Any], created_ids: Dict[str, Set[str]]) -> str | None:
    """Return skip reason if this demographic row should not be written."""
    demo_type = row.get("demographic_type")
    if demo_type == "M":
        linked = row.get("_linked_merchant_id")
        if linked and str(linked) in created_ids.get("merchant", set()):
            return (
                f"merchant demographic skipped: merchant_id={linked!r} "
                "already persisted earlier in this workbook"
            )
    if demo_type == "C":
        linked = row.get("_linked_chain_id")
        if linked and str(linked) in created_ids.get("chain", set()):
            return (
                f"chain demographic skipped: chain_id={linked!r} "
                "already persisted earlier in this workbook"
            )
    return None


def _build_cleaned_document(
    row: Dict[str, Any],
    cfg: Dict[str, Any],
    cleaned: Dict[str, Any],
) -> Dict[str, Any]:
    for k, v in row.items():
        if k in _INGEST_META_KEYS or k in cfg["schema"] or v is None:
            continue
        if k.startswith("_"):
            cleaned[k.lstrip("_")] = v
        else:
            cleaned[k] = v
    return cleaned


def _process_row(
    sheet: str,
    row: Dict[str, Any],
    row_idx: int,
    client: ApiGatewayClient,
    report: IngestReport,
) -> None:
    cfg = SHEETS[sheet]
    worksheet = _row_worksheet(row)

    fill_missing_required(row, cfg["schema"])
    cleaned, errors = validate_row(row, cfg["schema"])
    if errors:
        report.add_failure(sheet, row_idx, [str(e) for e in errors], worksheet)
        return

    cleaned = _build_cleaned_document(row, cfg, cleaned)

    if sheet == "merchant" and row.get("_no_merchant_demographic"):
        cleaned.pop("merchant_demographics_id", None)

    cascade_reason = _cascade_skip_demographic(row, report.created_ids) if sheet == "demographic" else None
    if cascade_reason:
        report.add_skip(sheet, row_idx, cascade_reason, worksheet)
        return

    parent_missing = False
    for fk_col, parent_sheet in cfg["parents"].items():
        if fk_col == "merchant_demographics_id" and row.get("_no_merchant_demographic"):
            continue
        fk_value = row.get(fk_col)
        if fk_value is None or (isinstance(fk_value, str) and fk_value.strip() == ""):
            if cfg["schema"].get(fk_col, {}).get("required"):
                report.add_failure(
                    sheet,
                    row_idx,
                    [f"{fk_col}: required parent reference missing"],
                    worksheet,
                )
                parent_missing = True
                break
            continue
        if not _parent_exists(client, parent_sheet, fk_value, report.created_ids):
            report.add_skip(
                sheet,
                row_idx,
                f"{fk_col}={fk_value!r} does not exist in "
                f"{parent_sheet} ({SHEETS[parent_sheet]['collection']})",
                worksheet,
            )
            parent_missing = True
            break
    if parent_missing:
        return

    _normalize_criteria_fields(cleaned)

    id_bson = cfg["schema"][cfg["id_field"]]["bson"]
    if cfg["id_field"] in ("criteria", "criteria_id") and (
        id_bson not in cleaned or cleaned[id_bson] is None
    ):
        report.add_skip(
            sheet,
            row_idx,
            f"{cfg['id_field']}: no criteria id in Excel — document not written",
            worksheet,
        )
        return

    try:
        id_value = cleaned[id_bson]
    except KeyError:
        report.add_failure(
            sheet,
            row_idx,
            [f"{cfg['id_field']}: missing id after validation"],
            worksheet,
        )
        return

    if _should_skip_duplicate_pk(sheet, id_value, report.created_ids):
        report.add_skip(
            sheet,
            row_idx,
            f"{cfg['id_field']}={id_value!r} already persisted earlier in this workbook",
            worksheet,
        )
        return

    try:
        client.upsert(sheet, id_bson, cleaned)
        report.add_success(sheet, id_value)
    except AlreadyPresentError as exc:
        report.add_skip(
            sheet,
            row_idx,
            f"{cfg['id_field']}={id_value!r} already present in API — skipped",
            worksheet,
            register_id=id_value,
        )
    except Exception as exc:  # noqa: BLE001
        report.add_failure(sheet, row_idx, [f"api_write_error: {exc}"], worksheet)


def ingest(
    parsed_workbook: Union[Dict[str, List[Dict[str, Any]]], List[Dict[str, List[Dict[str, Any]]]]],
    client: ApiGatewayClient,
) -> Dict[str, Any]:
    """
    Ingest synthesized records.

    Accepts either:
      - a list of per-worksheet bundles (preferred; preserves tab order), or
      - one merged dict (legacy; processes sheets globally by type).
    """
    report = IngestReport()

    if isinstance(parsed_workbook, list):
        for tab_records in parsed_workbook:
            for sheet in _sheets_in_order():
                rows = tab_records.get(sheet, [])
                if not rows:
                    continue
                for idx, row in enumerate(rows, start=2):
                    _process_row(sheet, row, idx, client, report)
    else:
        for sheet in _sheets_in_order():
            rows = parsed_workbook.get(sheet, [])
            if not rows:
                continue
            for idx, row in enumerate(rows, start=2):
                _process_row(sheet, row, idx, client, report)

    return report.to_dict()
