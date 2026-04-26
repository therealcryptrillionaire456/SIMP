variable "environment"         { type = string }
variable "cluster_name"        { type = string }
variable "eks_cluster_endpoint" { type = string }
variable "eks_cluster_ca_cert"  { type = string }
variable "broker_image"         { type = string }
variable "broker_tag"          { type = string default = "latest" }
variable "broker_replicas"      { type = number default = 3 }
variable "vault_addr"          { type = string }
variable "db_host"             { type = string }
variable "db_name"             { type = string }
variable "tags"               { type = map(string) default = {} }
