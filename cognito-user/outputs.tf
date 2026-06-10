output "user_pool_id" {
  value = data.aws_cognito_user_pool.pool_details.id
}

output "secret_arn" {
  value = aws_secretsmanager_secret.cognito_credentials.arn
}

output "username" {
  value = local.username
}

output "generated_password" {
  value     = random_password.user_password.result
  sensitive = true
}