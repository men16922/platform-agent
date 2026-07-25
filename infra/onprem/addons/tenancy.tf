# Phase 2 — Capsule: the soft isolation tier's enforcement point.
#
# Why an operator rather than plain ResourceQuota objects: a tenant's declared
# quota is a bound on the TENANT, and a soft-tier tenant owns one namespace per
# subscribed capability. Writing the declared quota into each namespace does not
# enforce it — it multiplies it by the namespace count, silently and in the
# generous direction. Capsule's `resourceQuotas.scope: Tenant` aggregates across
# the tenant's namespaces, which is the only shape that means what the registry
# says.
#
# Default OFF, consistent with every other add-on here: it installs webhooks that
# intercept namespace creation cluster-wide, which is not something to turn on
# by side effect. Enable per environment:
#   terraform apply -var capsule_enabled=true
resource "helm_release" "capsule" {
  count = var.capsule_enabled ? 1 : 0

  name             = "capsule"
  repository       = "https://projectcapsule.github.io/charts"
  chart            = "capsule"
  version          = var.capsule_chart_version
  namespace        = var.capsule_namespace
  create_namespace = true

  values = [file("${path.module}/values/capsule.yaml")]

  wait    = true
  timeout = 600
}
