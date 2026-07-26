// Platform add-ons — the cluster tooling provisioned by infra/onprem/addons
// (Terraform). These are provisioning OUTPUT, so the dashboard surfaces them on
// the Provisioning screen with the IaC metadata (pinned chart version, the
// namespace they land in) alongside a link to each UI.
//
// URLs are env-driven so the SAME dashboard points at local port-forwards in dev
// and at cluster ingress hosts in a real deployment — nothing is hard-coded.
// NEXT_PUBLIC_* are inlined at build time, so each must be referenced literally.

export type StackCategory =
  | "GitOps"
  | "Observability"
  | "Progressive delivery"
  | "Tenancy";

export interface StackLink {
  key: string;
  label: string;
  category: StackCategory;
  accent: string; // category accent color
  chart: string; // Helm chart + pinned version (the IaC contract)
  namespace: string;
  /** Empty when this add-on ships no console of its own — see `note`. */
  url: string;
  /**
   * Why there is no link, or where the UI actually lives.
   *
   * Loki and Tempo are queried THROUGH Grafana rather than serving a console, and
   * Fluent Bit / Capsule serve none at all. Omitting them would make the list read
   * as the full add-on inventory while hiding a third of it; linking them to their
   * API ports would hand someone a JSON 404. Naming the reason is the honest third
   * option.
   */
  note?: string;
}

export function getStackLinks(): StackLink[] {
  // In dev, fall back to the local port-forward URLs so the demo works out of the
  // box. In production, only surface a link if its NEXT_PUBLIC_*_URL is explicitly
  // set (cluster ingress) — otherwise omit it, so prod never shows dead localhost
  // links. Env values are referenced literally so NEXT_PUBLIC inlining applies.
  const dev = process.env.NODE_ENV !== "production";
  const at = (envUrl: string | undefined, localDefault: string) => envUrl || (dev ? localDefault : "");
  const grafana = at(process.env.NEXT_PUBLIC_GRAFANA_URL, "http://localhost:3001");
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
      url: grafana,
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
      key: "loki",
      label: "Loki",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "loki 7.1.0",
      namespace: "monitoring",
      // No console of its own: Loki is a store, and Grafana Explore is where a
      // human actually queries it.
      url: grafana ? `${grafana}/explore` : "",
      note: "query via Grafana Explore",
    },
    {
      key: "fluent-bit",
      label: "Fluent Bit",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "fluent-bit 0.57.9",
      namespace: "monitoring",
      url: "",
      note: "DaemonSet log shipper · no console",
    },
    {
      key: "tempo",
      label: "Tempo",
      category: "Observability",
      accent: "#8ab4f8",
      chart: "tempo 1.24.4",
      namespace: "monitoring",
      url: grafana ? `${grafana}/explore` : "",
      note: "query via Grafana Explore",
    },
    {
      key: "capsule",
      label: "Capsule",
      category: "Tenancy",
      accent: "#c9a4ff",
      chart: "capsule 0.13.10",
      namespace: "capsule-system",
      url: "",
      note: "tenancy operator · no console",
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
  // A console-less add-on is still provisioned, so it stays in the list; only a
  // link that would be dead gets dropped (prod with no ingress configured).
  return links.filter((link) => Boolean(link.url) || Boolean(link.note));
}
