# On-prem platform add-on stack (GitOps + observability) as IaC. Installs into
# an EXISTING local cluster (kind via ../terraform, or k3s via ../ansible) —
# substrate lifecycle stays in its own root; this root only owns helm releases,
# so the same module applies to either substrate by switching kubeconfig/context.

terraform {
  required_version = ">= 1.5"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
  }
}

provider "helm" {
  kubernetes = {
    config_path    = pathexpand(var.kubeconfig_path)
    config_context = var.kube_context
  }
}
