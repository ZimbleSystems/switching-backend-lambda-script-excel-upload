#!/usr/bin/env bash
# One-shot: create the S3 bucket, deploy the lambda, wire the S3 trigger
# on LocalStack. Run after `docker compose up -d` and `./build_zip.sh`.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/build"
ZIP="$BUILD/package.zip"

# AWS CLI on Windows is a native Win binary that doesn't understand
# MINGW paths (/c/Users/...). Convert to a Windows path AWS CLI accepts.
if command -v cygpath >/dev/null 2>&1; then
  ZIP_AWS="$(cygpath -m "$ZIP")"
else
  ZIP_AWS="$ZIP"
fi

ENDPOINT="${ENDPOINT:-http://localhost:4566}"
REGION="${REGION:-us-east-1}"
BUCKET="${BUCKET:-excel-uploads}"
REPORT_BUCKET="${REPORT_BUCKET:-excel-reports}"
FUNCTION="${FUNCTION:-excel-ingest}"
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-role"

# LocalStack accepts dummy creds
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$REGION"

aws() { command aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"; }

echo ">> Ensure zip exists"
[ -f "$ZIP" ] || { echo "Run ./build_zip.sh first"; exit 1; }

echo ">> Create buckets (if missing)"
aws s3api create-bucket --bucket "$BUCKET"        2>/dev/null || true
aws s3api create-bucket --bucket "$REPORT_BUCKET" 2>/dev/null || true

echo ">> Create / update lambda"
_wait_lambda_idle() {
  # Wait until LastUpdateStatus != InProgress and State == Active
  for _ in $(seq 1 60); do
    read -r STATE LAST <<<"$(aws lambda get-function-configuration \
        --function-name "$FUNCTION" \
        --query '[State,LastUpdateStatus]' --output text 2>/dev/null || echo 'Pending InProgress')"
    if [ "$STATE" = "Active" ] && [ "$LAST" != "InProgress" ]; then
      return 0
    fi
    sleep 1
  done
  echo "   warn: lambda still busy (State=$STATE LastUpdate=$LAST)"
}

# Mongo is exposed on the host at localhost:27017 by docker-compose; the
# lambda runs inside a container started by LocalStack, so it must reach
# the host via the special Docker Desktop DNS name "host.docker.internal".
MONGO_URI="${MONGO_URI:-mongodb://host.docker.internal:27017}"
ENV_VARS="Variables={MONGO_CONNECTION_STRING=$MONGO_URI,MONGO_DATABASE=merchant,REPORT_BUCKET=$REPORT_BUCKET}"

if aws lambda get-function --function-name "$FUNCTION" >/dev/null 2>&1; then
  _wait_lambda_idle
  aws lambda update-function-code \
    --function-name "$FUNCTION" \
    --zip-file "fileb://$ZIP_AWS" >/dev/null
  _wait_lambda_idle
  aws lambda update-function-configuration \
    --function-name "$FUNCTION" \
    --environment "$ENV_VARS" \
    --timeout 60 \
    --memory-size 1024 >/dev/null
  _wait_lambda_idle
else
  aws lambda create-function \
    --function-name "$FUNCTION" \
    --runtime python3.11 \
    --handler lambda_function.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$ZIP_AWS" \
    --timeout 60 \
    --memory-size 1024 \
    --environment "$ENV_VARS" >/dev/null
  _wait_lambda_idle
fi

echo ">> Wait for lambda to become Active"
for i in $(seq 1 30); do
  STATE="$(aws lambda get-function-configuration --function-name "$FUNCTION" \
            --query 'State' --output text 2>/dev/null || echo 'Pending')"
  [ "$STATE" = "Active" ] && break
  sleep 1
done
echo "   lambda state = $STATE"

echo ">> Allow S3 to invoke the lambda"
aws lambda remove-permission --function-name "$FUNCTION" --statement-id s3invoke 2>/dev/null || true
aws lambda add-permission \
  --function-name "$FUNCTION" \
  --statement-id s3invoke \
  --action "lambda:InvokeFunction" \
  --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::$BUCKET" >/dev/null

echo ">> Wire S3 -> Lambda notification on $BUCKET"
LAMBDA_ARN="arn:aws:lambda:${REGION}:000000000000:function:${FUNCTION}"
NOTIF=$(cat <<JSON
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "ExcelUploaded",
      "LambdaFunctionArn": "$LAMBDA_ARN",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": { "Key": { "FilterRules": [ { "Name": "suffix", "Value": ".xlsx" } ] } }
    }
  ]
}
JSON
)
aws s3api put-bucket-notification-configuration \
  --bucket "$BUCKET" \
  --notification-configuration "$NOTIF" \
  --skip-destination-validation

echo ">> Done. Try:"
echo "    bash upload.sh ../sample/sample-vertical.xlsx"
