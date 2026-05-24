# Terraform state bootstrap

This stack provisions the **remote-state S3 bucket + DynamoDB lock table** that
`infra/` depends on. Run it **once per AWS account** before the main stack.

```bash
cd infra/bootstrap
terraform init
terraform apply -auto-approve
```

After it completes, plug the outputs into the main stack's `-backend-config`:

```bash
cd ../          # back into infra/

terraform init \
  -backend-config="bucket=credit-default-platform-tf-state" \
  -backend-config="key=envs/staging/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=credit-default-platform-tf-lock"
```

State for this bootstrap stack is stored locally (`terraform.tfstate` next to
the .tf files). Commit it to a private repo or delete it after — chicken &
egg: we can't store the bucket-creating state in the bucket it's creating.
