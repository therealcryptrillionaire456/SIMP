# ─────────────────────────────────────────────────────────────────────────────
# T45: Network Module — VPC, Subnets, NAT Gateways
# ─────────────────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs for private subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default     = {}
}

locals {
  project_tag  = merge(var.tags, { Project = "SIMP", Environment = var.environment })
  az_subnet_map = {
    "us-east-1a" = "10.0.1.0/24"
    "us-east-1b" = "10.0.2.0/24"
    "us-east-1c" = "10.0.3.0/24"
  }
}

# ── VPC ─────────────────────────────────────────────────────────────────────

resource "aws_vpc" "simp_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-vpc" })
}

# ── Internet Gateway ────────────────────────────────────────────────────────

resource "aws_internet_gateway" "simp_igw" {
  vpc_id = aws_vpc.simp_vpc.id

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-igw" })
}

# ── Public Subnets (load balancer tier) ────────────────────────────────────

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.simp_vpc.id
  cidr_block              = local.az_subnet_map[var.availability_zones[count.index]]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.project_tag, {
    Name = "simp-${var.environment}-public-${var.availability_zones[count.index]}"
    Tier = "Public"
  })
}

# ── Private Subnets (application tier) ─────────────────────────────────────

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.simp_vpc.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.project_tag, {
    Name = "simp-${var.environment}-private-${var.availability_zones[count.index]}"
    Tier = "Private"
  })
}

# ── NAT Gateways ─────────────────────────────────────────────────────────────

resource "aws_eip" "nat_eip" {
  count = min(length(var.availability_zones), 2)  # HA: 2 NAT GWs
  domain = "vpc"

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-nat-eip-${count.index + 1}" })
}

resource "aws_nat_gateway" "simp_nat" {
  count = min(length(var.availability_zones), 2)

  allocation_id = aws_eip.nat_eip[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-nat-${count.index + 1}" })

  depends_on = [aws_internet_gateway.simp_igw]
}

# ── Route Tables ─────────────────────────────────────────────────────────────

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.simp_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.simp_igw.id
  }

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-rt-public" })
}

resource "aws_route_table" "private" {
  count = min(length(var.availability_zones), 2)

  vpc_id = aws_vpc.simp_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.simp_nat[count.index].id
  }

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-rt-private-${count.index + 1}" })
}

resource "aws_route_table_association" "public" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index % 2].id
}

# ── Security Groups ──────────────────────────────────────────────────────────

resource "aws_security_group" "broker_sg" {
  name        = "simp-${var.environment}-broker-sg"
  description  = "Security group for SIMP broker"
  vpc_id       = aws_vpc.simp_vpc.id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "WebSocket from internet"
    from_port   = 8765
    to_port     = 8765
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-broker-sg" })
}

resource "aws_security_group" "database_sg" {
  name        = "simp-${var.environment}-database-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.simp_vpc.id

  ingress {
    description     = "PostgreSQL from broker"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.broker_sg.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.project_tag, { Name = "simp-${var.environment}-database-sg" })
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.simp_vpc.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "broker_security_group_id" {
  description = "Broker security group ID"
  value       = aws_security_group.broker_sg.id
}

output "database_security_group_id" {
  description = "Database security group ID"
  value       = aws_security_group.database_sg.id
}
