resource "helm_release" "kube_prometheus_stack" {
  name             = "monitoring"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = var.kube_prometheus_stack_chart_version
  namespace        = var.monitoring_namespace
  create_namespace = true

  values = [
    templatefile("${path.module}/values/kube-prometheus-stack.yaml", {
      webhook_url = var.platform_agent_webhook_url
    })
  ]

  wait    = true
  timeout = 600
}
