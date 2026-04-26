# T45: SIMP Infrastructure as Code (Terraform)

## Structure

```
deploy/terraform/
├── main.tf                    # Root module (calls all sub-modules)
├── variables.tf               # Input variables
├── modules/
│   ├── network/               # VPC, subnets, NAT GWs, security groups
│   ├── eks/                  # EKS cluster + managed node group
│   ├── rds/                   # RDS PostgreSQL with parameter group
│   ├── vault/                 # HashiCorp Vault on EKS (DynamoDB HA)
│   └── broker/               # SIMP broker Helm release + HPA/PDB
├── environments/
│   ├── dev/                   # Dev environment (single-AZ, minimal)
│   └── prod/                  # Prod (multi-AZ, HA, SOC2-ready)
```

## Quick Start

### 1. Configure backend (one-time per account)

```bash
# Dev
aws s3 mb s3://simp-terraform-state-dev
aws dynamodb create-table --table-name simp-terraform-locks-dev \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Prod
aws s3 mb s3://simp-terraform-state-prod
aws dynamodb create-table --table-name simp-terraform-locks-prod \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 2. Initialize & plan

```bash
cd deploy/terraform/environments/dev
terraform init
terraform plan -var-file=../../variables.tf
```

### 3. Apply

```bash
terraform apply -var-file=../../variables.tf
```

## Secrets Management

- DB password: Store in AWS Secrets Manager or HashiCorp Vault
- Broker image: Push to ECR before apply
- Vault unseal keys: Store securely; use AWS SSM Parameter Store or Vault Auto-unseal with AWS KMS

## Modules

| Module | Purpose |
|--------|---------|
| `network` | VPC, public/private subnets, NAT GWs, security groups |
| `eks` | EKS cluster with managed node group, IAM roles |
| `rds` | RDS PostgreSQL 16 with parameter group, monitoring |
| `vault` | HashiCorp Vault on EKS with DynamoDB HA backend |
| `broker` | SIMP broker Helm chart + HPA + PodDisruptionBudget |

## Outputs

After apply, Terraform outputs:
- `broker_url` — LoadBalancer URL for SIMP broker
- `db_host` / `db_port` — PostgreSQL connection endpoint
- `vault_addr` — Internal Vault service address
- `cluster_endpoint` — EKS API server endpoint
