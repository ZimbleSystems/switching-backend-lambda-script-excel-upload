# ==========================================
# 1. GLOBAL DATA SOURCES & SECRETS
# ==========================================
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

data "aws_secretsmanager_secret" "cognito_credentials" {
  name = var.cognito_secret_name
}

data "aws_secretsmanager_secret_version" "cognito_credentials" {
  secret_id = data.aws_secretsmanager_secret.cognito_credentials.id
}

# Secrets Manager configuration for MongoDB
data "aws_secretsmanager_secret" "mongodb" {
  name = var.mongodb_secret_name
}

data "aws_secretsmanager_secret_version" "mongodb" {
  secret_id = data.aws_secretsmanager_secret.mongodb.id
}

# ==========================================
# 2. NETWORKING DATA SOURCES
# ==========================================
# Fetch the VPC by its Name tag
data "aws_vpc" "selected" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_name]
  }
}

# Fetch Subnets by their Name tags AND scope them to the selected VPC
data "aws_subnet" "subnet_1" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = [var.subnet1_name]
  }
}

data "aws_subnet" "subnet_2" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = [var.subnet2_name]
  }
}

data "aws_subnet" "subnet_3" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = [var.subnet3_name]
  }
}

data "aws_security_group" "selected" {
  vpc_id = data.aws_vpc.selected.id
  filter {
    name   = "tag:Name"
    values = var.security_group_name # Passed directly as a list(string)
  }
}

# ==========================================
# 3. COGNITO DATA SOURCES & SEARCH LOGIC
# ==========================================
# 1. Look up the User Pool ID using the User Pool Name
data "aws_cognito_user_pools" "selected" {
  name = var.user_pool_name
}

# 2. ADDED: Look up the full pool configurations using the ID found above to retrieve its Domain prefix
data "aws_cognito_user_pool" "pool_details" {
  user_pool_id = tolist(data.aws_cognito_user_pools.selected.ids)[0]
}

# 3. Look up ALL client IDs inside the User Pool
data "aws_cognito_user_pool_clients" "all" {
  user_pool_id = tolist(data.aws_cognito_user_pools.selected.ids)[0]
}

# 4. Map the unique client_name to find its unique client ID
locals {
  target_client_id = data.aws_cognito_user_pool_clients.all.client_ids[index(data.aws_cognito_user_pool_clients.all.client_names, var.app_client_name)]
}

# 5. Feed that clean ID into the singular data source to safely pull the correct Client Secret
data "aws_cognito_user_pool_client" "target_client" {
  user_pool_id = tolist(data.aws_cognito_user_pools.selected.ids)[0]
  client_id    = local.target_client_id
}

# ==========================================
# 4. LOCAL VALUES CONFIGURATION
# ==========================================
locals {
  data_bucket_arn = "arn:${data.aws_partition.current.partition}:s3:::${var.project_code}-${var.env}-data-bucket"
  token_url       = "https://${data.aws_cognito_user_pool.pool_details.domain}.auth.${data.aws_region.current.name}.amazoncognito.com/oauth2/token"
}

# ==========================================
# 5. LAMBDA COMPILATION & IAM ROLES
# ==========================================
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

# Attach VPC execution permissions to the Lambda Role
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Secrets Manager Access Policy for MongoDB Secret
resource "aws_iam_policy" "secrets_manager_policy" {
  name = "${var.project_code}-${var.env}-excel-ingest-mongodb-secret-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          data.aws_secretsmanager_secret.mongodb.arn,
          data.aws_secretsmanager_secret.cognito_credentials.arn
        ]
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

# S3 Permissions Policy
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

# ==========================================
# 6. LAMBDA FUNCTION RESOURCE
# ==========================================
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
      # Un-comment these lines whenever you are ready to pass the MongoDB credentials to your Python environment:
      # MONGO_CONNECTION_STRING = jsondecode(data.aws_secretsmanager_secret_version.mongodb.secret_string)["mongodb_atlas_conn_str"]
      # MONGO_DATABASE          = var.mongo_database

      REPORT_BUCKET        = var.report_bucket
      API_DEBUG_LOG        = var.api_debug_log
      API_GATEWAY_URL      = var.api_gateway_url
      COGNITO_TOKEN_URL    = local.token_url
      COGNITO_CLIENT_ID    = local.target_client_id
      COGNITO_USER_POOL_ID = tolist(data.aws_cognito_user_pools.selected.ids)[0]
      COGNITO_SCOPES       = var.cognito_scopes
      COGNITO_PASSWORD = jsondecode(
        data.aws_secretsmanager_secret_version.cognito_credentials.secret_string
      )["password"]

      COGNITO_USERNAME = jsondecode(
        data.aws_secretsmanager_secret_version.cognito_credentials.secret_string
      )["username"]
      COGNITO_REDIRECT_URI = var.cognito_redirect_uri
    }
  }

  vpc_config {
    subnet_ids = [
      data.aws_subnet.subnet_1.id,
      data.aws_subnet.subnet_2.id,
      data.aws_subnet.subnet_3.id
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
    aws_iam_policy.secrets_manager_policy,
    aws_iam_role_policy_attachment.lambda_vpc_execution
  ]
}