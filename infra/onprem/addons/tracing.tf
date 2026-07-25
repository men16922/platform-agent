# Phase 6 — Tracing: Grafana Tempo, in the monitoring namespace so the
# kube-prometheus-stack Grafana adds it as a datasource (metrics + logs + traces
# in one pane). Mirrors logging.tf exactly: pinned chart, low-footprint values,
# same namespace, datasource registered from the kps values.
#
# What this traces is *the agent's own Day-2 pipeline*, not a demo app: the
# detect→analyze→decide→execute chain emits one span per stage
# (src/agents/observability/tracing.py), so incident wall-clock is finally
# decomposable — "how much of the MTTR was local-LLM inference?" becomes a
# readable answer instead of an estimate.
#
# The app only speaks OTLP; the receiving backend is an env var away from being
# X-Ray/Cloud Trace instead (cloud-neutral, same rule the execution adapters use).
resource "helm_release" "tempo" {
  name       = "tempo"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "tempo"
  version    = var.tempo_chart_version
  namespace  = var.monitoring_namespace

  values = [file("${path.module}/values/tempo.yaml")]

  wait    = true
  timeout = 600
}
