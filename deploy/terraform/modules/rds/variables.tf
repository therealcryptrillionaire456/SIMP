variable "environment"              { type = string }
variable "cluster_name"             { type = string }
variable "vpc_id"                   { type = string }
variable "private_subnet_ids"        { type = list(string) }
variable "database_security_group_id" { type = string }
variable "db_instance_class"         { type = string default = "db.t3.medium" }
variable "allocated_storage_gb"      { type = number default = 50 }
variable "db_name"                  { type = string default = "simpdb" }
variable "master_username"           { type = string default = "simpadmin" }
variable "db_password"               { type = string sensitive = true }
variable "db_password_secret_arn"    { type = string default = "" }
variable "kms_key_id"               { type = string default = "" }
variable "tags"                     { type = map(string) default = {} }
