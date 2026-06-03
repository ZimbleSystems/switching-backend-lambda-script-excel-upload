terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Remote State Backend Configuration
  backend "s3" {
    bucket       = "publiccentralsouthtestbucket"
    key          = "lambda/excel-ingest-service/terraform.tfstate"
    region       = "ap-south-1"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  # Global default tags. This automatically tags your S3 buckets, Lambdas, and IAM roles!
  default_tags {
    tags = merge(var.tags, {
      Environment = var.env
      Project     = var.project_code
      ManagedBy   = "Terraform"
    })
  }
}