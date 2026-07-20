// Platform add-ons — the cluster tooling provisioned by infra/onprem/addons
// (Terraform). These are provisioning OUTPUT, so the dashboard surfaces them on
// the Provisioning screen with the IaC metadata (pinned chart version, the
// namespace they land in) alongside a link to each UI.
//
// URLs are env-driven so the SAME dashboard points at local port-forwards in dev
// and at cluster ingress hosts in a real deployment — nothing is hard-coded.
// NEXT_PUBLIC_* are inlined at build time, so each must be referenced literally.

export type StackCategory = "GitOps" | "Observability" | "Progressive delivery";

export interface StackLink {
  key: string;
  label: string;
  category: StackCategory;
  accent: string; // category accent color
  chart: string; // Helm chart + pinned version (the IaC contract)
  namespace: string;
  url: string;
}

export function getStackLinks(): StackLink[] {
  // In dev, fall back to the local port-forward URLs so the demo works out of the
  // box. In production, only surface a link if its NEXT_PUBLIC_*_URL is explicitly
  // set (cluster ingress) — otherwise omit it, so prod never shows dead localhost
  // links. Env values are referenced literally so NEXT_PUBLIC inlining applies.
  const dev = process.env.NODE_ENV !== "production";
  const at = (envUrl: string | undefined, localDefault: string) => envUrl || (dev ? localDefault : "");
  const links: StackLink[] = [
    {
      key: "argocd",
      label: "ArgoCD",
      category: "GitOps",
      accent: "#ef7b4d",
      chart: "argo-cd 10.1.4",
      namespace: "argocd",
      url: at(process.env.NEXT_PUBLIC_ARGOCD_URL, "https://localhost:8090"),
    },
    {
      key: "grafana",
      label: "Grafana",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "kube-prometheus-stack 87.17.0",
      namespace: "monitoring",
      url: at(process.env.NEXT_PUBLIC_GRAFANA_URL, "http://localhost:3001"),
    },
    {
      key: "prometheus",
      label: "Prometheus",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "kube-prometheus-stack 87.17.0",
      namespace: "monitoring",
      url: at(process.env.NEXT_PUBLIC_PROMETHEUS_URL, "http://localhost:9090"),
    },
    {
      key: "alertmanager",
      label: "Alertmanager",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "kube-prometheus-stack 87.17.0",
      namespace: "monitoring",
      url: at(process.env.NEXT_PUBLIC_ALERTMANAGER_URL, "http://localhost:9093"),
    },
    {
      key: "rollouts",
      label: "Argo Rollouts",
      category: "Progressive delivery",
      accent: "#69d3a7",
      chart: "argo-rollouts 2.41.1",
      namespace: "argo-rollouts",
      url: at(process.env.NEXT_PUBLIC_ROLLOUTS_URL, "http://localhost:3101/rollouts"),
    },
  ];
  return links.filter((link) => Boolean(link.url));
}
