# ─────────────────────────────────────────────────────────────────────────────
# T45: Vault Module — HashiCorp Vault on EKS with DynamoDB HA backend
# ─────────────────────────────────────────────────────────────────────────────

variable "environment"           { type = string }
variable "cluster_name"          { type = string }
variable "eks_cluster_endpoint"  { type = string }
variable "eks_cluster_ca_cert"   { type = string }
variable "vpc_id"               { type = string }
variable "private_subnet_ids"     { type = list(string) }
variable "broker_sg_id"          { type = string }
variable "tags"                 { type = map(string) default = {} }

locals {
  project_tag = merge(var.tags, { Project = "SIMP", Environment = var.environment })
}

# ── DynamoDB Table (HA backend) ───────────────────────────────────────────────

resource "aws_dynamodb_table" "vault_ha" {
  name           = "simp-${var.environment}-vault-ha"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "Path"
  range_key      = "Key"

  attribute {
    name = "Path"
    type = "S"
  }
  attribute {
    name = "Key"
    type = "S"
  }

  point_in_time_recovery = var.environment == "prod"

  server_side_encryption {
    enabled = true
  }

  ttl {
    attribute_name = "Expires"
    enabled        = false
  }

  tags = local.project_tag
}

# ── S3 Bucket (audit logs) ───────────────────────────────────────────────────

resource "aws_s3_bucket" "vault_audit" {
  bucket = "simp-${var.environment}-vault-audit-logs"

  tags = local.project_tag
}

resource "aws_s3_bucket_versioning" "vault_audit" {
  bucket = aws_s3_bucket.vault_audit.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vault_audit" {
  bucket = aws_s3_bucket.vault_audit.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "vault_audit" {
  bucket = aws_s3_bucket.vault_audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Vault Namespace (Kubernetes) ─────────────────────────────────────────────

resource "kubernetes_namespace" "vault" {
  metadata {
    name = "vault"
    labels = {
      app = "hashicorp-vault"
      environment = var.environment
    }
  }

  depends_on = [aws_eks_cluster.simp]
}

# ── Vault Helm Release ─────────────────────────────────────────────────────────

resource "helm_release" "vault" {
  name       = "simp-vault"
  chart      = "hashicorp/vault"
  namespace  = kubernetes_namespace.vault.metadata[0].name
  version    = "0.27.0"

  set {
    name  = "server.image.tag"
    value = "1.16.2"
  }
  set {
    name  = "server.ha.enabled"
    value = "true"
  }
  set {
    name  = "server.ha.replicas"
    value = "3"
  }
  set {
    name  = "server.ha.raft.enabled"
    value = "false"
  }
  set {
    name  = "server.dataStorage.enabled"
    value = "true"
  }
  set {
    name  = "server.dataStorage.size"
    value = "10Gi"
  }
  set {
    name  = "server.dataStorage.storageClass"
    value = "gp3"
  }
  set {
    name  = "injector.enabled"
    value = "false"
  }
  set {
    name  = "server.route.enabled"
    value = "false"
  }
  set {
    name  = "ui.enabled"
    value = "false"
  }

  values = [<<-EOF
server:
  ha:
    config: |
      ui = false
      listener "tcp" {
        tls_disable = true
        address = "[::]:8200"
        cluster_address = "[::]:8201"
      }
      storage "dynamodb" {
        table = "${aws_dynamodb_table.vault_ha.name}"
        region = "${var.region}"
        read_capacity = 5
        write_capacity = 5
      }
      service_registration "kubernetes" {}
  standalone:
    enabled = false
EOF
  ]

  depends_on = [kubernetes_namespace.vault]
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "dynamodb_table_name" { value = aws_dynamodb_table.vault_ha.name }
output "vault_audit_bucket"  { value = aws_s3_bucket.vault_audit.bucket }
output "vault_namespace"      { value = kubernetes_namespace.vault.metadata[0].name }
