import { mockDeployments } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";

const statusIcon = {
  success: { icon: "✓", color: "text-[var(--success)]" },
  failed: { icon: "✗", color: "text-[var(--danger)]" },
  "rolling-back": { icon: "↺", color: "text-[var(--warning)]" },
};

export default function DeploymentsPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-7">
      <div>
        <p className="eyebrow mb-3">Guarded delivery pipeline</p>
        <h2 className="text-3xl font-semibold tracking-tight">Deployments</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          AI Agent-driven deployments across 4 cloud providers
        </p>
      </div>

      {/* Pipeline visualization */}
      <div className="surface overflow-hidden p-5">
        <div className="mb-5 flex items-start justify-between"><div><p className="eyebrow">Deployment pipeline</p><p className="mt-2 text-sm font-medium">Spec → plan → guard → deploy → validate</p></div><span className="flex items-center gap-2 text-xs text-[var(--success)]"><span className="pulse-dot" />5 runs today</span></div>
        <div className="flex flex-wrap items-center gap-2">
          {["Spec", "Plan", "Guard", "Build", "Push", "Deploy", "Validate"].map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className={`rounded-lg border px-3 py-2 text-xs font-semibold ${step === "Guard" || step === "Validate" ? "border-emerald-400/25 bg-emerald-400/10 text-[var(--success)]" : "border-[#8ab4f8]/25 bg-[var(--accent-soft)] text-[#c4ddff]"}`}>
                {step}
              </span>
              {i < 6 && <span className="text-[var(--muted)]">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Deployments table */}
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              <th className="text-left p-3">ID</th>
              <th className="text-left p-3">Service</th>
              <th className="text-left p-3">Version</th>
              <th className="text-left p-3">Provider</th>
              <th className="text-left p-3">Environment</th>
              <th className="text-left p-3">Agent</th>
              <th className="text-left p-3">Status</th>
              <th className="text-right p-3">Duration</th>
              <th className="text-right p-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {mockDeployments.map((dep) => {
              const status = statusIcon[dep.status];
              return (
                <tr key={dep.id} className="border-t border-white/6 transition-colors hover:bg-white/[0.025]">
                  <td className="p-3">
                    <code className="text-xs text-[var(--muted)]">{dep.id}</code>
                  </td>
                  <td className="p-3 font-medium">{dep.service}</td>
                  <td className="p-3"><code className="text-xs">{dep.version}</code></td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px] font-semibold ${providerBadgeStyles[dep.provider]}`}>
                      <ProviderLogo provider={dep.provider} size="sm" />{dep.provider === "gcp" ? "GCP" : dep.provider === "azure" ? "Azure" : dep.provider === "onprem" ? "On-Prem" : "AWS"}
                    </span>
                  </td>
                  <td className="p-3 text-[var(--muted)]">{dep.environment}</td>
                  <td className="p-3 text-xs text-[var(--muted)]">{dep.agent}</td>
                  <td className="p-3">
                    <span className={status.color}>
                      {status.icon} {dep.status}
                    </span>
                  </td>
                  <td className="p-3 text-right text-[var(--muted)]">{dep.duration_sec}s</td>
                  <td className="p-3 text-right text-[var(--muted)] text-xs">
                    {new Date(dep.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
