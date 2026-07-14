// Per-agent tool catalog shown in the "Tools" popup on each Agent card.
// On-Prem mirrors the real tool set (src/agents/ai: provision + deploy + ops);
// the cloud agents deploy via their native services (per the deployment matrix).

export interface ToolInfo {
  name: string;
  desc: string;
}
export interface ToolGroup {
  label: string;
  tools: ToolInfo[];
}

export const AGENT_TOOLS: Record<string, ToolGroup[]> = {
  onprem: [
    {
      label: "Provision (IaC · mutating)",
      tools: [
        { name: "provision_cluster", desc: "Stand up a cluster — Terraform (kind) or Ansible (k3s)" },
        { name: "teardown_cluster", desc: "Destroy a provisioned cluster" },
      ],
    },
    {
      label: "Deploy (mutating)",
      tools: [
        { name: "deploy_service", desc: "preferred — build → push → deploy → validate in ONE call" },
        { name: "build_image", desc: "build step only (fine-grained control)" },
        { name: "push_image", desc: "push a built image to the registry (Harbor)" },
        { name: "deploy_to_cluster", desc: "apply a pre-built image (needs image_uri from push)" },
        { name: "validate_deployment", desc: "rollout status + readiness check" },
      ],
    },
    {
      label: "Investigate (read-only)",
      tools: [
        { name: "list_pods", desc: "kubectl get pods" },
        { name: "get_logs", desc: "kubectl logs (deployment pods)" },
        { name: "describe_deployment", desc: "kubectl describe — conditions & events" },
        { name: "rollout_status", desc: "kubectl rollout status" },
        { name: "list_namespaces", desc: "kubectl get namespaces" },
      ],
    },
    {
      label: "Recover (mutating)",
      tools: [
        { name: "rollback_deployment", desc: "roll back a deployment to its previous version" },
      ],
    },
  ],
  aws: [
    {
      label: "Deploy (EKS · native services)",
      tools: [
        { name: "build_image", desc: "AWS CodeBuild" },
        { name: "push_image", desc: "Amazon ECR" },
        { name: "deploy_to_cluster", desc: "kubectl → EKS" },
        { name: "validate_deployment", desc: "HTTP health + rollout status" },
        { name: "rollback_deployment", desc: "revert to the previous version" },
      ],
    },
  ],
  gcp: [
    {
      label: "Deploy (GKE · native services)",
      tools: [
        { name: "gcp_build_image", desc: "Cloud Build" },
        { name: "gcp_push_image", desc: "Artifact Registry" },
        { name: "gcp_deploy_to_cluster", desc: "kubectl → GKE" },
        { name: "gcp_validate_deployment", desc: "HTTP health + rollout status" },
        { name: "gcp_rollback_deployment", desc: "revert to the previous version" },
      ],
    },
  ],
  azure: [
    {
      label: "Deploy (AKS · native services)",
      tools: [
        { name: "build_image_azure", desc: "ACR Tasks" },
        { name: "push_image_azure", desc: "Azure Container Registry" },
        { name: "deploy_to_aks", desc: "kubectl → AKS" },
        { name: "validate_aks_deployment", desc: "HTTP health + rollout status" },
        { name: "rollback_aks_deployment", desc: "revert to the previous version" },
      ],
    },
  ],
};

export function toolCount(cloud: string): number {
  return (AGENT_TOOLS[cloud] ?? []).reduce((n, g) => n + g.tools.length, 0);
}
