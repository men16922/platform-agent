/**
 * Deep links from an incident to its distributed trace.
 *
 * The pipeline emits one span per stage (detect → analyze → decide → execute), so
 * a trace answers "where did the time go" — on the live run that was 82% in local
 * LLM inference. Without a link the reader has to eyeball timestamps in Grafana.
 *
 * Same prod-safe rule as `stack-links.ts`: in dev fall back to the local
 * port-forward so the demo works out of the box; in production emit a link ONLY
 * when the URL is explicitly configured, so prod never renders a dead localhost
 * link. NEXT_PUBLIC_* are inlined at build time, so each must be referenced
 * literally rather than looked up dynamically.
 */

/** Grafana's Tempo datasource uid, as registered by the add-on stack. */
const TEMPO_DATASOURCE_UID = "tempo";

function grafanaBaseUrl(): string {
  const dev = process.env.NODE_ENV !== "production";
  const configured = process.env.NEXT_PUBLIC_GRAFANA_URL;
  return configured || (dev ? "http://localhost:3001" : "");
}

/**
 * Grafana Explore URL for one trace, or null when we cannot build a real one.
 *
 * Returns null (rather than a best-effort link) when tracing produced no id or
 * Grafana is not configured — a dead link that looks live is worse than no link,
 * because it reads as "the trace is missing" instead of "tracing was off".
 */
export function getTraceUrl(traceId: string | undefined | null): string | null {
  if (!traceId) return null;
  const base = grafanaBaseUrl();
  if (!base) return null;

  // Grafana Explore takes its state as a JSON blob in the `left` query param.
  const pane = {
    datasource: TEMPO_DATASOURCE_UID,
    queries: [{ refId: "A", queryType: "traceql", query: traceId }],
    range: { from: "now-24h", to: "now" },
  };
  return `${base.replace(/\/$/, "")}/explore?left=${encodeURIComponent(JSON.stringify(pane))}`;
}

/** Short, stable display form of a 128-bit trace id (full id is 32 hex chars). */
export function shortTraceId(traceId: string | undefined | null): string {
  if (!traceId) return "";
  return traceId.length > 12 ? `${traceId.slice(0, 12)}…` : traceId;
}
