output "offline_dsn" {
  description = "SQLAlchemy DSN for the offline/registry Postgres (password omitted)."
  value       = "postgresql+psycopg://feaststore@${aws_db_instance.offline.endpoint}/feaststore"
}

output "online_redis_url" {
  description = "Redis URL for the online store (rediss:// -- TLS in transit)."
  value       = "rediss://${aws_elasticache_replication_group.online.primary_endpoint_address}:6379/0"
}

output "stores_security_group_id" {
  description = "Security group guarding the stores; attach serving tasks as allowed sources."
  value       = aws_security_group.stores.id
}
