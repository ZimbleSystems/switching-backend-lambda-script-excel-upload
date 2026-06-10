"""
Local debug runner: synthesize first worksheet tab and attempt one API upsert per entity type.
Requires API_GATEWAY_URL and COGNITO PKCE env vars (same as Lambda).
Optional: API_DEBUG_LOG=true and API_DEBUG_LOG_FILE=api-debug.log for full request/response logs.

Usage (from project root):
  set PYTHONPATH=src
  python debug_api_ingest.py path/to/workbook.xlsx
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from excel_parser import parse_workbook
from synthesizer import synthesize
from api_client import ApiGatewayClient, SHEET_TO_API_PATH
from orchestrator import ingest
from schemas import SHEETS


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python debug_api_ingest.py <workbook.xlsx>")
        sys.exit(1)

    xlsx = Path(sys.argv[1])
    bundles = parse_workbook(xlsx.read_bytes())
    print(f"parsed {len(bundles)} tab(s); running ingest on all")

    worksheets = [b["worksheet"] for b in bundles]
    tabs = synthesize(
        [b["pages"] for b in bundles],
        worksheets=worksheets,
        per_tab=True,
    )

    client = ApiGatewayClient()
    print("API_GATEWAY_URL:", client.api_gateway_url)
    print("SHEET_TO_API_PATH:", json.dumps(SHEET_TO_API_PATH, indent=2))

    report = ingest(tabs, client)
    print(json.dumps(report, indent=2, default=str))
    client.close()


if __name__ == "__main__":
    main()
