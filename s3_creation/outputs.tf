output "upload_bucket_id" {
  description = "The ID of the S3 upload bucket"
  value       = aws_s3_bucket.upload_bucket.id
}

output "report_bucket_id" {
  description = "The ID of the S3 report bucket"
  value       = aws_s3_bucket.report_bucket.id
}

output "upload_bucket_arn" {
  description = "The ARN of the S3 upload bucket"
  value       = aws_s3_bucket.upload_bucket.arn
}

output "report_bucket_arn" {
  description = "The ARN of the S3 report bucket"
  value       = aws_s3_bucket.report_bucket.arn
}