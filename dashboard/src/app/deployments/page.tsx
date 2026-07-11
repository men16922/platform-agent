import { DataSourceBadge } from "@/components/data-source-badge";
import { getDeploymentFeed } from "@/lib/activity-data";
import { DeploymentsControl } from "@/components/deployments-control";

export const dynamic = "force-dynamic";

export default async function DeploymentsPage() {
  const { deployments, source } = await getDeploymentFeed();

  return (
    <div className="mx-auto max-w-7xl space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
        <p className="eyebrow mb-3">Guarded delivery pipeline</p>
        <h2 className="text-3xl font-semibold tracking-tight">Deployments</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          AI Agent-driven deployments across 4 cloud providers
        </p>
        </div>
        <DataSourceBadge source={source} />
      </div>

      {/* Pipeline visualization */}
      <div className="surface overflow-hidden p-5">
        <div className="mb-5 flex items-start justify-between"><div><p className="eyebrow">Deployment pipeline</p><p className="mt-2 text-sm font-medium">Spec → plan → guard → deploy → validate</p></div><span className="flex items-center gap-2 text-xs text-[var(--success)]"><span className="pulse-dot" />{deployments.length} runs today</span></div>
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

      {/* Deployments controller (table + trigger modals) */}
      <DeploymentsControl initialDeployments={deployments} />
    </div>
  );
}
