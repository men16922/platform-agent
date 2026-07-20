import Link from "next/link";
import { getIncidentById } from "@/lib/incident-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { DataSourceBadge } from "@/components/data-source-badge";
import type { Incident } from "@/lib/mock-data";

export const dynamic = "force-dynamic";

const severityBadge: Record<Incident["severity"], string> = {
  P1: "border-red-300/45 bg-red-400/20 text-red-100",
  P2: "border-yellow-300/45 bg-yellow-400/18 text-yellow-100",
  P3: "border-blue-300/45 bg-blue-400/18 text-blue-100",
};

// Which brain analysed this incident — ties the record back to the model that
// produced the root cause. On-prem runs the local Qwen (offline); each cloud
// uses its native model.
const analystByProvider: Record<Incident["provider"], string> = {
  onprem: "Local Qwen (MLX, offline)",
  aws: "Bedrock · Claude",
  gcp: "Vertex AI · Gemini",
  azure: "Azure OpenAI · GPT",
};

const providerLabel: Record<Incident["provider"], string> = {
  onprem: "ON-PREM",
  aws: "AWS",
  gcp: "GOOGLE CLOUD",
  azure: "MICROSOFT AZURE",
};

export default async function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { incident, source } = await getIncidentById(id);

  if (!incident) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Link href="/incidents" className="text-xs text-[var(--muted)] hover:text-white">← Incidents</Link>
        <div className="surface p-8 text-center text-sm text-[var(--muted)]">
          No incident found for <code className="text-[#cbd6e9]">{id}</code>.
        </div>
      </div>
    );
  }

  const hasConfidence = typeof incident.confidence === "number";
  const confidencePct = hasConfidence ? Math.round((incident.confidence as number) * 100) : null;

  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <div className="flex items-center justify-between gap-4">
        <Link href="/incidents" className="text-xs text-[#8ab4f8] hover:underline">← Incidents</Link>
        <DataSourceBadge source={source} />
      </div>

      {/* Header */}
      <div className="space-y-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#8ab4f8]">Autonomous response record</p>
        <div className="flex flex-wrap items-center gap-3">
          <span className={`rounded border px-2 py-1 text-xs font-bold tracking-wide ${severityBadge[incident.severity]}`}>
            {incident.severity}
          </span>
          <h2 className="text-2xl font-semibold tracking-tight text-[#e6edf7]">{incident.alarm_name}</h2>
          <span className={`inline-flex items-center gap-1.5 rounded border py-0.5 pl-1 pr-2 text-[10px] font-bold tracking-wide ${providerBadgeStyles[incident.provider]}`}>
            <span className="flex h-5 w-5 items-center justify-center rounded bg-white p-0.5"><ProviderLogo provider={incident.provider} size="sm" /></span>
            {providerLabel[incident.provider]}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--muted)]">
          <code className="text-[#a9c7ff]">{incident.id}</code>
          <span className="rounded bg-black/15 px-1.5 py-0.5 font-bold text-[#d8dde5]">{incident.mode}</span>
          {incident.resolved ? (
            <span className="rounded bg-emerald-400/12 px-1.5 py-0.5 font-bold text-[var(--success)]">✓ RESOLVED</span>
          ) : (
            <span className="rounded bg-yellow-400/15 px-1.5 py-0.5 font-bold text-[var(--warning)]">● OPEN</span>
          )}
          <span suppressHydrationWarning>{new Date(incident.created_at).toLocaleString()}</span>
        </div>
      </div>

      {/* LLM analysis — the star of the detail view */}
      <section className="space-y-2">
        <SectionTitle accent="#c4b5fd">LLM root-cause analysis</SectionTitle>
        <div className="surface space-y-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-2 text-[11px] font-semibold text-[#d9ccff]">
              🧠 {analystByProvider[incident.provider]}
            </span>
            {hasConfidence ? (
              <span className="font-mono text-[11px] text-[var(--muted)]">confidence {confidencePct}%</span>
            ) : (
              <span className="font-mono text-[11px] text-[var(--muted)]">confidence n/a</span>
            )}
          </div>

          {hasConfidence && (
            <div className="space-y-1">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/8">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${confidencePct}%`,
                    background:
                      (confidencePct as number) >= 70
                        ? "var(--success)"
                        : (confidencePct as number) >= 40
                          ? "var(--warning)"
                          : "var(--danger)",
                  }}
                />
              </div>
              {confidencePct === 0 && (
                <p className="text-[10px] text-[var(--muted)]">
                  0% = heuristic fallback (the model was unreachable, e.g. offline pod without a brain).
                </p>
              )}
            </div>
          )}

          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[#e6edf7]">{incident.root_cause}</p>
        </div>
      </section>

      {/* Decision */}
      <section className="space-y-2">
        <SectionTitle accent="#8ab4f8">Decision</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Fact label="Severity" value={incident.severity} />
          <Fact label="Remediation mode" value={incident.mode} />
          <Fact label="Runbook" value={incident.runbook_id} mono />
          <Fact label="Status" value={incident.resolved ? "Resolved" : "Open"} />
        </div>
      </section>

      {/* Actions */}
      <section className="space-y-2">
        <SectionTitle accent="#69d3a7">
          Executed actions <span className="font-normal text-[var(--muted)]">— {incident.executed_actions.length}</span>
        </SectionTitle>
        {incident.executed_actions.length === 0 ? (
          <div className="surface p-4 text-xs text-[var(--muted)]">
            No actions executed{incident.mode === "APPROVE" ? " — remediation was approval-gated." : "."}
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {incident.executed_actions.map((action) => (
              <span key={action} className="rounded-md border border-white/6 bg-white/[0.035] px-2 py-1 font-mono text-[11px] text-[#cbd6e9]">
                {action}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Reconciliation gate */}
      {incident.reconciliation && (
        <section className="space-y-2">
          <SectionTitle accent="#f5c563">Reconciliation gate</SectionTitle>
          <div
            className={`surface space-y-2 p-4 text-xs leading-5 ${incident.reconciliation.grounded ? "text-[var(--success)]" : "text-amber-100"}`}
          >
            <div className="flex flex-wrap items-center gap-2 font-bold">
              <span>🛡️ {incident.reconciliation.grounded ? "Grounded in detector evidence" : "Not grounded — decision downgraded"}</span>
              <span className="rounded bg-white/8 px-1.5 py-0.5 font-mono text-[10px]">
                grounding {incident.reconciliation.grounding_ratio.toFixed(2)}
              </span>
              {incident.reconciliation.mode_override && (
                <span className="rounded bg-amber-400/20 px-1.5 py-0.5 font-mono text-[10px]">
                  AUTO → {incident.reconciliation.mode_override}
                </span>
              )}
            </div>
            {incident.reconciliation.issues.length > 0 && (
              <ul className="list-disc pl-4 text-amber-100/80">
                {incident.reconciliation.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function SectionTitle({ children, accent }: { children: React.ReactNode; accent: string }) {
  return (
    <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[#9fb0c9]">
      <span className="h-3 w-0.5 rounded" style={{ background: accent }} />
      {children}
    </h3>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="surface p-3">
      <p className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</p>
      <p className={`mt-1.5 text-sm text-[#e6edf7] ${mono ? "font-mono text-xs" : ""}`}>{value}</p>
    </div>
  );
}
