import { StatusCard } from "@/components/status-card";
import { IncidentRow } from "@/components/incident-row";
import { DataSourceBadge } from "@/components/data-source-badge";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { getIncidentFeed } from "@/lib/incident-data";
import { getDeploymentFeed, getProviderHealthFeed } from "@/lib/activity-data";
import Link from "next/link";
import { deploymentDuration } from "@/lib/deployment-duration";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [{ incidents, source }, { deployments, source: deploymentSource }, { health, source: healthSource, notice: healthNotice }] = await Promise.all([
    getIncidentFeed(),
    getDeploymentFeed(),
    getProviderHealthFeed(),
  ]);
  const recentIncidents = incidents.slice(0, 3);
  const recentDeployments = deployments.slice(0, 4);
  const successfulDeployments = deployments.filter((deployment) => deployment.status === "success");
  const attentionDeployments = deployments.filter((deployment) => deployment.status === "failed" || deployment.status === "rolling-back" || deployment.status === "unknown");
  const attentionDeployment = attentionDeployments[0];
  const latestDeployment = recentDeployments[0];

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
            <div className="mb-4 flex items-center gap-2"><span className="pulse-dot" /><span className="eyebrow text-[#c4ddff]">Operations workflow</span></div>
            <h3 className="max-w-lg text-2xl font-semibold leading-tight tracking-tight">Review the evidence behind each action.</h3>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">Follow recorded incidents and deployments, then inspect the execution trace before deciding what to do next.</p>
            <div className="mt-6 grid grid-cols-4 gap-2">
              <PipelineNode label="Detect" detail="Signals" active={false} />
              <PipelineNode label="Analyze" detail="Analysis" active={false} />
              <PipelineNode label="Decide" detail="Policy" active={false} />
              <PipelineNode label="Execute" detail="Validate" active={false} />
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-[#292a2d] p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between"><p className="eyebrow">Latest deployment record</p><DataSourceBadge source={deploymentSource} /></div>
            {latestDeployment ? <>
              <p className="text-sm font-medium">{latestDeployment.service} <span className="font-mono text-[var(--muted)]">{latestDeployment.version}</span></p>
              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between"><dt>Recorded status</dt><dd>{latestDeployment.status}</dd></div>
                <div className="flex justify-between"><dt>Namespace</dt><dd>{latestDeployment.namespace ?? "Not recorded"}</dd></div>
                <div className="flex justify-between"><dt>Recorded at</dt><dd>{latestDeployment.created_at}</dd></div>
              </dl>
              <Link href="/deployments" className="mt-4 inline-block text-xs text-[#aaa1ff] hover:underline">Review deployment →</Link>
            </> : <p className="text-sm text-[var(--muted)]">No deployment records available.</p>}
            <p className="mt-4 text-xs leading-5 text-[var(--muted)]">Recorded results do not establish current cluster health.</p>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between"><h3 className="eyebrow">Provider health</h3><DataSourceBadge source={healthSource} /></div>
        {health.length === 0 && <p className="surface p-4 text-sm text-[var(--muted)]">No provider health observations available. {healthNotice}</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {health.map((h) => (
            <StatusCard key={h.provider} health={h} />
          ))}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatBox label="Incidents observed" value={incidents.length.toString()} detail="Current incident feed" />
        <StatBox label="Resolved records" value={incidents.filter(i => i.resolved).length.toString()} color="success" detail="Marked resolved in this feed" />
        <StatBox label="Deployments in feed" value={deployments.length.toString()} detail={`${attentionDeployments.length} need attention`} />
        <StatBox label="Reported successful" value={successfulDeployments.length.toString()} detail="Deployment records marked success" />
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
          {attentionDeployment && <div className="rounded-xl border border-red-400/45 bg-red-500/13 p-4">
            <p className="text-sm font-semibold">{attentionDeployment.service} {attentionDeployment.version}</p>
            <p className="mt-2 text-xs">Recorded status: {attentionDeployment.status}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">Review the execution trace and current workload state before recovery.</p>
            <Link href="/deployments" className="mt-3 inline-block text-xs text-[#aaa1ff] hover:underline">Review deployment →</Link>
          </div>}
          <div className="mt-5"><div className="mb-2 flex items-center justify-between"><p className="eyebrow">Successful records</p><span className="text-xs text-[var(--muted)]">{successfulDeployments.length} in feed</span></div><div className="space-y-2">{successfulDeployments.slice(0, 3).map((dep) => (<div key={dep.id} className="flex items-center gap-3 rounded-lg bg-black/10 px-3 py-2.5"><span className="flex h-6 w-6 items-center justify-center rounded bg-emerald-400/15 text-xs text-[var(--success)]">✓</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{dep.service} <span className="font-mono font-normal text-[var(--muted)]">{dep.version}</span></p><p className="mt-0.5 text-[10px] text-[var(--muted)]">{dep.provider.toUpperCase()} · {deploymentDuration(dep)}</p></div></div>))}</div></div>
        </div>
      </section>

      <section className="surface overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--card-border)] px-5 py-4"><div><p className="eyebrow">Deployment register</p><p className="mt-1 text-sm font-medium">Recent deployment records</p></div><span className="text-xs text-[var(--muted)]">Latest records in feed</span></div>
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
                    <span className={`text-xs font-medium ${dep.status === "success" ? "text-[var(--success)]" : dep.status === "failed" ? "text-[var(--danger)]" : "text-[var(--muted)]"}`}>
                      {dep.status === "success" ? "✓" : dep.status === "failed" ? "✗" : "·"} {dep.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right text-xs text-[var(--muted)]">{deploymentDuration(dep)}</td>
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

function StatBox({ label, value, color, detail }: { label: string; value: string; color?: string; detail: string }) {
  const textColor = color === "success" ? "text-[var(--success)]" : "text-[var(--foreground)]";
  return (
    <div className="surface p-4">
      <div className="eyebrow mb-3">{label}</div><div className={`text-3xl font-semibold tracking-tight ${textColor}`}>{value}</div><div className="mt-2 text-xs text-[var(--muted)]">{detail}</div>
    </div>
  );
}
