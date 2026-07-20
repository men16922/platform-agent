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

# --- Phase 3: GitOps -------------------------------------------------------
# ArgoCD manages the platform-agent chart itself, closing the loop: the same
# repo that describes the add-on stack also drives the workload ArgoCD syncs.
# Defaults target the GitHub origin (public after push); swap repo_url for a
# local gitea remote to run fully offline.
variable "gitops_repo_url" {
  type    = string
  default = "https://github.com/men16922/platform-agent.git"
}

variable "gitops_target_revision" {
  type    = string
  default = "main"
}

variable "gitops_chart_path" {
  type    = string
  default = "infra/helm/platform-agent"
}

variable "gitops_values_file" {
  type    = string
  default = "values-kind.yaml" # k3s substrate: pass values-k3s.yaml
}

variable "gitops_dest_namespace" {
  type    = string
  default = "default"
}

# Helm release name ArgoCD renders the workload chart under. Kept as "pa" so the
# managed Service name (pa-platform-agent-webhook) matches the Alertmanager
# receiver URL from Phase 2 — GitOps adopts the same resources the loop targets.
variable "gitops_release_name" {
  type    = string
  default = "pa"
}
