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
  # Zero when GitOps owns this release. See var.rollouts_demo_gitops_owned for
  # why the state rm has to happen BEFORE the flag flips.
  count = var.rollouts_demo_gitops_owned ? 0 : 1

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
    # Stage 2 — the agent as the release gate. Exposed the same way as stage 1 so
    # the two judges are independently switchable: the metric judge and the
    # pipeline judge answer different questions, and either one alone is a valid
    # configuration.
    {
      name  = "agentAnalysis.enabled"
      value = var.rollouts_demo_agent_analysis_enabled
    },
    {
      name  = "agentAnalysis.url"
      value = var.rollouts_demo_agent_analysis_url
    },
  ]

  wait    = true
  timeout = 300

  depends_on = [helm_release.argo_rollouts]
}

# Phase 1b — the same release, owned by ArgoCD instead.
#
# Terraform still owns this ownership RECORD (one small Application object); it
# no longer owns the workload. That is the point of the handoff: the delivery
# engine reconciles the app continuously, Terraform stops racing it.
#
# `cascadeDelete = false` on purpose — this Application adopts objects it did
# not create, so deleting the record must never delete the workload.
resource "helm_release" "rollouts_demo_app" {
  count = var.rollouts_demo_gitops_owned ? 1 : 0

  name      = "rollouts-demo-app"
  chart     = "${path.module}/charts/argocd-app"
  namespace = var.argocd_namespace

  set = [
    {
      name  = "name"
      value = "rollouts-demo"
    },
    {
      name  = "argocdNamespace"
      value = var.argocd_namespace
    },
    {
      name  = "repoURL"
      value = var.gitops_repo_url
    },
    {
      name  = "targetRevision"
      value = var.gitops_target_revision
    },
    {
      name  = "chartPath"
      value = "infra/onprem/addons/charts/rollouts-demo"
    },
    # Must equal the adopted release's name, or adoption renders a second set of
    # objects under different names instead of taking over the existing ones.
    {
      name  = "releaseName"
      value = "rollouts-demo"
    },
    {
      name  = "destNamespace"
      value = var.argo_rollouts_namespace
    },
  ]

  wait    = true
  timeout = 300

  depends_on = [helm_release.argocd, helm_release.argo_rollouts]
}
