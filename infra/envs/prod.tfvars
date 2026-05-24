environment = "prod"
aws_region  = "us-east-1"
vpc_cidr    = "10.30.0.0/16"
azs         = ["us-east-1a", "us-east-1b", "us-east-1c"]
eks_version = "1.30"

# Production sized for ~100 RPS sustained + headroom.
node_instance_types = ["m6i.large"]
node_desired_size   = 3
node_min_size       = 3
node_max_size       = 10
