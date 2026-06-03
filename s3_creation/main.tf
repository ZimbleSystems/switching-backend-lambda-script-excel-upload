resource "aws_s3_bucket" "upload_bucket" {
  bucket = "${var.project_code}-${var.env}-upload-bucket"
  tags = {
    Environment = var.env
    Project     = var.project_code
  }
}

resource "aws_s3_bucket" "report_bucket" {  
  bucket = "${var.project_code}-${var.env}-report-bucket"
  tags = {
    Environment = var.env
    Project     = var.project_code
   }
}

resource "aws_s3_bucket_public_access_block" "upload_bucket_public_access_block" {
  bucket = aws_s3_bucket.upload_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "report_bucket_public_access_block" {
  bucket = aws_s3_bucket.report_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "upload_bucket_versioning" {
  bucket = aws_s3_bucket.upload_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "report_bucket_versioning" {
  bucket = aws_s3_bucket.report_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}