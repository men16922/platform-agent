# Phase 3 — GitOps: ArgoCD manages the platform-agent workload chart.
#
# The Application CR is shipped through a tiny local chart (charts/
# platform-agent-app) instead of kubernetes_manifest, so `terraform plan` never
# needs the argoproj.io CRDs to already exist. depends_on forces the argo-cd
# release (which installs those CRDs) to complete first at apply time.
resource "helm_release" "platform_agent_app" {
  name      = "platform-agent-app"
  chart     = "${path.module}/charts/platform-agent-app"
  namespace = var.argocd_namespace

  set = [
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
      value = var.gitops_chart_path
    },
    {
      name  = "valuesFile"
      value = var.gitops_values_file
    },
    {
      name  = "destNamespace"
      value = var.gitops_dest_namespace
    },
    {
      name  = "releaseName"
      value = var.gitops_release_name
    },
  ]

  wait    = true
  timeout = 300

  depends_on = [helm_release.argocd]
}
