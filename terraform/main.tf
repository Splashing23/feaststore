locals {
  name = "feaststore-${var.environment}"
}

# --- networking -------------------------------------------------------------

resource "aws_security_group" "stores" {
  name_prefix = "${local.name}-stores-"
  description = "Ingress to feaststore online/offline stores"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "postgres_ingress" {
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.stores.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
}

resource "aws_security_group_rule" "redis_ingress" {
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.stores.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
}

# --- offline store (RDS Postgres) ------------------------------------------

resource "aws_db_subnet_group" "offline" {
  name       = "${local.name}-offline"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "offline" {
  identifier             = "${local.name}-offline"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.offline_instance_class
  allocated_storage      = 50
  max_allocated_storage  = 500
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = "feaststore"
  username               = "feaststore"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.offline.name
  vpc_security_group_ids = [aws_security_group.stores.id]
  multi_az               = var.environment == "prod"
  skip_final_snapshot    = var.environment != "prod"
  deletion_protection    = var.environment == "prod"
  apply_immediately      = var.environment != "prod"
  backup_retention_period = var.environment == "prod" ? 14 : 1
}

# --- online store (ElastiCache Redis) --------------------------------------

resource "aws_elasticache_subnet_group" "online" {
  name       = "${local.name}-online"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "online" {
  replication_group_id       = "${local.name}-online"
  description                = "feaststore online store (${var.environment})"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.online_node_type
  num_cache_clusters         = var.online_num_nodes
  automatic_failover_enabled = var.online_num_nodes > 1
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.online.name
  security_group_ids         = [aws_security_group.stores.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}
