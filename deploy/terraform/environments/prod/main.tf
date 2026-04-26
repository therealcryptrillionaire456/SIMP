# ─────────────────────────────────────────────────────────────────────────────
# T45: Prod Environment
# Multi-AZ, HA, production-grade
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "simp-terraform-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "simp-terraform-locks-prod"
  }
}

module "simp" {
  source = "../../"

  environment = "prod"
  region      = "us-east-1"
  cluster_name = "simp-prod"

  vpc_cidr          = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

  # EKS (HA)
  eks_instance_types = ["t3.medium", "t3.large"]
  eks_capacity_type  = "SPOT"
  eks_desired_size   = 3
  eks_min_size       = 2
  eks_max_size       = 10
  kms_key_arn       = "arn:aws:kms:us-east-1:ACCOUNT_ID:key/YOUR_KEY_ID"

  # RDS (prod tier)
  db_instance_class    = "db.r6g.large"
  db_allocated_storage_gb = 200
  db_name               = "simpdb"
  db_username           = "simpprod"
  db_password           = "CHANGE_ME_IN_AWS_SECRETS_MANAGER"  # from Vault
  db_password_secret_arn = "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:simp/prod/db-password"

  # Broker (HA)
  broker_image     = "simp-broker:1.0.0"
  broker_replicas  = 3

  common_tags = {
    Project = "SIMP"
    Environment = "prod"
    ManagedBy = "Terraform"
    CostCenter = "production"
    Compliance = "SOC2"
  }
}
