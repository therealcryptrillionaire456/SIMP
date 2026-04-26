# ─────────────────────────────────────────────────────────────────────────────
# T45: Dev Environment
# Single-AZ, minimal resources for local development
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "simp-terraform-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "simp-terraform-locks-dev"
  }
}

module "simp" {
  source = "../../"

  environment = "dev"
  region      = "us-east-1"
  cluster_name = "simp-dev"

  vpc_cidr          = "10.0.0.0/16"
  availability_zones = ["us-east-1a"]

  # EKS (minimal)
  eks_instance_types = ["t3.small"]
  eks_capacity_type  = "ON_DEMAND"
  eks_desired_size   = 1
  eks_min_size       = 1
  eks_max_size       = 2

  # RDS (dev tier)
  db_instance_class    = "db.t3.micro"
  db_allocated_storage_gb = 20
  db_name               = "simpdb_dev"
  db_username           = "simpdev"
  db_password           = "CHANGE_ME_IN_AWS_SECRETS_MANAGER"

  # Broker
  broker_image = "simp-broker:latest"
  broker_replicas = 1

  common_tags = {
    Project = "SIMP"
    Environment = "dev"
    ManagedBy = "Terraform"
    CostCenter = "engineering"
  }
}
