"""
Dependency-aware ingestion orchestrator.

Processes sheets in `order` ascending. Within an order group, sheets are
independent and processed in registration order. For each row we:

  1. validate field-level rules (validators.validate_row)
  2. resolve parent IDs (skip the row with an explicit error if any
     parent does not exist in Mongo and was not produced in this run)
  3. upsert into the target collection

A structured report is returned so the Lambda can log it / surface it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from .errors import ValidationError
from .mongo_writer import MongoWriter
from .schemas import SHEETS
from .defaults import fill_missing_required
from .validators import validate_row


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

    def add_success(self, sheet: str, id_value: str) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["success"] += 1
        self.created_ids.setdefault(sheet, set()).add(str(id_value))

    def add_failure(self, sheet: str, row_idx: int, errors: List[str]) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["failed"] += 1
        self.errors.append({"sheet": sheet, "row": row_idx, "errors": errors})

    def add_skip(self, sheet: str, row_idx: int, reason: str) -> None:
        self.summary.setdefault(sheet, {"success": 0, "failed": 0, "skipped": 0})
        self.summary[sheet]["skipped"] += 1
        self.errors.append({"sheet": sheet, "row": row_idx, "errors": [reason]})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "errors": self.errors,
            "created_ids": {k: sorted(v) for k, v in self.created_ids.items()},
        }


def _parent_exists(
    writer: MongoWriter,
    parent_sheet: str,
    parent_id_value: Any,
    created_ids: Dict[str, Set[str]],
) -> bool:
    parent_cfg = SHEETS[parent_sheet]
    if str(parent_id_value) in created_ids.get(parent_sheet, set()):
        return True
    parent_id_field_bson = parent_cfg["schema"][parent_cfg["id_field"]]["bson"]
    return writer.exists(parent_cfg["collection"], parent_id_field_bson, parent_id_value)


def ingest(
    parsed_workbook: Dict[str, List[Dict[str, Any]]],
    writer: MongoWriter,
) -> Dict[str, Any]:
    report = IngestReport()

    for sheet in _sheets_in_order():
        rows = parsed_workbook.get(sheet, [])
        cfg = SHEETS[sheet]
        if not rows:
            continue

        for idx, row in enumerate(rows, start=2):  # excel row 1 = header
            fill_missing_required(row, cfg["schema"])
            cleaned, errors = validate_row(row, cfg["schema"])
            if errors:
                report.add_failure(sheet, idx, [str(e) for e in errors])
                continue

            # Merge nested / extra BSON fields produced by synthesizer
            # (addresses[], merchant_tables[], ie_* maps, etc.).
            for k, v in row.items():
                if k in cfg["schema"] or v is None:
                    continue
                if k.startswith("_"):
                    cleaned[k.lstrip("_")] = v
                else:
                    cleaned[k] = v

            # Parent FK checks
            parent_missing = False
            for fk_col, parent_sheet in cfg["parents"].items():
                fk_value = row.get(fk_col)
                if fk_value is None or (isinstance(fk_value, str) and fk_value.strip() == ""):
                    if cfg["schema"].get(fk_col, {}).get("required"):
                        report.add_failure(
                            sheet, idx, [f"{fk_col}: required parent reference missing"]
                        )
                        parent_missing = True
                        break
                    continue
                if not _parent_exists(writer, parent_sheet, fk_value, report.created_ids):
                    report.add_skip(
                        sheet,
                        idx,
                        f"{fk_col}={fk_value!r} does not exist in "
                        f"{parent_sheet} ({SHEETS[parent_sheet]['collection']})",
                    )
                    parent_missing = True
                    break
            if parent_missing:
                continue

            try:
                id_value = cleaned[cfg["schema"][cfg["id_field"]]["bson"]]
                writer.upsert(cfg["collection"], cfg["schema"][cfg["id_field"]]["bson"], cleaned)
                report.add_success(sheet, id_value)
            except Exception as exc:  # noqa: BLE001
                report.add_failure(sheet, idx, [f"db_write_error: {exc}"])

    return report.to_dict()
