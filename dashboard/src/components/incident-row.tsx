import Link from "next/link";
import { Incident } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";

const severityColors = {
  P1: "border-red-300/45 bg-red-400/20 text-red-100",
  P2: "border-yellow-300/45 bg-yellow-400/18 text-yellow-100",
  P3: "border-blue-300/45 bg-blue-400/18 text-blue-100",
};

export function IncidentRow({ incident }: { incident: Incident }) {
  const confidencePct = typeof incident.confidence === "number" ? Math.round(incident.confidence * 100) : null;
  return (
    <Link href={`/incidents/${incident.id}`} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-[#8ab4f8]/60 rounded-xl">
    <article className={`group relative flex flex-col gap-3 overflow-hidden rounded-xl border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_50px_rgba(0,0,0,0.28)] ${incident.severity === "P1" ? "border-red-400/45 bg-[linear-gradient(110deg,rgba(127,29,29,0.38),rgba(48,49,52,0.96)_38%)]" : incident.severity === "P2" ? "border-yellow-400/40 bg-[linear-gradient(110deg,rgba(113,82,10,0.30),rgba(48,49,52,0.96)_38%)]" : "border-blue-400/35 bg-[linear-gradient(110deg,rgba(30,64,175,0.22),rgba(48,49,52,0.96)_38%)]"}`}>
      <div className={`absolute bottom-0 left-0 top-0 w-0.5 ${incident.severity === "P1" ? "bg-[var(--danger)]" : incident.severity === "P2" ? "bg-[var(--warning)]" : "bg-[var(--accent)]"}`} />
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`rounded border px-2 py-1 text-xs font-bold tracking-wide ${severityColors[incident.severity]}`}>
          {incident.severity}
        </span>
        <span className={`inline-flex items-center gap-1.5 rounded border py-0.5 pl-1 pr-2 text-[10px] font-bold tracking-wide ${providerBadgeStyles[incident.provider]}`}>
          <span className="flex h-5 w-5 items-center justify-center rounded bg-white p-0.5"><ProviderLogo provider={incident.provider} size="sm" /></span>
          {incident.provider === "gcp" ? "GOOGLE CLOUD" : incident.provider === "azure" ? "MICROSOFT AZURE" : incident.provider === "onprem" ? "ON-PREM" : "AWS"}
        </span>
        <span className="rounded bg-black/15 px-1.5 py-1 text-[10px] font-bold tracking-wide text-[#d8dde5]">{incident.mode}</span>
        {confidencePct !== null && (
          <span className="rounded bg-[#c4b5fd]/15 px-1.5 py-1 text-[10px] font-bold text-[#d9ccff]" title="LLM analysis confidence">🧠 {confidencePct}%</span>
        )}
        <span className="ml-auto text-xs text-[var(--muted)]">
          {new Date(incident.created_at).toLocaleString()}
        </span>
        {incident.resolved ? (
          <span className="rounded bg-emerald-400/12 px-1.5 py-1 text-[10px] font-bold text-[var(--success)]">✓ RESOLVED</span>
        ) : (
          <span className="rounded bg-yellow-400/15 px-1.5 py-1 text-[10px] font-bold text-[var(--warning)]">● OPEN</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <code className="text-xs text-[var(--muted)]">{incident.id}</code>
        <span className="font-medium text-sm">{incident.alarm_name}</span>
      </div>
      <p className="line-clamp-2 text-sm leading-6 text-[var(--muted)]">{incident.root_cause}</p>
      {incident.reconciliation && !incident.reconciliation.grounded && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-400/[0.08] p-2.5 text-[11px] leading-5 text-amber-100">
          <div className="flex items-center gap-2 font-bold">
            <span>🛡️ Reconciliation gate</span>
            <span className="rounded bg-amber-400/20 px-1.5 py-0.5 font-mono text-[10px]">
              grounding {incident.reconciliation.grounding_ratio.toFixed(2)}
            </span>
            {incident.reconciliation.mode_override && (
              <span className="rounded bg-amber-400/20 px-1.5 py-0.5 font-mono text-[10px]">
                AUTO → {incident.reconciliation.mode_override}
              </span>
            )}
          </div>
          {incident.reconciliation.issues.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-amber-100/80">
              {incident.reconciliation.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {incident.reconciliation?.grounded && (
        <span className="inline-flex w-fit items-center gap-1 rounded bg-emerald-400/12 px-1.5 py-0.5 text-[10px] font-bold text-[var(--success)]">
          🛡️ grounded {incident.reconciliation.grounding_ratio.toFixed(2)}
        </span>
      )}
      {incident.executed_actions.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {incident.executed_actions.map((action) => (
            <span
              key={action}
              className="rounded-md border border-white/5 bg-white/[0.035] px-1.5 py-1 font-mono text-[10px] text-[#cbd6e9]"
            >
              {action}
            </span>
          ))}
        </div>
      )}
      <span className="pointer-events-none absolute bottom-3 right-4 text-xs text-[var(--muted)] opacity-0 transition-opacity group-hover:opacity-100">
        View analysis →
      </span>
    </article>
    </Link>
  );
}
