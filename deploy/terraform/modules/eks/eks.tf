# ─────────────────────────────────────────────────────────────────────────────
# T45: EKS Module — Managed Kubernetes cluster
# ─────────────────────────────────────────────────────────────────────────────

variable "environment"        { type = string }
variable "cluster_name"        { type = string }
variable "kubernetes_version" { type = string default = "1.29" }
variable "vpc_id"             { type = string }
variable "private_subnet_ids"  { type = list(string) }
variable "broker_sg_id"       { type = string }
variable "tags"               { type = map(string) default = {} }

locals {
  project_tag = merge(var.tags, { Project = "SIMP", Environment = var.environment })
}

# ── EKS Cluster ──────────────────────────────────────────────────────────────

resource "aws_eks_cluster" "simp" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster_role.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["0.0.0.0/0"]
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = var.kms_key_arn
    }
  }

  tags = local.project_tag

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_cluster_encryption_policy,
  ]
}

# ── Node Group (EC2) ─────────────────────────────────────────────────────────

resource "aws_eks_node_group" "simp_nodes" {
  cluster_name    = aws_eks_cluster.simp.name
  node_group_name = "${var.cluster_name}-nodes"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = var.private_subnet_ids
  instance_types   = var.instance_types
  capacity_type    = var.capacity_type
  desired_size     = var.desired_size
  min_size         = var.min_size
  max_size         = var.max_size

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  labels = { NodeRole = "simp-broker" }

  tags = local.project_tag

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_policy,
    aws_iam_role_policy_attachment.eks_worker_node_policy,
  ]
}

# ── IAM Roles ────────────────────────────────────────────────────────────────

resource "aws_iam_role" "eks_cluster_role" {
  name = "simp-${var.environment}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster_role.name
}

resource "aws_iam_role_policy_attachment" "eks_cluster_encryption_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSEncryptionServiceRolePolicy"
  role       = aws_iam_role.eks_cluster_role.name
}

resource "aws_iam_role" "eks_node_role" {
  name = "simp-${var.environment}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node_role.name
}

resource "aws_iam_role_policy_attachment" "eks_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node_role.name
}

resource "aws_iam_role_policy_attachment" "eks_node_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node_role.name
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "cluster_name"       { value = aws_eks_cluster.simp.name }
output "cluster_endpoint"    { value = aws_eks_cluster.simp.endpoint }
output "cluster_ca_cert"     { value = base64decode(aws_eks_cluster.simp.certificate_authority[0].data) }
output "node_group_arn"     { value = aws_eks_node_group.simp_nodes.arn }
output "eks_cluster_role_arn" { value = aws_iam_role.eks_cluster_role.arn }
output "eks_node_role_arn"   { value = aws_iam_role.eks_node_role.arn }
