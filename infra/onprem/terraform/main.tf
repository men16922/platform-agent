# On-prem cluster provisioning as IaC (Tier 1: kind on Docker — testable on a Mac
# with no VMs). Terraform owns the lifecycle (create/destroy) of a 3-node kind
# cluster + a local registry wired for containerd. The realistic on-prem path
# (bare-metal / VM nodes + kubeadm/k3s) is handled by the Ansible playbook under
# ../ansible. Uses null_resource + the kind/docker CLIs (the community kind
# terraform providers are immature); swap for a real infra provider in prod.

terraform {
  required_version = ">= 1.5"
}

variable "cluster_name" {
  type    = string
  default = "platform-agent"
}

variable "registry_name" {
  type    = string
  default = "kind-registry"
}

variable "registry_port" {
  type    = number
  default = 5001
}

# --- Local registry container ---
resource "null_resource" "registry" {
  triggers = {
    name = var.registry_name
    port = var.registry_port
  }

  provisioner "local-exec" {
    command = <<-EOT
      docker inspect ${var.registry_name} >/dev/null 2>&1 || \
        docker run -d --restart=always -p 127.0.0.1:${var.registry_port}:5000 \
          --name ${var.registry_name} registry:2
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "docker rm -f ${self.triggers.name} 2>/dev/null || true"
  }
}

# --- 3-node kind cluster (ingress ports + registry mirror from kind-config.yaml) ---
resource "null_resource" "cluster" {
  depends_on = [null_resource.registry]

  triggers = {
    name   = var.cluster_name
    config = filemd5("${path.module}/kind-config.yaml")
  }

  provisioner "local-exec" {
    command = <<-EOT
      kind get clusters | grep -qx ${var.cluster_name} || \
        kind create cluster --name ${var.cluster_name} --config ${path.module}/kind-config.yaml
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "kind delete cluster --name ${self.triggers.name} 2>/dev/null || true"
  }
}

# --- Connect the registry to the kind network so nodes can pull ---
resource "null_resource" "registry_network" {
  depends_on = [null_resource.cluster]

  provisioner "local-exec" {
    command = "docker network connect kind ${var.registry_name} 2>/dev/null || true"
  }
}

output "cluster_name" {
  value = var.cluster_name
}

output "kubeconfig_context" {
  value = "kind-${var.cluster_name}"
}

output "registry" {
  value = "localhost:${var.registry_port}"
}
