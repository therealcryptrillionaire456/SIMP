# ─────────────────────────────────────────────────────────────────────────────
# T45: Broker Module — SIMP broker on EKS with Helm
# ─────────────────────────────────────────────────────────────────────────────

variable "environment"         { type = string }
variable "cluster_name"         { type = string }
variable "eks_cluster_endpoint"  { type = string }
variable "eks_cluster_ca_cert"   { type = string }
variable "broker_image"          { type = string }
variable "broker_replicas"       { type = number default = 3 }
variable "vault_addr"            { type = string }
variable "db_host"              { type = string }
variable "db_name"              { type = string }
variable "tags"                { type = map(string) default = {} }

locals {
  project_tag = merge(var.tags, { Project = "SIMP", Environment = var.environment })
}

# ── K8s Provider ─────────────────────────────────────────────────────────────

data "terraform_remote_state" "network" {
  backend = "local"
  config = {
    path = "terraform.tfstate"
  }
  workspace = var.environment
}

# ── Kubernetes ConfigMap ──────────────────────────────────────────────────────

resource "kubernetes_config_map" "simp_env" {
  metadata {
    name      = "simp-broker-env"
    namespace = "simp"
    labels    = { app = "simp-broker" }
  }

  data = {
    SIMP_ENV           = var.environment
    VAULT_ADDR         = var.vault_addr
    DB_HOST            = var.db_host
    DB_NAME            = var.db_name
    LOG_LEVEL          = var.environment == "prod" ? "INFO" : "DEBUG"
    HEALTH_CHECK_SECONDS = "30"
    MAX_AGENTS         = "100"
  }
}

# ── Helm Release ─────────────────────────────────────────────────────────────

resource "helm_release" "simp_broker" {
  name       = "simp-broker"
  chart      = "../../helm/simp-broker"
  namespace  = "simp"
  version    = "0.1.0"

  set {
    name  = "image.repository"
    value = var.broker_image
  }
  set {
    name  = "image.tag"
    value = var.broker_tag
  }
  set {
    name  = "replicaCount"
    value = var.broker_replicas
  }
  set {
    name  = "service.type"
    value = "LoadBalancer"
  }
  set {
    name  = "service.port"
    value = "5555"
  }
  set {
    name  = "env.SIMP_ENV"
    value = var.environment
  }
  set {
    name  = "env.VAULT_ADDR"
    value = var.vault_addr
  }
  set {
    name  = "env.DB_HOST"
    value = var.db_host
  }
  set {
    name  = "resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "resources.requests.memory"
    value = "256Mi"
  }
  set {
    name  = "resources.limits.cpu"
    value = "2000m"
  }
  set {
    name  = "resources.limits.memory"
    value = "4Gi"
  }
}

# ── HPA ──────────────────────────────────────────────────────────────────────

resource "kubernetes_horizontal_pod_autoscaler_v2" "simp_broker" {
  metadata {
    name      = "simp-broker-hpa"
    namespace = "simp"
  }

  spec {
    min_replicas = 1
    max_replicas = 10

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = "simp-broker"
    }

    metrics {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type               = "Utilization"
          average_utilization = 70
        }
      }
    }
    metrics {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type               = "Utilization"
          average_utilization = 80
        }
      }
    }
  }
}

# ── PDB ──────────────────────────────────────────────────────────────────────

resource "kubernetes_pod_disruption_budget" "simp_broker" {
  metadata {
    name      = "simp-broker-pdb"
    namespace = "simp"
  }

  spec {
    max_unavailable = var.environment == "prod" ? 1 : "50%"

    selector {
      match_labels = {
        app = "simp-broker"
      }
    }
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "broker_service_url" {
  description = "LoadBalancer URL for the SIMP broker"
  value       = "http://${kubernetes_service.simp_broker.load_balancer[0].hostname}:5555"
}

output "broker_deployment_name" {
  value = "simp-broker"
}

output "hpa_min_replicas" { value = 1 }
output "hpa_max_replicas" { value = 10 }
