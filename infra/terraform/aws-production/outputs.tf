output "cluster_name" {
  description = "EKS cluster name (aws eks update-kubeconfig --name <this>)."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "aurora_endpoint" {
  description = "Writer endpoint for PLATFORM_STATE_DSN."
  value       = aws_rds_cluster.state.endpoint
}

output "aurora_master_secret_arn" {
  description = "Secrets Manager secret holding the AWS-managed master password."
  value       = aws_rds_cluster.state.master_user_secret[0].secret_arn
}

output "state_dsn_template" {
  description = "PLATFORM_STATE_DSN shape — substitute the password from the managed secret."
  value       = "postgresql://platform_agent:<password-from-secret>@${aws_rds_cluster.state.endpoint}:5432/platform_state"
}

output "chart_irsa_role_arn" {
  description = "Annotate the chart ServiceAccount with this (eks.amazonaws.com/role-arn)."
  value       = aws_iam_role.chart.arn
}
