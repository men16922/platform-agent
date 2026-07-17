# Aurora PostgreSQL Serverless v2 — the production State Store behind the
# opt-in PLATFORM_STATE_DSN seam (src/agents/ai/state_store.py). Min capacity
# 0.5 ACU keeps the idle floor low; the master password is AWS-managed in
# Secrets Manager (never in state or values files).

resource "aws_db_subnet_group" "aurora" {
  name       = "${var.name}-aurora"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "aurora" {
  name        = "${var.name}-aurora"
  description = "Aurora ingress from EKS nodes only"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "PostgreSQL from EKS worker nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }

  egress {
    description = "none needed; deny-all egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
    self        = true
  }
}

resource "aws_rds_cluster" "state" {
  cluster_identifier          = "${var.name}-state"
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  database_name               = "platform_state"
  master_username             = "platform_agent"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  storage_encrypted      = true
  skip_final_snapshot    = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = var.aurora_max_acu
  }
}

resource "aws_rds_cluster_instance" "state" {
  cluster_identifier = aws_rds_cluster.state.id
  identifier         = "${var.name}-state-1"
  engine             = aws_rds_cluster.state.engine
  instance_class     = "db.serverless"
}
