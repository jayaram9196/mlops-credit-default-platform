# S3-triggered batch scorer. Files dropped into s3://<data>/batch/incoming/
# trigger this Lambda, which scores the rows by invoking the SageMaker endpoint
# (or, fallback, the API's batch endpoint) and writes results to
# s3://<artifacts>/batch/scored/.

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_scorer" {
  name               = "${local.name_prefix}-lambda-scorer"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_exec" {
  role       = aws_iam_role.lambda_scorer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_scorer_permissions" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/batch/incoming/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/batch/scored/*"]
  }
  statement {
    actions   = ["sagemaker:InvokeEndpoint"]
    resources = ["arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.name_prefix}-*"]
  }
}

resource "aws_iam_role_policy" "lambda_scorer" {
  name   = "${local.name_prefix}-lambda-scorer-inline"
  role   = aws_iam_role.lambda_scorer.id
  policy = data.aws_iam_policy_document.lambda_scorer_permissions.json
}

# Package the handler. In production, replace with a versioned zip published by CI.
data "archive_file" "lambda_scorer" {
  type        = "zip"
  source_file = "${path.module}/lambda/scorer.py"
  output_path = "${path.module}/lambda/scorer.zip"
}

resource "aws_lambda_function" "batch_scorer" {
  function_name    = "${local.name_prefix}-batch-scorer"
  role             = aws_iam_role.lambda_scorer.arn
  handler          = "scorer.handler"
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 512
  filename         = data.archive_file.lambda_scorer.output_path
  source_code_hash = data.archive_file.lambda_scorer.output_base64sha256

  environment {
    variables = {
      ARTIFACTS_BUCKET   = aws_s3_bucket.artifacts.bucket
      SAGEMAKER_ENDPOINT = "${local.name_prefix}-staging"
      LOG_LEVEL          = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = local.common_tags
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.batch_scorer.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data.arn
}

resource "aws_s3_bucket_notification" "data_incoming" {
  bucket = aws_s3_bucket.data.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.batch_scorer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "batch/incoming/"
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}
