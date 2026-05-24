locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
  }

  # EKS managed node group + cluster authentication
  cluster_name = "${local.name_prefix}-eks"

  # GitHub OIDC subject pattern that the deploy role will trust
  github_oidc_subjects = [
    "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main",
    "repo:${var.github_org}/${var.github_repo}:ref:refs/tags/v*",
    "repo:${var.github_org}/${var.github_repo}:environment:staging",
    "repo:${var.github_org}/${var.github_repo}:environment:prod",
  ]
}
