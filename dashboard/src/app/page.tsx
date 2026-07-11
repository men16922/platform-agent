import { StatusCard } from "@/components/status-card";
import { IncidentRow } from "@/components/incident-row";
import { DataSourceBadge } from "@/components/data-source-badge";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { getIncidentFeed } from "@/lib/incident-data";
import { getDeploymentFeed, getProviderHealthFeed } from "@/lib/activity-data";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [{ incidents, source }, { deployments }, { health }] = await Promise.all([
    getIncidentFeed(),
    getDeploymentFeed(),
    getProviderHealthFeed(),
  ]);
  const recentIncidents = incidents.slice(0, 3);
  const recentDeployments = deployments.slice(0, 4);
  const attentionDeployment = deployments.find((deployment) => deployment.status !== "success");

  return (
    <div className="mx-auto max-w-[1800px] space-y-7">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow mb-3">Operations command center</p>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Platform overview</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--muted)]">
            Autonomous visibility across AWS, GCP, Azure, and your on-prem estate.
          </p>
        </div>
        <div className="surface flex items-center gap-3 px-4 py-3 text-xs">
          <span className="pulse-dot" />
          <div><p className="font-semibold text-[var(--foreground)]">Incident telemetry</p><p className="mt-0.5 text-[var(--muted)]">Read-only feed</p></div>
          <DataSourceBadge source={source} />
        </div>
      </div>

      <section className="surface relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-[#8ab4f8]/12 blur-3xl" />
        <div className="relative grid gap-7 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <div className="mb-4 flex items-center gap-2"><span className="pulse-dot" /><span className="eyebrow text-[#c4ddff]">Autonomous control plane</span></div>
            <h3 className="max-w-lg text-2xl font-semibold leading-tight tracking-tight">Signals become verified actions — without losing human control.</h3>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">Every incident is evaluated against a provider-aware runbook, policy guard, and validation step before it reaches production.</p>
            <div className="mt-6 grid grid-cols-4 gap-2">
              <PipelineNode label="Detect" detail="Signals" active />
              <PipelineNode label="Analyze" detail="Root cause" active />
              <PipelineNode label="Decide" detail="Policy" active />
              <PipelineNode label="Execute" detail="Validate" active />
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-[#292a2d] p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between"><div><p className="eyebrow">Active run</p><p className="mt-1 text-sm font-medium">AWS remediation workflow</p></div><span className="rounded-md bg-emerald-400/10 px-2 py-1 text-[10px] font-bold tracking-wide text-[var(--success)]">VALIDATED</span></div>
            <div className="mb-4 flex items-end gap-1.5" aria-label="Response telemetry trend">
              {[24, 35, 28, 52, 46, 70, 54, 82, 66, 91, 74, 100].map((height, index) => <span key={index} className="flex-1 rounded-t-sm bg-gradient-to-t from-[#4285f4] to-[#8ab4f8] opacity-80" style={{ height: `${height * 0.34}px` }} />)}
            </div>
            <div className="grid grid-cols-3 border-t border-white/7 pt-3 text-xs"><div><p className="text-[var(--muted)]">Response time</p><p className="mt-1 font-semibold">1m 24s</p></div><div><p className="text-[var(--muted)]">Guard checks</p><p className="mt-1 font-semibold text-[var(--success)]">4 / 4</p></div><div><p className="text-[var(--muted)]">Mode</p><p className="mt-1 font-semibold text-[#c4ddff]">AUTO</p></div></div>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between"><h3 className="eyebrow">Provider health</h3><span className="text-xs text-[var(--muted)]">4 regions monitored</span></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {health.map((h) => (
            <StatusCard key={h.provider} health={h} />
          ))}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatBox label="Incidents observed" value={incidents.length.toString()} detail="Current incident feed" />
        <StatBox label="Autonomously resolved" value={incidents.filter(i => i.resolved).length.toString()} color="success" detail="Resolved by runbook" />
        <StatBox label="Deployments today" value={deployments.length.toString()} detail={`${deployments.filter(d => d.status !== "success").length || "No"} needs attention`} />
        <StatBox label="Validation checks" value="490" color="success" detail="All passing" />
      </section>

      <section className="grid gap-7 xl:grid-cols-[1.25fr_0.75fr]">
        <div>
          <div className="mb-3 flex items-center justify-between"><h3 className="eyebrow">Incident feed</h3><Link href="/incidents" className="text-xs text-[#aaa1ff] hover:underline">View all →</Link></div>
          <div className="space-y-3">
          {recentIncidents.map((incident) => (
            <IncidentRow key={incident.id} incident={incident} />
          ))}
          </div>
        </div>
        <div className="surface overflow-hidden p-5">
          <div className="mb-4 flex items-start justify-between"><div><h3 className="eyebrow">Deployment posture</h3><p className="mt-2 text-sm font-medium">Autonomous delivery control</p></div><span className="rounded-md bg-[var(--accent-soft)] px-2 py-1 text-[10px] font-bold tracking-wide text-[#c4ddff]">AI ORCHESTRATED</span></div>
          {attentionDeployment && <div className="rounded-xl border border-red-400/45 bg-red-500/13 p-4 shadow-[inset_3px_0_0_var(--danger)]"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1"><ProviderLogo provider={attentionDeployment.provider} size="sm" /></span><div><p className="text-[10px] font-bold tracking-[0.12em] text-[#ffb4ae]">GUARD INTERVENTION</p><p className="mt-1 text-sm font-semibold">{attentionDeployment.service} <span className="font-mono text-xs font-normal">{attentionDeployment.version}</span></p></div></div><span className="rounded bg-red-400/18 px-2 py-1 text-[10px] font-bold text-[#ffb4ae]">ACTION NEEDED</span></div><div className="mt-4 grid grid-cols-4 gap-1.5 text-center text-[10px] font-semibold"><PipelineStatus label="Build" state="done" /><PipelineStatus label="Push" state="done" /><PipelineStatus label="Deploy" state="done" /><PipelineStatus label="Validate" state="blocked" /></div><p className="mt-3 text-xs leading-5 text-[#f6c3c0]">Validation failed after {attentionDeployment.duration_sec}s. Rollback is ready for review.</p></div>}
          <div className="mt-5"><div className="mb-2 flex items-center justify-between"><p className="eyebrow">Verified today</p><span className="text-xs text-[var(--success)]">4 successful</span></div><div className="space-y-2">{recentDeployments.slice(0, 3).map((dep) => (<div key={dep.id} className="flex items-center gap-3 rounded-lg bg-black/10 px-3 py-2.5"><span className="flex h-6 w-6 items-center justify-center rounded bg-emerald-400/15 text-xs text-[var(--success)]">✓</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{dep.service} <span className="font-mono font-normal text-[var(--muted)]">{dep.version}</span></p><p className="mt-0.5 text-[10px] text-[var(--muted)]">{dep.provider.toUpperCase()} · {dep.duration_sec}s</p></div><span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" /></div>))}</div></div>
        </div>
      </section>

      <section className="surface overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--card-border)] px-5 py-4"><div><p className="eyebrow">Deployment register</p><p className="mt-1 text-sm font-medium">Recent validated changes</p></div><span className="text-xs text-[var(--muted)]">Last 24 hours</span></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
              <tr>
              <th className="px-5 py-3 text-left font-semibold">Service</th><th className="px-5 py-3 text-left font-semibold">Version</th><th className="px-5 py-3 text-left font-semibold">Provider</th><th className="px-5 py-3 text-left font-semibold">Agent</th><th className="px-5 py-3 text-left font-semibold">Status</th><th className="px-5 py-3 text-right font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {recentDeployments.map((dep) => (
                <tr key={dep.id} className="border-t border-white/6 transition-colors hover:bg-white/[0.025]">
                  <td className="px-5 py-3.5 font-medium">{dep.service}</td><td className="px-5 py-3.5"><code className="text-xs text-[#cbd6e9]">{dep.version}</code></td><td className="px-5 py-3.5">
                    <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px] font-semibold tracking-wide ${providerBadgeStyles[dep.provider]}`}>
                      <span className="flex h-4 w-4 items-center justify-center rounded bg-white p-0.5"><ProviderLogo provider={dep.provider} size="sm" /></span>{dep.provider === "gcp" ? "GCP" : dep.provider === "azure" ? "AZURE" : dep.provider === "onprem" ? "ON-PREM" : "AWS"}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-[var(--muted)]">{dep.agent}</td><td className="px-5 py-3.5">
                    <span className={`text-xs font-medium ${dep.status === "success" ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                      {dep.status === "success" ? "✓" : "✗"} {dep.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right text-xs text-[var(--muted)]">{dep.duration_sec}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function PipelineNode({ label, detail, active }: { label: string; detail: string; active: boolean }) {
  return <div className="relative rounded-lg border border-white/8 bg-white/[0.025] p-2.5"><span className={`mb-3 block h-1.5 w-1.5 rounded-full ${active ? "bg-[var(--success)] shadow-[0_0_10px_var(--success)]" : "bg-[var(--muted)]"}`} /><p className="text-xs font-semibold">{label}</p><p className="mt-1 text-[10px] text-[var(--muted)]">{detail}</p></div>;
}

function PipelineStatus({ label, state }: { label: string; state: "done" | "blocked" }) {
  return <div className={`rounded-md border px-1 py-2 ${state === "done" ? "border-emerald-300/30 bg-emerald-300/10 text-[var(--success)]" : "border-red-300/40 bg-red-300/15 text-[#ffb4ae]"}`}>{state === "done" ? "✓ " : "! "}{label}</div>;
}

function StatBox({ label, value, color, detail }: { label: string; value: string; color?: string; detail: string }) {
  const textColor = color === "success" ? "text-[var(--success)]" : "text-[var(--foreground)]";
  return (
    <div className="surface p-4">
      <div className="eyebrow mb-3">{label}</div><div className={`text-3xl font-semibold tracking-tight ${textColor}`}>{value}</div><div className="mt-2 text-xs text-[var(--muted)]">{detail}</div>
    </div>
  );
}
