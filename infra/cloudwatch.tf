resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/credit-default-platform/${var.environment}/api"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-batch-scorer"
  retention_in_days = 30
  tags              = local.common_tags
}

# Alarm: API error rate (driven by Prometheus metrics scraped + remote-written
# to CloudWatch by adot, OR by the API's structured logs subscription filter).
# The metric is created lazily by `aws_cloudwatch_log_metric_filter` below.
resource "aws_cloudwatch_log_metric_filter" "api_errors" {
  name           = "${local.name_prefix}-api-errors"
  pattern        = "{ ($.level = \"error\") }"
  log_group_name = aws_cloudwatch_log_group.api.name

  metric_transformation {
    name      = "ApiErrors"
    namespace = "CreditDefault/${var.environment}"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.name_prefix}-api-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApiErrors"
  namespace           = "CreditDefault/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_description   = "API has logged > 5 errors in 5 minutes"
  tags                = local.common_tags
}
