"""
AWS Lambda entry point.

Trigger: S3 ObjectCreated event for an Excel file.

Required environment variables:
    MONGO_CONNECTION_STRING   e.g. mongodb+srv://user:pass@host/db
    MONGO_DATABASE            e.g. merchant

Optional environment variables:
    REPORT_BUCKET             if set, the run report is written to this S3 bucket
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict
from urllib.parse import unquote_plus

import boto3

from excel_parser import parse_workbook
from mongo_writer import MongoWriter
from orchestrator import ingest
from synthesizer import synthesize

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_s3 = boto3.client("s3")


def _download(bucket: str, key: str) -> bytes:
    resp = _s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def _put_report(bucket: str, key: str, report: Dict[str, Any]) -> None:
    _s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(report, indent=2, default=str).encode("utf-8"),
        ContentType="application/json",
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:  # noqa: ARG001
    logger.info("event=%s", json.dumps(event, default=str)[:2000])

    writer = MongoWriter()
    overall: Dict[str, Any] = {"files": []}

    try:
        for record in event.get("Records", []):
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            logger.info("processing s3://%s/%s", bucket, key)

            payload = _download(bucket, key)
            parsed = parse_workbook(payload)
            records = synthesize(parsed)
            file_report = ingest(records, writer)
            file_report["parsed_pages"] = {k: list(v.keys()) for k, v in parsed.items()}
            file_report["source"] = f"s3://{bucket}/{key}"
            overall["files"].append(file_report)

            report_bucket = os.environ.get("REPORT_BUCKET")
            if report_bucket:
                report_key = key.rsplit(".", 1)[0] + ".report.json"
                _put_report(report_bucket, report_key, file_report)
                logger.info("report written to s3://%s/%s", report_bucket, report_key)
    finally:
        writer.close()

    logger.info("ingest_report=%s", json.dumps(overall, default=str)[:5000])
    return {"statusCode": 200, "body": json.dumps(overall, default=str)}
