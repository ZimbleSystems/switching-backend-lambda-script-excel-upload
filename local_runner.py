"""
Local runner so you can validate the Excel against the same rules
WITHOUT deploying to Lambda.

Usage:
    python local_runner.py --file path/to/data.xlsx \
        --mongo "mongodb://localhost:27017" \
        --db merchant

If --mongo is omitted, the runner does a DRY RUN: it only validates
the workbook and prints what would be inserted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.excel_parser import parse_workbook
from src.orchestrator import ingest
from src.schemas import SHEETS
from src.synthesizer import synthesize
from src.validators import validate_row


class _DryRunWriter:
    """In-memory stand-in for MongoWriter; pretends every parent exists
    if it was inserted earlier in the run, and remembers documents so we
    can dump them later."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Dict]] = {}

    def exists(self, collection: str, id_field: str, id_value: str) -> bool:
        for doc in self._store.get(collection, {}).values():
            if str(doc.get(id_field)) == str(id_value):
                return True
        return False

    def upsert(self, collection: str, id_field: str, document: Dict) -> Dict:
        self._store.setdefault(collection, {})[str(document[id_field])] = document
        return {"matched": 0, "modified": 0, "upserted_id": "dry-run"}

    def close(self) -> None:
        return None

    def dump(self) -> Dict[str, Dict[str, Dict]]:
        return self._store


def _validate_only(parsed: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for sheet, rows in parsed.items():
        cfg = SHEETS[sheet]
        sheet_errors = []
        for idx, row in enumerate(rows, start=2):
            cleaned, errors = validate_row(row, cfg["schema"])
            if errors:
                sheet_errors.append(
                    {"row": idx, "errors": [str(e) for e in errors]}
                )
        out[sheet] = {
            "rows": len(rows),
            "errors": sheet_errors,
            "ok_rows": len(rows) - len(sheet_errors),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Excel ingest runner")
    parser.add_argument("--file", required=True, help="Path to .xlsx workbook")
    parser.add_argument(
        "--mongo", default=None,
        help="Mongo connection string. If omitted, run DRY (validate only)",
    )
    parser.add_argument("--db", default="merchant", help="Mongo database name")
    parser.add_argument("--show-docs", action="store_true",
                        help="Dump cleaned Mongo documents the lambda would insert")
    args = parser.parse_args()

    payload = Path(args.file).read_bytes()
    parsed = parse_workbook(payload)
    records = synthesize(parsed)
    print("pages parsed:", {k: len(v) for k, v in parsed.items()})
    print("records produced:", {k: len(v) for k, v in records.items()})

    if args.mongo:
        from src.mongo_writer import MongoWriter

        writer = MongoWriter(args.mongo, args.db)
        try:
            report = ingest(records, writer)
        finally:
            writer.close()
    else:
        writer = _DryRunWriter()
        report = ingest(records, writer)  # type: ignore[arg-type]
        report["_note"] = "DRY RUN - nothing written to Mongo"
        if args.show_docs:
            report["mongo_documents"] = writer.dump()

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
