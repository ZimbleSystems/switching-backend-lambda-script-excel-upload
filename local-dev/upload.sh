#!/usr/bin/env bash
# Upload an xlsx to the LocalStack S3 bucket and tail the lambda logs.

set -euo pipefail

FILE="${1:-../sample/sample-vertical.xlsx}"
[ -f "$FILE" ] || { echo "file not found: $FILE"; exit 1; }

# Native Windows AWS CLI needs Windows-style paths
if command -v cygpath >/dev/null 2>&1; then
  FILE_AWS="$(cygpath -m "$FILE")"
else
  FILE_AWS="$FILE"
fi

ENDPOINT="${ENDPOINT:-http://localhost:4566}"
REGION="${REGION:-us-east-1}"
BUCKET="${BUCKET:-excel-uploads}"
REPORT_BUCKET="${REPORT_BUCKET:-excel-reports}"
FUNCTION="${FUNCTION:-excel-ingest}"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$REGION"

aws() { command aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"; }

KEY="$(basename "$FILE")"
echo ">> Uploading $FILE -> s3://$BUCKET/$KEY"
aws s3 cp "$FILE_AWS" "s3://$BUCKET/$KEY"

echo ">> Waiting 6s for lambda to fire..."
sleep 6

echo ">> Lambda logs (most recent stream):"
LOG_GROUP="/aws/lambda/$FUNCTION"
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
      --query 'logGroups[0].logGroupName' --output text 2>/dev/null \
   | grep -q "$LOG_GROUP"; then
  STREAM="$(aws logs describe-log-streams \
              --log-group-name "$LOG_GROUP" \
              --order-by LastEventTime --descending \
              --query 'logStreams[0].logStreamName' --output text 2>/dev/null)"
  if [ -n "$STREAM" ] && [ "$STREAM" != "None" ]; then
    aws logs get-log-events \
      --log-group-name "$LOG_GROUP" \
      --log-stream-name "$STREAM" \
      --limit 200 \
      --query 'events[].message' --output text
  else
    echo "  (log group exists but no streams yet)"
  fi
else
  echo "  (log group $LOG_GROUP does not exist - lambda probably did not fire)"
  echo "  Try: bash invoke_direct.sh"
fi

echo ""
echo ">> Report (if produced):"
REPORT_KEY="${KEY%.*}.report.json"
aws s3 cp "s3://$REPORT_BUCKET/$REPORT_KEY" - 2>/dev/null \
  || echo "  (no report file at s3://$REPORT_BUCKET/$REPORT_KEY)"
