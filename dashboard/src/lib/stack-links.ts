// Platform add-on stack UIs (ArgoCD / Grafana / Prometheus / Alertmanager /
// Argo Rollouts). URLs are env-driven so the SAME dashboard points at local
// port-forwards in dev and at cluster ingress hosts in a real deployment —
// nothing is hard-coded. Set NEXT_PUBLIC_<STACK>_URL to override a default.
//
// NEXT_PUBLIC_* are inlined at build time, so each must be referenced literally
// (a dynamic process.env[key] lookup would not be replaced).

export interface StackLink {
  key: string;
  label: string;
  icon: string;
  url: string;
  hint: string;
}

export function getStackLinks(): StackLink[] {
  return [
    {
      key: "argocd",
      label: "ArgoCD",
      icon: "🔁",
      hint: "GitOps",
      url: process.env.NEXT_PUBLIC_ARGOCD_URL || "https://localhost:8090",
    },
    {
      key: "grafana",
      label: "Grafana",
      icon: "📊",
      hint: "Metrics + logs",
      url: process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001",
    },
    {
      key: "prometheus",
      label: "Prometheus",
      icon: "🔥",
      hint: "Metrics",
      url: process.env.NEXT_PUBLIC_PROMETHEUS_URL || "http://localhost:9090",
    },
    {
      key: "alertmanager",
      label: "Alertmanager",
      icon: "🔔",
      hint: "Alerts",
      url: process.env.NEXT_PUBLIC_ALERTMANAGER_URL || "http://localhost:9093",
    },
    {
      key: "rollouts",
      label: "Argo Rollouts",
      icon: "🚦",
      hint: "Progressive delivery",
      url: process.env.NEXT_PUBLIC_ROLLOUTS_URL || "http://localhost:3101/rollouts",
    },
  ].filter((link) => Boolean(link.url));
}
