# Phase 4 — Progressive delivery: Argo Rollouts controller + a canary demo.
#
# The controller installs the Rollout CRD; the demo Rollout ships through a tiny
# local chart (charts/rollouts-demo) as a helm_release that depends_on the
# controller, mirroring the Phase 3 CRD-ordering pattern.
resource "helm_release" "argo_rollouts" {
  name             = "argo-rollouts"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-rollouts"
  version          = var.argo_rollouts_chart_version
  namespace        = var.argo_rollouts_namespace
  create_namespace = true

  values = [file("${path.module}/values/argo-rollouts.yaml")]

  wait    = true
  timeout = 600
}

resource "helm_release" "rollouts_demo" {
  name      = "rollouts-demo"
  chart     = "${path.module}/charts/rollouts-demo"
  namespace = var.argo_rollouts_namespace

  # Metric-based canary judgment (AnalysisTemplate + Prometheus). Default off —
  # see values.yaml for why. Exposed as a variable so enabling it is an IaC change
  # rather than a hand-edit of chart values.
  set = [
    {
      name  = "analysis.enabled"
      value = var.rollouts_demo_analysis_enabled
    },
    {
      name  = "analysis.prometheusAddress"
      value = var.rollouts_demo_prometheus_address
    },
  ]

  wait    = true
  timeout = 300

  depends_on = [helm_release.argo_rollouts]
}
