# feaststore infrastructure

Terraform for the managed stores feaststore needs in AWS:

- **RDS Postgres** — offline store + registry
- **ElastiCache Redis (replication group)** — online store, TLS in transit + at rest

The serving container itself is deployed separately (ECS/Fargate or k8s); this
module intentionally stops at the stateful pieces and exposes their connection
details as outputs, plus a security group you attach your serving task to via
`allowed_security_group_ids`.

## Usage

```hcl
module "feaststore" {
  source                     = "./terraform"
  environment                = "prod"
  vpc_id                     = "vpc-0abc123"
  private_subnet_ids         = ["subnet-0a", "subnet-0b"]
  db_password                = var.feaststore_db_password  # from a secrets manager
  allowed_security_group_ids = [aws_security_group.serving.id]
}
```

```bash
terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

Wire the outputs into the serving task's environment as `FEASTSTORE_OFFLINE_DSN`
and `FEASTSTORE_ONLINE_REDIS_URL`.

## Notes

- `prod` gets Multi-AZ Postgres, deletion protection, and 14-day backups; lower
  environments trade those for cost and faster teardown.
- State backend is commented out in `versions.tf` — enable the S3 backend before
  using this for anything shared.
