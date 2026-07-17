variable "region" {
  description = "AWS region for the production substrate."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Base name for every resource (cluster, DB, roles)."
  type        = string
  default     = "platform-agent"
}

variable "vpc_cidr" {
  description = "VPC CIDR. Two public + two private subnets are carved from it."
  type        = string
  default     = "10.80.0.0/16"
}

variable "eks_version" {
  description = "EKS Kubernetes version (matches the kubectl baked into infra/onprem/Dockerfile)."
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "Managed node group instance type."
  type        = string
  default     = "t3.medium"
}

variable "node_count" {
  description = "Desired managed node count (min 1, max 3)."
  type        = number
  default     = 2
}

variable "aurora_max_acu" {
  description = "Aurora Serverless v2 max capacity (ACU). Min is pinned at 0.5 to stay near-$0 idle."
  type        = number
  default     = 2
}

variable "chart_namespace" {
  description = "Namespace the Helm chart is installed into (IRSA trust condition)."
  type        = string
  default     = "default"
}

variable "chart_service_account" {
  description = "ServiceAccount name the Helm chart creates (release-name-platform-agent)."
  type        = string
  default     = "pa-platform-agent"
}

variable "activity_table_name" {
  description = "Existing DynamoDB activity table the deploy recorder writes (CDK-owned). IRSA grants are scoped to exactly this table."
  type        = string
  default     = "platform-agent-activity"
}
