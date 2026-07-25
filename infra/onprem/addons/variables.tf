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

# argo-rollouts 2.41.1 ships Argo Rollouts v1.9.1 (Phase 4 progressive delivery).
variable "argo_rollouts_chart_version" {
  type    = string
  default = "2.41.1"
}

variable "argo_rollouts_namespace" {
  type    = string
  default = "argo-rollouts"
}

# Phase 5 logging: Loki (log store) + Fluent Bit (shipper), installed alongside
# the kube-prometheus-stack in the monitoring namespace so Grafana can add Loki
# as a datasource (metrics + logs in one pane). loki 7.1.0 ships Loki 3.6.8;
# fluent-bit 0.57.9 ships Fluent Bit 5.0.9.
variable "loki_chart_version" {
  type    = string
  default = "7.1.0"
}

variable "fluent_bit_chart_version" {
  type    = string
  default = "0.57.9"
}

# Metric-based canary judgment for the Rollouts demo. Default false: this path is
# additive to the live-verified manual promote/abort gate, and shipping an
# unverified auto-abort as the default would risk that demo.
variable "rollouts_demo_analysis_enabled" {
  type    = bool
  default = false
}

# kube-prometheus-stack names its Prometheus Service from its own chart helpers,
# so the address is configuration rather than something this module derives.
# Confirmed live against the module's own Grafana datasource.
variable "rollouts_demo_prometheus_address" {
  type    = string
  default = "http://monitoring-kube-prometheus-prometheus.monitoring.svc:9090"
}

# Phase 6 tracing: Grafana Tempo (single binary) in the monitoring namespace so
# the kps Grafana adds it as a third datasource (metrics + logs + traces).
# tempo 1.24.4 ships Tempo 2.9.0 (verified: helm search repo grafana/tempo --versions).
variable "tempo_chart_version" {
  type    = string
  default = "1.24.4"
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
