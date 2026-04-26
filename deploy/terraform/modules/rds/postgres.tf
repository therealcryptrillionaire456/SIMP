# ─────────────────────────────────────────────────────────────────────────────
# T45: RDS Module — Managed PostgreSQL for SIMP state
# ─────────────────────────────────────────────────────────────────────────────

variable "environment"              { type = string }
variable "cluster_name"             { type = string }
variable "vpc_id"                   { type = string }
variable "private_subnet_ids"        { type = list(string) }
variable "database_security_group_id" { type = string }
variable "db_instance_class"         { type = string default = "db.t3.medium" }
variable "allocated_storage_gb"      { type = number default = 50 }
variable "db_name"                  { type = string default = "simpdb" }
variable "master_username"           { type = string default = "simpadmin" }
variable "tags"                     { type = map(string) default = {} }

locals {
  project_tag = merge(var.tags, { Project = "SIMP", Environment = var.environment })
}

# ── DBSubnet Group ────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "simp_rds" {
  name       = "simp-${var.environment}-rds-subnet"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-rds-subnet" })
}

# ── RDS Instance ─────────────────────────────────────────────────────────────

resource "aws_db_instance" "simp_postgres" {
  identifier           = "simp-${var.environment}-postgres"
  instance_class       = var.db_instance_class
  allocated_storage    = var.allocated_storage_gb
  storage_type         = "gp3"
  engine               = "postgres"
  engine_version       = "16.2"
  db_name              = var.db_name
  username             = var.master_username
  password             = var.db_password  # from Vault
  parameter_group_name = "simp-${var.environment}-pg16"
  license_model        = "postgresql-license"
  publicly_accessible  = false
  vpc_security_group_ids = [var.database_security_group_id]
  db_subnet_group_name   = aws_db_subnet_group.simp_rds.name

  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"

  skip_final_snapshot    = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "simp-${var.environment}-final-snapshot" : null

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  storage_encrypted   = true
  kms_key_id          = var.kms_key_id

  monitoring_interval  = 60
  monitoring_role_arn  = aws_iam_role.rds_monitoring_role.arn

  tags = local.project_tag

  timeouts {
    create = "60m"
    update = "80m"
    delete = "40m"
  }
}

# ── Parameter Group ──────────────────────────────────────────────────────────

resource "aws_db_parameter_group" "simp_pg16" {
  name   = "simp-${var.environment}-pg16"
  family = "postgres16"

  parameter {
    name  = "max_connections"
    value = "500"
  }
  parameter {
    name  = "shared_buffers"
    value = "256MB"
  }
  parameter {
    name  = "effective_cache_size"
    value = "768MB"
  }
  parameter {
    name  = "maintenance_work_mem"
    value = "256MB"
  }
  parameter {
    name  = "checkpoint_completion_target"
    value = "0.9"
  }
  parameter {
    name  = "wal_buffers"
    value = "16MB"
  }
  parameter {
    name  = "default_statistics_target"
    value = "100"
  }
  parameter {
    name  = "random_page_cost"
    value = "1.1"
  }
  parameter {
    name  = "effective_io_concurrency"
    value = "200"
  }
  parameter {
    name  = "work_mem"
    value = "4MB"
  }
  parameter {
    name  = "min_wal_size"
    value = "1GB"
  }
  parameter {
    name  = "max_wal_size"
    value = "4GB"
  }

  tags = local.project_tag
}

# ── Monitoring Role ───────────────────────────────────────────────────────────

resource "aws_iam_role" "rds_monitoring_role" {
  name = "simp-${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  role       = aws_iam_role.rds_monitoring_role.name
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "rds_endpoint"   { value = aws_db_instance.simp_postgres.endpoint }
output "rds_port"       { value = aws_db_instance.simp_postgres.port }
output "rds_arn"        { value = aws_db_instance.simp_postgres.arn }
output "rds_db_name"    { value = aws_db_instance.simp_postgres.db_name }
output "rds_password_secret_arn" { value = var.db_password_secret_arn }
