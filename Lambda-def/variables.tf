variable "aws_region" {
  type        = string
  description = "The target AWS region where resources will be deployed."
  default     = "ap-south-1"
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

variable "create_python_layer" {
  type        = bool
  description = "Whether this stack should create and attach the packaged Python dependency layer."
  default     = true
}

variable "vpc_name" {
  type        = string
  description = "The value of the Name tag assigned to your target VPC network."
}

variable "subnet1_name" {
  type        = string
  description = "The value of the Name tag assigned to the first private deployment subnet."
}

variable "subnet2_name" {
  type        = string
  description = "The value of the Name tag assigned to the second private deployment subnet."
}

variable "security_group_name" {
  type        = list(string)
  description = "The list of string values matching the Name tags of your target security groups."
}

variable "mongodb_secret_name" {
  type        = string
  description = "The precise path name of your AWS Secrets Manager secret storing cluster strings."
}

variable "mongo_database" {
  type        = string
  description = "The destination MongoDB cluster database name to execute document insertions."
}

variable "lambda_timeout" {
  type        = number
  description = "The maximum execution processing limit threshold in seconds."
  default     = 180
}

variable "lambda_memory" {
  type        = number
  description = "The absolute allocation pool sizing boundary metric assigned to runtime containers."
  default     = 512
}

variable "upload_bucket_name" {
  type        = string
  description = "The unique name for the S3 bucket serving as the primary ingest target."
}

variable "report_bucket" {
  type        = string
  description = "The unique name for the S3 bucket serving as the analytics report target."
}
