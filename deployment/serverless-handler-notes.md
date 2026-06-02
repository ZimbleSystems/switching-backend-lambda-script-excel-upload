# Deployment notes

## Package layout for AWS Lambda

The Lambda **handler** is `lambda_function.lambda_handler`.

```
excel-ingest-lambda/
├── lambda_function.py
├── src/
│   ├── __init__.py
│   ├── excel_parser.py
│   ├── validators.py
│   ├── schemas.py
│   ├── mongo_writer.py
│   ├── orchestrator.py
│   └── errors.py
└── requirements.txt
```

## Build a deployment zip

```bash
cd excel-ingest-lambda
rm -rf build/ package.zip
mkdir build
pip install -r requirements.txt -t build/
cp -r src lambda_function.py build/
cd build && zip -r ../package.zip . && cd ..
```

The zip will be ~30–40 MB because of `pandas` + `pymongo`. If that exceeds
limits, switch to a **Lambda Layer** for `pandas` (e.g. AWS-managed
Klayers/pandas) or replace `pandas` with raw `openpyxl` parsing.

## Required IAM permissions

The execution role needs at minimum:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::<your-upload-bucket>/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<your-report-bucket>/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}
```

If Mongo Atlas is used over VPC peering, add the relevant `ec2:*` ENI
permissions and place the Lambda in the correct VPC + subnets.

## S3 event configuration

In the S3 bucket -> Properties -> Event notifications:
- Event type: `s3:ObjectCreated:Put`
- Suffix: `.xlsx`
- Destination: this Lambda function

## Environment variables

See `env.example`.

## Optional improvements

- Send Mongo connection string via AWS Secrets Manager and fetch in
  `MongoWriter`.
- Add SNS/Slack notification on failures by inspecting the returned
  `ingest_report`.
- Replace `pandas` with `openpyxl` only to shrink the package.
