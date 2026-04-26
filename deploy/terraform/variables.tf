variable "region" { type = string default = "us-east-1" }
variable "environment" { type = string }
variable "cluster_name" { type = string default = "simp-prod" }
variable "common_tags" {
  type    = map(string)
  default = { Project = "SIMP", ManagedBy = "Terraform" }
}
variable "vpc_cidr" { type = string default = "10.0.0.0/16" }
variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# EKS
variable "eks_instance_types" { type = list(string) default = ["t3.medium"] }
variable "eks_capacity_type" { type = string default = "ON_DEMAND" }
variable "eks_desired_size" { type = number default = 3 }
variable "eks_min_size" { type = number default = 1 }
variable "eks_max_size" { type = number default = 5 }
variable "kms_key_arn" { type = string default = "" }

# RDS
variable "db_instance_class" { type = string default = "db.t3.medium" }
variable "db_allocated_storage_gb" { type = number default = 50 }
variable "db_name" { type = string default = "simpdb" }
variable "db_username" { type = string default = "simpadmin" }
variable "db_password" { type = string sensitive = true }
variable "db_password_secret_arn" { type = string default = "" }
variable "kms_key_id" { type = string default = "" }

# Broker
variable "broker_image" { type = string }
variable "broker_tag" { type = string default = "latest" }
variable "broker_replicas" { type = number default = 3 }
