# Local development with LocalStack

Run the lambda exactly the way AWS does — S3 upload triggers the
function — without an AWS account, using LocalStack + a local Mongo.

## Prerequisites

| Tool | Why |
|---|---|
| Docker Desktop | Hosts LocalStack and Mongo |
| Python 3.11    | Builds the deployment zip |
| AWS CLI v2     | Talks to LocalStack at `localhost:4566` |
| Git Bash / WSL | For the `*.sh` helper scripts on Windows |

Install the AWS CLI once if you don't have it:

```bash
pip install awscli
aws --version
```

## One-time setup

```bash
cd excel-ingest-lambda/local-dev
docker compose up -d                # starts LocalStack + Mongo
bash build_zip.sh                   # produces build/package.zip
bash deploy_localstack.sh           # creates buckets, deploys lambda, wires S3 trigger
```

If the second step prints `package.zip size: ... bytes` you're good.

### `build_zip.sh`: Permission denied on WSL (`/mnt/c/...`)

If you see hundreds of `rm: ... Permission denied` under `local-dev/build/`,
a previous Docker build left **root-owned** files on the Windows drive. The
script now cleans and zips **entirely inside Docker** to avoid that.

If it still fails, clean `build/` with Docker (do **not** use `$(pwd)` in **CMD** — it
does not expand):

```bat
REM Windows CMD (from local-dev folder)
clean_build.cmd
```

```powershell
# PowerShell
.\clean_build.ps1
```

```bash
# Git Bash / WSL only
docker run --rm -v "$(pwd)/build:/build" alpine sh -c 'rm -rf /build/*'
bash build_zip.sh
```

## Test an upload

```bash
bash upload.sh ../sample/sample-vertical.xlsx
```

This will:

1. `aws s3 cp` the file to `s3://excel-uploads/sample-vertical.xlsx`
   (LocalStack)
2. LocalStack fires the `s3:ObjectCreated:*` event
3. Your lambda runs (in a Docker container started by LocalStack), the
   pipeline writes documents into your real local Mongo on `localhost:27017`
4. The script tails CloudWatch logs and prints the `*.report.json` from
   the report bucket if one was produced

## Inspect Mongo

The Mongo container is on the same Docker network as LocalStack (so the
lambda reaches it at `mongo:27017`) and exposed on your host at
`localhost:27017`. Easiest inspection:

```bash
docker exec -it excel-ingest-mongo mongosh merchant \
  --eval 'db.getCollectionNames().forEach(n => print(n + ": " + db[n].countDocuments()))'
```

You should see counts for: `demographic`, `criteria`, `instrument-criteria`,
`chain_auth`, `merchant_auth`, `store_auth`.

To inspect a single document:

```bash
docker exec -it excel-ingest-mongo mongosh merchant \
  --eval 'printjson(db.merchant_auth.findOne({merchant_id: "01"}))'
```

## Re-deploy after a code change

```bash
bash build_zip.sh && bash deploy_localstack.sh
```

(`deploy_localstack.sh` is idempotent — it creates the function the first
time and updates the code/config every time after.)

## Test the failure path

```bash
python ../sample/generate_sample_broken.py
bash upload.sh ../sample/sample-vertical-broken.xlsx
```

The lambda logs will list every per-row validation error and the report
file will record `failed`/`skipped` counts per entity.

## Tear down

```bash
docker compose down -v             # stop and remove volumes
```

## When you're ready for real AWS

Use exactly the same `build/package.zip` and the same handler
(`lambda_function.lambda_handler`). The deployment notes in
`../deployment/serverless-handler-notes.md` cover IAM, real S3 events,
and Mongo Atlas.
