variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging | prod)"
  type        = string
  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be one of: staging, prod."
  }
}

variable "project" {
  description = "Resource-name prefix"
  type        = string
  default     = "credit-default-platform"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones to span"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "eks_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.30"
}

variable "node_instance_types" {
  description = "EC2 instance types for the EKS managed node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "node_desired_size" {
  description = "Desired EKS node count"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum EKS node count"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum EKS node count"
  type        = number
  default     = 6
}

variable "github_org" {
  description = "GitHub org / user owning the repo (for OIDC trust)"
  type        = string
  default     = "jayaram9196"
}

variable "github_repo" {
  description = "GitHub repo name (for OIDC trust)"
  type        = string
  default     = "mlops-credit-default-platform"
}

variable "image_tag_default" {
  description = "Default image tag the SageMaker training job and Lambda will reference"
  type        = string
  default     = "latest"
}
