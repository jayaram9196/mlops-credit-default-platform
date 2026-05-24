output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC ID"
}

output "private_subnet_ids" {
  value       = module.vpc.private_subnets
  description = "Private subnet IDs (EKS nodes + Lambda live here)"
}

output "cluster_name" {
  value       = module.eks.cluster_name
  description = "EKS cluster name"
}

output "cluster_endpoint" {
  value       = module.eks.cluster_endpoint
  description = "EKS API endpoint"
}

output "cluster_oidc_issuer_url" {
  value       = module.eks.cluster_oidc_issuer_url
  description = "OIDC issuer URL — needed for IRSA"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "ECR repo URL for the API image"
}

output "data_bucket_name" {
  value       = aws_s3_bucket.data.bucket
  description = "S3 bucket holding raw + processed data"
}

output "artifacts_bucket_name" {
  value       = aws_s3_bucket.artifacts.bucket
  description = "S3 bucket holding MLflow artifacts + model registry blobs"
}

output "api_irsa_role_arn" {
  value       = aws_iam_role.api_irsa.arn
  description = "IRSA role for the credit-default-api pod"
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "ARN to use in GitHub Actions `aws-actions/configure-aws-credentials`"
}

output "lambda_scorer_function_name" {
  value       = aws_lambda_function.batch_scorer.function_name
  description = "Lambda function name for S3-triggered batch scoring"
}

output "kubeconfig_command" {
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
  description = "Command to populate ~/.kube/config for this cluster"
}
