# Excel Ingest Lambda

AWS Lambda (**Python 3.11**) that ingests vertical onboarding Excel workbooks into MongoDB. Triggered by **S3** upload (`.xlsx`).

## What it does

1. **S3** `ObjectCreated` → download `.xlsx`
2. **Parse** vertical template from **every worksheet tab** in the workbook (each tab = one merchant/store bundle; pages: Merchant, Store, Chain, Merchant Criteria, Instrument Criteria)
3. **Synthesize** implicit records (demographics, table refs, defaults)
4. **Transform** display text → service codes (`Activo` → `A`, `Nuevo León` → `NLE`, …)
5. **Validate** against rules aligned with Quarkus DTOs
6. **Authenticate** via AWS Cognito to acquire a JWT token
7. **Upsert** via HTTP to the **API Gateway** in dependency order
8. **Report** → CloudWatch + optional S3 (`REPORT_BUCKET`)

```
S3 (.xlsx) → parse_workbook → synthesize → authenticate (Cognito) → ingest via API Gateway → report
```

Empty tabs (no Merchant/Store rows) are skipped. The ingest report includes `worksheets`: tab name + which logical pages were found per tab.

### Multi-tab workbooks (shared masters)

Each Excel tab is ingested in order. **Duplicate primary keys** across tabs are skipped individually (not the whole tab): e.g. merchant `01`, merchant criteria `100`, instrument criteria `300` are written once; later tabs only add new entities (typically **stores**).

- **Chain** `0` and template `chain_id_link` text are treated as “no chain” (no `chain` / chain demographic rows).
- **Merchant demographic** rows are created only when Excel supplies `merchant_demographics_id` or the Merchant page has real address/contact data.
- **Store demographics** are written per tab when each tab has its own id (e.g. `DS_101`, `DS_104`).
- Skips appear in `summary.<sheet>.skipped` and `errors[]` with optional `worksheet` (tab name).

## API Gateway Endpoints


| Sheet               | API Path                               |
| ------------------- | -------------------------------------- |
| demographic         | `/auth/demographic/v1/`                |
| merchant_criteria   | `/config/merchant-criteria/v1/`        |
| instrument_criteria | `/config/instrument-criteria/v1/`      |
| chain               | `/auth/chain/v1/`                      |
| merchant            | `/auth/merchant/v1/`                   |
| store               | `/auth/store/v1/`                      |
| connector           | `/config/connector-properties/v1/`     |
| connector_table     | `/auth/connectorTable/v1/`             |


Ingest order per tab: `demographic` → criteria → `chain` (if real id) → `merchant` → `store`.

## Repository contents (production)

```
excel-ingest-lambda/
├── lambda_function.py      # Handler: lambda_function.lambda_handler
├── requirements.txt
├── src/                    # Application code
└── README.md
```

Not in git (local only): `local-dev/`, `deployment/`, `sample/`, `local_runner.py`.

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

Upload `**package.zip**` to Lambda after every change to `src/` or `lambda_function.py`.

On Windows Git Bash, use `cygpath` or run `local-dev/build_zip.sh` from a local copy of the dev scripts.

## AWS configuration


| Setting | Value                            |
| ------- | -------------------------------- |
| Runtime | `python3.11`                     |
| Handler | `lambda_function.lambda_handler` |
| Timeout | 60s+                             |
| Memory  | 1024 MB+                         |


### Environment variables


| Key                     | Required | Description                                    |
| ----------------------- | -------- | ---------------------------------------------- |
| `API_GATEWAY_URL`       | Yes      | e.g. `https://iconn.poc.zimblesystems.click`   |
| `COGNITO_USER_POOL_ID`  | Yes      | User pool ID for PKCE auth (e.g. `ap-south-1_563GXconM`) |
| `COGNITO_CLIENT_ID`     | Yes      | App client ID (authorization code + PKCE)      |
| `COGNITO_REDIRECT_URI`  | Yes      | Registered callback URL (302 intercepted; need not be reachable) |
| `COGNITO_SCOPES`        | Yes      | e.g. `openid profile adminscope/allaccessscope email` |
| `COGNITO_USERNAME`      | Yes      | Hosted UI login user                           |
| `COGNITO_PASSWORD`      | Yes      | Hosted UI login password                       |
| `COGNITO_REGION`        | No       | AWS region (defaults from user pool id prefix) |
| `COGNITO_DOMAIN`        | No       | Hosted UI domain; auto-discovered if omitted   |
| `COGNITO_CLIENT_SECRET` | No       | HTTP Basic on token exchange if client is confidential |
| `REPORT_BUCKET`         | No       | S3 bucket for ingest JSON reports              |
| `API_DEBUG_LOG`         | No       | `true` to log each API URL, method, request body, and response (CloudWatch) |
| `API_DEBUG_LOG_FILE`    | No       | Optional NDJSON file path for the same debug output (e.g. `/tmp/api-debug.log`) |


### S3 trigger

- Upload bucket: `s3:ObjectCreated:*`, suffix `.xlsx`
- Lambda needs `s3:GetObject` on upload bucket; `s3:PutObject` on report bucket if `REPORT_BUCKET` is set
- Allow S3 to invoke the function (resource policy on function ARN)

### IAM (minimum)

- `s3:GetObject` — upload bucket
- `s3:PutObject` — report bucket (optional)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- *Note: VPC ENI permissions for direct MongoDB access are no longer required. The Lambda makes standard HTTPS requests to the API Gateway.*

## Remove non-production paths already on GitHub

```bash
git rm -r --cached local-dev deployment sample local_runner.py 2>/dev/null || true
git add .gitignore README.md
git commit -m "Track production code only"
git push
```

Files stay on your disk; they are only removed from the remote repo.

## License

Internal Zimble project.