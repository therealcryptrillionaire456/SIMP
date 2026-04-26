variable "environment"        { description = "Environment name" type = string }
variable "cluster_name"        { description = "EKS cluster name" type = string }
variable "vpc_id"             { description = "VPC ID" type = string }
variable "private_subnet_ids"  { description = "Private subnet IDs" type = list(string) }
variable "broker_sg_id"       { description = "Broker security group ID" type = string }
variable "tags"               { description = "Common tags" type = map(string) default = {} }
variable "instance_types"     { description = "EC2 instance types for nodes" type = list(string) default = ["t3.medium"] }
variable "capacity_type"      { description = "SPOT or ON_DEMAND" type = string default = "ON_DEMAND" }
variable "desired_size"       { description = "Desired node count" type = number default = 3 }
variable "min_size"           { description = "Minimum node count" type = number default = 1 }
variable "max_size"           { description = "Maximum node count" type = number default = 5 }
variable "kms_key_arn"        { description = "KMS key ARN for encryption" type = string default = "" }
