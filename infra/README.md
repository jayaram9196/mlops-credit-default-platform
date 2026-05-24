# Terraform — credit-default-platform AWS infra

Provisions the full AWS footprint that Phases 4–7 need: VPC, EKS, ECR, S3, IAM
(IRSA + GitHub OIDC), CloudWatch log groups + alarms, SageMaker training role,
and the S3-triggered Lambda batch scorer.

## Layout

```
infra/
  versions.tf       provider versions + default_tags
  backend.tf        S3 + DynamoDB remote state (config via -backend-config)
  variables.tf      typed inputs
  locals.tf         derived names / OIDC subjects
  outputs.tf        cluster endpoint, role ARNs, bucket names, etc.

  vpc.tf            terraform-aws-modules/vpc/aws — 3 AZs, private+public+intra
  eks.tf            terraform-aws-modules/eks/aws — managed node group + addons
  ecr.tf            ECR repo for the API image + lifecycle policy
  s3.tf             data + artifacts buckets, versioning + SSE + lifecycle
  iam.tf            IRSA role for the pod + GitHub Actions OIDC deploy role
  cloudwatch.tf     log groups + metric filter + error-rate alarm
  sagemaker.tf      training role + model (AWS-native alternate training path)
  lambda.tf         S3-triggered batch scorer (invokes SageMaker endpoint)
  lambda/scorer.py  Lambda handler source

  envs/
    staging.tfvars  staging overrides (smaller nodes, single NAT)
    prod.tfvars     prod overrides (m6i.large nodes, NAT per AZ)

  bootstrap/        one-time state-bucket + lock-table stack
    main.tf
    README.md
```

## Modules used (community)

- `terraform-aws-modules/vpc/aws` — VPC, subnets, NAT, route tables.
- `terraform-aws-modules/eks/aws` — cluster, OIDC provider, managed node group, core addons.

Everything else is custom code so the IAM and S3 stories stay explicit.

## End-to-end provisioning

```bash
# 0) one-time per account: create the state bucket + lock table
cd infra/bootstrap
terraform init
terraform apply -auto-approve
cd ..

# 1) init with remote backend
terraform init \
  -backend-config="bucket=credit-default-platform-tf-state" \
  -backend-config="key=envs/staging/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=credit-default-platform-tf-lock"

# 2) plan + apply staging
terraform plan  -var-file=envs/staging.tfvars
terraform apply -var-file=envs/staging.tfvars

# 3) point kubectl at the new cluster
$(terraform output -raw kubeconfig_command)

# 4) install the API via the Helm chart from Phase 4
helm upgrade --install credit-default-api ../k8s/helm/credit-default-api \
  -n credit-default --create-namespace \
  --set image.repository=$(terraform output -raw ecr_repository_url) \
  --set image.tag=sha-<git-sha> \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$(terraform output -raw api_irsa_role_arn) \
  --set modelInit.enabled=true \
  --set modelInit.modelUri=s3://$(terraform output -raw artifacts_bucket_name)/models/staging/

# 5) teardown
terraform destroy -var-file=envs/staging.tfvars
```

## Cost note

This is a **portfolio blueprint**, not a permanent deployment. EKS control
plane is ~$73/month. NAT gateway is ~$32/month/AZ. Run `terraform destroy`
between demos.

For zero-cost validation: `terraform validate` and `terraform fmt -check` cover
the code quality story without spending anything. The CI workflow in
`.github/workflows/` already runs these on every PR.

## GitHub Actions wiring (after first apply)

Once the OIDC provider + deploy role exist, plug the ARN into the
`build-deploy.yml` deploy step (currently commented out):

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/credit-default-platform-staging-gha-deploy
    aws-region: us-east-1
```

The role's trust policy already allows the `main` branch + `staging` and
`prod` GitHub Environments.
