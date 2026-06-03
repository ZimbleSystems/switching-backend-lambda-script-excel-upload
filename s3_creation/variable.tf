variable "env" {
  description = "The environment for the S3 bucket"
  type        = string
}

variable "project_code" {
  description = "The project code for the S3 bucket"
  type        = string
}

variable "tags" {
  description = "Tags for the S3 bucket"
  type        = map(string)
    default     = {}
}

variable "aws_region" {
  type        = string
  description = "The target AWS region where resources will be deployed."
}