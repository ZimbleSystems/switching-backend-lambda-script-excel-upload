output "vpc_id" {
  value       = data.aws_vpc.selected.id
  description = "The target AWS infrastructure network identifier resolved via Name Tag."
}

output "subnet_ids" {
  value = [
    data.aws_subnet.subnet_1.id,
    data.aws_subnet.subnet_2.id
  ]
  description = "The target decoupled private routing subnet execution footprints."
}

output "security_group_id" {
  value       = data.aws_security_group.selected.id
  description = "The security group identifier used to firewall execution boundaries."
}

output "lambda_function_arn" {
  value       = aws_lambda_function.excel_ingest_lambda.arn
  description = "The execution target registry tracking the deployment package compute handler."
}

output "lambda_layer_arn" {
  value       = aws_lambda_layer_version.python_layer.arn
  description = "The dependency layers container registry footprint delivering custom binaries."
}