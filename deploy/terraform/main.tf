# ─────────────────────────────────────────────────────────────────────────────
# T45: SIMP Root Module — orchestrates all sub-modules
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws        = { source  = "hashicorp/aws"        version = "~> 5.0" }
    kubernetes = { source  = "hashicorp/kubernetes"  version = "~> 2.0" }
    helm       = { source  = "hashicorp/helm"        version = "~> 2.0" }
  }

  # State stored in S3 with DynamoDB locking (per-environment)
  backend "s3" {
    encrypt = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = var.common_tags
  }
}

provider "kubernetes" {
  host                   = var.eks_cluster_endpoint
  cluster_ca_certificate = base64decode(var.eks_cluster_ca_cert)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
    command      = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = var.eks_cluster_endpoint
    cluster_ca_certificate = base64decode(var.eks_cluster_ca_cert)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
      command      = "aws"
    }
  }
}

# ── Data Sources ──────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

# ── Module Calls ───────────────────────────────────────────────────────────────

module "network" {
  source = "./modules/network"

  environment       = var.environment
  region            = var.region
  vpc_cidr          = var.vpc_cidr
  availability_zones = var.availability_zones
  tags              = var.common_tags
}

module "eks" {
  source = "./modules/eks"

  environment       = var.environment
  cluster_name      = var.cluster_name
  vpc_id            = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  broker_sg_id      = module.network.broker_security_group_id
  instance_types    = var.eks_instance_types
  capacity_type     = var.eks_capacity_type
  desired_size      = var.eks_desired_size
  min_size          = var.eks_min_size
  max_size          = var.eks_max_size
  kms_key_arn       = var.kms_key_arn
  tags              = var.common_tags
}

module "rds" {
  source = "./modules/rds"

  environment              = var.environment
  cluster_name             = var.cluster_name
  vpc_id                   = module.network.vpc_id
  private_subnet_ids        = module.network.private_subnet_ids
  database_security_group_id = module.network.database_security_group_id
  db_instance_class        = var.db_instance_class
  allocated_storage_gb     = var.db_allocated_storage_gb
  db_name                  = var.db_name
  master_username          = var.db_username
  db_password              = var.db_password
  db_password_secret_arn   = var.db_password_secret_arn
  kms_key_id               = var.kms_key_id
  tags                     = var.common_tags

  depends_on = [module.eks]
}

module "vault" {
  source = "./modules/vault"

  environment          = var.environment
  cluster_name         = module.eks.cluster_name
  eks_cluster_endpoint = module.eks.cluster_endpoint
  eks_cluster_ca_cert  = module.eks.cluster_ca_cert
  vpc_id              = module.network.vpc_id
  private_subnet_ids   = module.network.private_subnet_ids
  broker_sg_id        = module.network.broker_security_group_id
  region              = var.region
  tags                = var.common_tags

  depends_on = [module.eks]
}

module "broker" {
  source = "./modules/broker"

  environment         = var.environment
  cluster_name        = module.eks.cluster_name
  eks_cluster_endpoint = module.eks.cluster_endpoint
  eks_cluster_ca_cert  = module.eks.cluster_ca_cert
  broker_image        = var.broker_image
  broker_tag          = var.broker_tag
  broker_replicas     = var.broker_replicas
  vault_addr          = "http://vault.vault.svc.cluster.local:8200"
  db_host             = module.rds.rds_endpoint
  db_name             = var.db_name
  tags                = var.common_tags

  depends_on = [module.vault, module.rds]
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "environment"     { value = var.environment }
output "vpc_id"          { value = module.network.vpc_id }
output "cluster_name"    { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "db_host"         { value = module.rds.rds_endpoint }
output "db_port"         { value = module.rds.rds_port }
output "vault_addr"      { value = "http://vault.vault.svc.cluster.local:8200" }
output "broker_url"      { value = module.broker.broker_service_url }
output "account_id"      { value = data.aws_caller_identity.current.account_id }
