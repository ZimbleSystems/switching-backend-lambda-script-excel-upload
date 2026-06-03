# S3 Event Notification Configuration
resource "aws_s3_bucket_notification" "data_bucket_notification" {
  bucket = var.upload_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.excel_ingest_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".xlsx"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}

# Lambda Permission for S3 to invoke the function
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.excel_ingest_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.upload_bucket_name}"
}