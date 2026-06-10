data "aws_cognito_user_pools" "selected" {
  name = var.user_pool_name
}

data "aws_cognito_user_pool" "pool_details" {
  user_pool_id = tolist(data.aws_cognito_user_pools.selected.ids)[0]
}

resource "random_password" "user_password" {
  length           = 12
  special          = true
  override_special = "@"

  min_upper   = 1
  min_lower   = 1
  min_numeric = 1
  min_special = 1
}

locals {
  username = var.username
}

resource "aws_cognito_user" "user" {
  user_pool_id = data.aws_cognito_user_pool.pool_details.id
  username     = var.username

  password = random_password.user_password.result

  attributes = {
    email             = var.email
    "custom:modules"  = var.modules
    "custom:tenantId" = var.tenant_id
  }
}

resource "aws_cognito_user_in_group" "all_access" {
  user_pool_id = data.aws_cognito_user_pool.pool_details.id
  username     = aws_cognito_user.user.username
  group_name   = var.group_name
}

resource "aws_secretsmanager_secret" "cognito_credentials" {
  name                    = "${var.project_code}/${var.env}/cognito/${local.username}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cognito_credentials" {
  secret_id = aws_secretsmanager_secret.cognito_credentials.id

  secret_string = jsonencode({
    username   = var.username
    password   = random_password.user_password.result
    email      = var.email
    tenant_id  = var.tenant_id
    modules    = var.modules
    group_name = var.group_name
    user_pool  = data.aws_cognito_user_pool.pool_details.name
  })
}