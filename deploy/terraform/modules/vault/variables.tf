variable "environment"          { type = string }
variable "cluster_name"         { type = string }
variable "eks_cluster_endpoint" { type = string }
variable "eks_cluster_ca_cert"  { type = string }
variable "vpc_id"              { type = string }
variable "private_subnet_ids"    { type = list(string) }
variable "broker_sg_id"         { type = string }
variable "region"               { type = string default = "us-east-1" }
variable "tags"                { type = map(string) default = {} }
