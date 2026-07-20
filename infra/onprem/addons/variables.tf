variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  type    = string
  default = "kind-platform-agent" # k3s substrate: pass the fetched kubeconfig instead
}

variable "argocd_namespace" {
  type    = string
  default = "argocd"
}

variable "monitoring_namespace" {
  type    = string
  default = "monitoring"
}

# Chart versions are pinned exactly (guard-tested) so applies are reproducible.
# argo-cd 10.1.4 ships Argo CD v3.4.5.
variable "argocd_chart_version" {
  type    = string
  default = "10.1.4"
}

variable "kube_prometheus_stack_chart_version" {
  type    = string
  default = "87.17.0"
}

# Where Alertmanager delivers alerts: the platform-agent chart's in-cluster
# webhook Service (Day-2 detect→analyze→decide→execute entrypoint). Default
# matches `helm install pa infra/helm/platform-agent` in the default namespace.
variable "platform_agent_webhook_url" {
  type    = string
  default = "http://pa-platform-agent-webhook.default.svc:8078/webhook/alertmanager"
}
