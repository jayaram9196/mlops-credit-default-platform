environment = "staging"
aws_region  = "us-east-1"
vpc_cidr    = "10.20.0.0/16"
azs         = ["us-east-1a", "us-east-1b", "us-east-1c"]
eks_version = "1.30"

# Smaller footprint for staging — cost control.
node_instance_types = ["t3.medium"]
node_desired_size   = 2
node_min_size       = 2
node_max_size       = 4
