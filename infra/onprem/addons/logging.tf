# Phase 5 — Logging: Loki (store) + Fluent Bit (shipper), in the monitoring
# namespace so the kube-prometheus-stack Grafana adds Loki as a datasource
# (metrics + logs in one pane). Fluent Bit depends_on Loki so the gateway
# Service its output targets exists first.
resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki"
  version    = var.loki_chart_version
  namespace  = var.monitoring_namespace

  values = [file("${path.module}/values/loki.yaml")]

  wait    = true
  timeout = 600
}

resource "helm_release" "fluent_bit" {
  name       = "fluent-bit"
  repository = "https://fluent.github.io/helm-charts"
  chart      = "fluent-bit"
  version    = var.fluent_bit_chart_version
  namespace  = var.monitoring_namespace

  values = [file("${path.module}/values/fluent-bit.yaml")]

  wait    = true
  timeout = 300

  depends_on = [helm_release.loki]
}
