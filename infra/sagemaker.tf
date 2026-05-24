# SageMaker training role + model + endpoint config. This is the AWS-native
# alternate training path called out in the JD: the same training code runs on
# EKS day-to-day, with a SageMaker job available for big-data retrains.

data "aws_iam_policy_document" "sagemaker_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker_training" {
  name               = "${local.name_prefix}-sagemaker-training"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_trust.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "sagemaker_training_permissions" {
  statement {
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.data.arn,
      "${aws_s3_bucket.data.arn}/*",
    ]
  }
  statement {
    actions = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"]
    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/sagemaker/*"]
  }
  statement {
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sagemaker_training" {
  name   = "${local.name_prefix}-sagemaker-training-inline"
  role   = aws_iam_role.sagemaker_training.id
  policy = data.aws_iam_policy_document.sagemaker_training_permissions.json
}

# A reusable SageMaker model definition that points at the latest training
# image — actual training jobs are launched by the retraining DAG (Phase 7).
resource "aws_sagemaker_model" "training" {
  name               = "${local.name_prefix}-training-model"
  execution_role_arn = aws_iam_role.sagemaker_training.arn

  primary_container {
    image          = "${aws_ecr_repository.api.repository_url}:${var.image_tag_default}"
    model_data_url = "s3://${aws_s3_bucket.artifacts.bucket}/sagemaker/training/model.tar.gz"
  }

  tags = local.common_tags

  lifecycle {
    # we expect the image tag to roll forward outside Terraform
    ignore_changes = [primary_container]
  }
}
