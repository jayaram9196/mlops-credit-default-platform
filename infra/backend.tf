# State backend. Bootstrap the bucket + DynamoDB lock once via `infra/bootstrap/`
# before running `terraform init` here.
#
# Override via -backend-config at init time so the same code can target multiple envs:
#   terraform init \
#     -backend-config="bucket=credit-default-platform-tf-state" \
#     -backend-config="key=envs/staging/terraform.tfstate" \
#     -backend-config="region=us-east-1" \
#     -backend-config="dynamodb_table=credit-default-platform-tf-lock"

terraform {
  backend "s3" {
    # values supplied via -backend-config at init time
    encrypt = true
  }
}
