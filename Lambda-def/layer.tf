resource "aws_lambda_layer_version" "python_layer" {
  filename                 = "${path.module}/../layer/python.zip"
  layer_name               = "${var.project_code}-${var.env}-excel-ingest-dependencies"
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["arm64"]

  # Tracks changes to your zip file automatically
  source_code_hash = filebase64sha256("${path.module}/../layer/python.zip")
}
