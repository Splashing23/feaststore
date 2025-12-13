variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region to deploy into."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment environment (dev/staging/prod)."
}

variable "vpc_id" {
  type        = string
  description = "VPC to place the stores in."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for RDS and ElastiCache."
}

variable "offline_instance_class" {
  type        = string
  default     = "db.t4g.medium"
  description = "RDS instance class for the offline/registry Postgres."
}

variable "online_node_type" {
  type        = string
  default     = "cache.t4g.small"
  description = "ElastiCache node type for the online Redis store."
}

variable "online_num_nodes" {
  type        = number
  default     = 2
  description = "Number of Redis nodes (1 primary + replicas)."
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Master password for the offline Postgres instance."
}

variable "allowed_security_group_ids" {
  type        = list(string)
  default     = []
  description = "Security groups permitted to reach the stores (e.g. the serving task SG)."
}
