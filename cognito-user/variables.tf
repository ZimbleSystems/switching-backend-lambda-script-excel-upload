variable "aws_region" {
  type        = string
  description = "The target AWS region where resources will be deployed."
}

variable "env" {
  type        = string
  description = "The deployment environment name (e.g., dev, staging, prod)."
}

variable "project_code" {
  type        = string
  description = "The project code prefix used to maintain unique resource names."
}

variable "tags" {
  type        = map(string)
  description = "A collection of custom resource tags to merge with global defaults."
  default     = {}
}

variable "user_pool_name" {
  type        = string
  description = "The name of the existing Cognito User Pool to integrate with."
}

variable "username" {
  type        = string
  description = "Cognito username"
}

variable "modules" {
  type        = string
  description = "Value for custom:modules"
}

variable "tenant_id" {
  type        = string
  description = "Value for custom:tenantId"
}

variable "group_name" {
  type        = string
  description = "Existing Cognito group name"
}

variable "email" {
  type = string
}