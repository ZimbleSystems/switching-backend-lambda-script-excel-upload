# Excel Ingest Lambda

AWS Lambda (**Python 3.11**) that ingests vertical onboarding Excel workbooks into MongoDB. Triggered by **S3** upload (`.xlsx`); writes entities used by Zimble merchant/store/criteria services.

## What it does

1. **S3** `ObjectCreated` → download `.xlsx`
2. **Parse** vertical template (one row per attribute; pages: Merchant, Store, Chain, Merchant Criteria, Instrument Criteria)
3. **Synthesize** implicit records (demographics per page, table refs, defaults)
4. **Transform** UI/display text → service codes (`Activo` → `A`, `Nuevo León` → `NLE`, …)
5. **Validate** against schema rules aligned with Quarkus DTOs
6. **Upsert** to Mongo in dependency order (parents before children)
7. **Report** → CloudWatch logs + optional JSON on S3 (`REPORT_BUCKET`)

```
S3 (.xlsx) → parse_workbook → synthesize → ingest → report
```

## Mongo targets

| Logical sheet | Collection | Notes |
|---------------|------------|--------|
| demographic | `demographic` | Synthesized from M/S/C address blocks |
| merchant_criteria | `criteria` | |
| instrument_criteria | `instrument-criteria` | |
| connector | `connector_properties` | |
| connector_table | `connector_table` | |
| chain | `chain_auth` | |
| merchant | `merchant_auth` | |
| store | `store_auth` | |

Database name: **`merchant`** (configurable via `MONGO_DATABASE`).

### Ingest order

```
demographic, merchant_criteria, instrument_criteria, connector, chain
  → connector_table → merchant → store
```

Children are skipped with an explicit error if a required parent ID is missing.

## Repository layout

```
excel-ingest-lambda/
├── lambda_function.py      # AWS handler (lambda_function.lambda_handler)
├── requirements.txt
├── local_runner.py         # Local test without S3/Lambda
├── src/                    # Application code (deployed in zip)
├── deployment/             # env template + AWS notes
├── sample/                 # Workbook generator + sample .xlsx
└── local-dev/              # LocalStack + Docker build scripts (dev only)
```

**Not in git:** `local-dev/build/` and `package.zip` — produced by `build_zip.sh` (see `.gitignore`).

## Prerequisites

| Environment | Requirement |
|-------------|-------------|
| **AWS Lambda** | Runtime `python3.11`, handler `lambda_function.lambda_handler` |
| **Build** | Docker (recommended) — see `local-dev/build_zip.sh` |
| **Local test** | Python 3.11+, MongoDB |
| **Local S3 simulation** | Docker, LocalStack — see `local-dev/README.md` |

Do **not** build deployment wheels with local **Python 3.14** on Windows; use the Docker build script so pandas/numpy match Lambda Linux **cp311**.

## Build deployment package

```bash
cd excel-ingest-lambda/local-dev
./build_zip.sh
# Output: local-dev/build/package.zip  (~30–40 MB)
```

Upload **`package.zip`** to Lambda (function code). Rebuild after any change under `src/` or `lambda_function.py`.

## AWS configuration (infra)

### Lambda settings

| Setting | Value |
|---------|--------|
| Runtime | `python3.11` |
| Handler | `lambda_function.lambda_handler` |
| Timeout | 60s+ (1024 MB memory suggested) |

### Environment variables

| Key | Required | Description |
|-----|----------|-------------|
| `MONGO_CONNECTION_STRING` | Yes | Full Mongo URI (credentials in URI) |
| `MONGO_DATABASE` | Yes | e.g. `merchant` |
| `REPORT_BUCKET` | No | S3 bucket for `*.report.json` ingest reports |

Template: [`deployment/env.example`](deployment/env.example)

### S3

- **Upload bucket** — trigger source; filter suffix `.xlsx`
- **Report bucket** (optional) — set as `REPORT_BUCKET`

### IAM (minimum)

- `s3:GetObject` on upload bucket
- `s3:PutObject` on report bucket (if used)
- CloudWatch Logs
- VPC ENI permissions if Mongo is private

Details: [`deployment/serverless-handler-notes.md`](deployment/serverless-handler-notes.md)

## Local development

### Quick run (no Lambda)

```bash
cd excel-ingest-lambda
pip install -r requirements.txt

python sample/generate_sample.py
python local_runner.py --file sample/sample-vertical.xlsx --show-docs

# With Mongo
python local_runner.py --file sample/sample-vertical.xlsx \
  --mongo "mongodb://localhost:27017" --db merchant
```

### Full stack (LocalStack + S3 trigger)

See [`local-dev/README.md`](local-dev/README.md):

```bash
cd local-dev
docker compose up -d
./build_zip.sh
./deploy_localstack.sh
./upload.sh ../sample/sample-vertical.xlsx
```

## Excel template

Attribute layout per page: [`sample/sample-template.md`](sample/sample-template.md).

Generate samples:

```bash
python sample/generate_sample.py
python sample/generate_sample_broken.py   # demo failure paths
```

## Publishing to GitHub

```bash
cd excel-ingest-lambda
git init
git add .
git status   # confirm build/ and package.zip are not listed
git commit -m "Add excel ingest lambda"
git remote add origin <your-repo-url>
git push -u origin main
```

Only **source** is tracked; CI or developers run `build_zip.sh` to produce `package.zip` for AWS.

## Related documentation

- `deployment/serverless-handler-notes.md` — zip layout, IAM, S3 events
- `local-dev/README.md` — LocalStack workflow
- Parent repo `docs/` — Excel vs services field mapping (if present in monorepo)

## License

Internal Zimble project — adjust license text as required by your organization.
