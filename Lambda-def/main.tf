# Data source for current AWS account
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

data "aws_secretsmanager_secret" "mongodb" {
  name = var.mongodb_secret_name
}

data "aws_secretsmanager_secret_version" "mongodb" {
  secret_id = data.aws_secretsmanager_secret.mongodb.id
}

# Fetch the VPC by its Name tag
data "aws_vpc" "selected" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_name]
  }
}

# Fetch Subnet 1 by its Name tag AND scope it to the selected VPC
data "aws_subnet" "subnet_1" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = [var.subnet1_name]
  }
}

# Fetch Subnet 2 by its Name tag AND scope it to the selected VPC
data "aws_subnet" "subnet_2" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = [var.subnet2_name]
  }
}

data "aws_security_group" "selected" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = var.security_group_name
  }
}

locals {
  data_bucket_arn = "arn:${data.aws_partition.current.partition}:s3:::${var.project_code}-${var.env}-data-bucket"
}

# Archive the Lambda function code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda_function.zip"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_code}-${var.env}-excel-ingest-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# CRITICAL: Attach VPC execution permissions to the Lambda Role
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_policy" "secrets_manager_policy" {
  name = "${var.project_code}-${var.env}-excel-ingest-mongodb-secret-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = data.aws_secretsmanager_secret.mongodb.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.secrets_manager_policy.arn
}

# Custom CloudWatch Logs Policy
resource "aws_iam_role_policy" "lambda_logs_policy" {
  name = "${var.project_code}-${var.env}-excel-ingest-lambda-logs-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "logs:CreateLogGroup"
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_code}-${var.env}-excel-ingest-lambda:*"
        ]
      }
    ]
  })
}

# KMS Decrypt Policy for bucket encryption
resource "aws_iam_role_policy" "lambda_kms_policy" {
  name = "${var.project_code}-${var.env}-excel-ingest-lambda-kms-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
      }
    ]
  })
}

# FIXED: Replaced invalid JSON colon ':' syntax with correct HCL assignment '='
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${var.project_code}-${var.env}-excel-ingest-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = local.data_bucket_arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${var.upload_bucket_name}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${var.report_bucket}/*"
      }
    ]
  })
}

# Lambda Function: excel-ingest-lambda
resource "aws_lambda_function" "excel_ingest_lambda" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "${var.project_code}-${var.env}-excel-ingest-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  architectures = ["arm64"]
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory
  publish       = true

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [aws_lambda_layer_version.python_layer.arn]

  environment {
    variables = {
      MONGO_CONNECTION_STRING = jsondecode(data.aws_secretsmanager_secret_version.mongodb.secret_string)["mongodb_atlas_conn_str"]
      MONGO_DATABASE          = var.mongo_database
      REPORT_BUCKET           = var.report_bucket
    }
  }

  vpc_config {
    subnet_ids = [
      data.aws_subnet.subnet_1.id,
      data.aws_subnet.subnet_2.id
    ]
    security_group_ids = [
      data.aws_security_group.selected.id
    ]
  }

  tags = merge(var.tags, {
    Name = "${var.project_code}-${var.env}-excel-ingest-lambda"
  })

  depends_on = [
    data.archive_file.lambda_zip,
    aws_iam_role_policy.lambda_logs_policy,
    aws_iam_role_policy.lambda_kms_policy,
    aws_iam_role_policy.lambda_s3_policy,
    aws_iam_role_policy_attachment.lambda_vpc_execution
  ]
}
