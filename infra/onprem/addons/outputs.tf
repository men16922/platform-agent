output "argocd_namespace" {
  value = var.argocd_namespace
}

output "monitoring_namespace" {
  value = var.monitoring_namespace
}

output "ui_access" {
  value = <<-EOT
    ArgoCD:  kubectl -n ${var.argocd_namespace} port-forward svc/argocd-server 8090:443
             (admin password: kubectl -n ${var.argocd_namespace} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)
    Grafana: kubectl -n ${var.monitoring_namespace} port-forward svc/monitoring-grafana 3001:80
    Prom:    kubectl -n ${var.monitoring_namespace} port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
  EOT
}

output "gitops_application" {
  value = <<-EOT
    ArgoCD Application 'platform-agent' → ${var.gitops_repo_url}
      path=${var.gitops_chart_path} rev=${var.gitops_target_revision} values=${var.gitops_values_file}
    Sync/drift:  kubectl -n ${var.argocd_namespace} get application platform-agent
  EOT
}
