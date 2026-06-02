# Excel Ingest Lambda

AWS Lambda (**Python 3.11**) that ingests vertical onboarding Excel workbooks into MongoDB. Triggered by **S3** upload (`.xlsx`).

## What it does

1. **S3** `ObjectCreated` → download `.xlsx`
2. **Parse** vertical template (pages: Merchant, Store, Chain, Merchant Criteria, Instrument Criteria)
3. **Synthesize** implicit records (demographics, table refs, defaults)
4. **Transform** display text → service codes (`Activo` → `A`, `Nuevo León` → `NLE`, …)
5. **Validate** against rules aligned with Quarkus DTOs
6. **Upsert** to Mongo in dependency order
7. **Report** → CloudWatch + optional S3 (`REPORT_BUCKET`)

```
S3 (.xlsx) → parse_workbook → synthesize → ingest → report
```

## Mongo collections (`MONGO_DATABASE`, default `merchant`)

| Sheet | Collection |
|-------|------------|
| demographic | `demographic` |
| merchant_criteria | `criteria` |
| instrument_criteria | `instrument-criteria` |
| connector | `connector_properties` |
| connector_table | `connector_table` |
| chain | `chain_auth` |
| merchant | `merchant_auth` |
| store | `store_auth` |

Ingest order: parents (`demographic`, criteria, connector, chain) → `connector_table` → `merchant` → `store`.

## Repository contents (production)

```
excel-ingest-lambda/
├── lambda_function.py      # Handler: lambda_function.lambda_handler
├── requirements.txt
├── src/                    # Application code
├── deployment/             # env.example, AWS deploy notes
└── README.md
```

Local dev tools (`local-dev/`, `local_runner.py`, `sample/`) are **not** in this repo — keep them on your machine or a separate dev branch/archive.

## Build `package.zip` for AWS

Use **Linux Python 3.11** wheels (Docker). Do not `pip install` with Windows Python 3.14.

From the project root:

```bash
docker run --rm \
  -v "$(pwd):/work" -w /work \
  python:3.11-slim \
  sh -ec '
    pip install -q -r requirements.txt -t /tmp/pkg
    cp -r src /tmp/pkg/src
    cp lambda_function.py /tmp/pkg/
    cd /tmp/pkg && apt-get update -qq && apt-get install -qq -y zip >/dev/null
    zip -qr /work/package.zip .
  '
```

Upload **`package.zip`** to Lambda after every change to `src/` or `lambda_function.py`.

On Windows Git Bash, use `cygpath` or run `local-dev/build_zip.sh` from a local copy of the dev scripts.

## AWS configuration

| Setting | Value |
|---------|--------|
| Runtime | `python3.11` |
| Handler | `lambda_function.lambda_handler` |
| Timeout | 60s+ |
| Memory | 1024 MB+ |

### Environment variables

| Key | Required | Description |
|-----|----------|-------------|
| `MONGO_CONNECTION_STRING` | Yes | Full Mongo URI |
| `MONGO_DATABASE` | Yes | e.g. `merchant` |
| `REPORT_BUCKET` | No | S3 bucket for ingest JSON reports |

See [`deployment/env.example`](deployment/env.example).

### S3 trigger

- Upload bucket: `s3:ObjectCreated:*`, suffix `.xlsx`
- Lambda needs `s3:GetObject` (upload) and `s3:PutObject` (report bucket if used)

IAM and event details: [`deployment/serverless-handler-notes.md`](deployment/serverless-handler-notes.md).

## Remove dev files already on GitHub

If `local-dev/`, `sample/`, or `local_runner.py` were pushed earlier:

```bash
git rm -r --cached local-dev sample local_runner.py 2>/dev/null || true
git add .gitignore README.md
git commit -m "Track production code only"
git push
```

Files stay on your disk; they are only removed from the remote repo.

## License

Internal Zimble project.
