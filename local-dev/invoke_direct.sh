#!/usr/bin/env bash
# Bypass the S3 trigger and invoke the lambda directly with a synthetic
# S3 event. Useful when LocalStack's S3->Lambda wiring is misbehaving but
# you still want to verify the lambda code itself works against Mongo.

set -euo pipefail

ENDPOINT="${ENDPOINT:-http://localhost:4566}"
REGION="${REGION:-us-east-1}"
BUCKET="${BUCKET:-excel-uploads}"
FUNCTION="${FUNCTION:-excel-ingest}"
KEY="${1:-sample-vertical.xlsx}"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$REGION"
export AWS_REGION="$REGION"

aws() { command aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"; }

PAYLOAD=$(cat <<JSON
{"Records":[{"s3":{"bucket":{"name":"$BUCKET"},"object":{"key":"$KEY"}}}]}
JSON
)

OUT="$(mktemp)"
echo ">> Invoking $FUNCTION with synthetic S3 event for s3://$BUCKET/$KEY"

# AWS CLI v1 accepts --payload as a string; v2 needs --cli-binary-format
if aws lambda invoke --help 2>/dev/null | grep -q -- '--cli-binary-format'; then
  aws lambda invoke \
    --function-name "$FUNCTION" \
    --cli-binary-format raw-in-base64-out \
    --payload "$PAYLOAD" \
    "$OUT" >/dev/null
else
  aws lambda invoke \
    --function-name "$FUNCTION" \
    --payload "$PAYLOAD" \
    "$OUT" >/dev/null
fi

echo ">> Lambda return:"
cat "$OUT"
echo ""

echo ">> Recent log events:"
LOG_GROUP="/aws/lambda/$FUNCTION"
STREAM="$(aws logs describe-log-streams --log-group-name "$LOG_GROUP" \
            --order-by LastEventTime --descending \
            --query 'logStreams[0].logStreamName' --output text 2>/dev/null || true)"
if [ -n "$STREAM" ] && [ "$STREAM" != "None" ]; then
  aws logs get-log-events --log-group-name "$LOG_GROUP" \
      --log-stream-name "$STREAM" --limit 200 \
      --query 'events[].message' --output text
fi
