import { DataSourceBadge } from "@/components/data-source-badge";
import { getDeploymentFeed } from "@/lib/activity-data";
import { HistoryLogTable } from "@/components/history-log-table";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const [prov, dep] = await Promise.all([getDeploymentFeed(["provision"]), getDeploymentFeed(["deploy"])]);

  return (
    <div className="mx-auto max-w-[1800px] space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="eyebrow mb-3">Activity history</p>
          <h2 className="text-3xl font-semibold tracking-tight">History</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Every provisioning and deployment run — click <em>View trace</em> for the full lifecycle.
          </p>
        </div>
        <DataSourceBadge source={dep.source} />
      </div>

      <HistoryLogTable title="Provisioning Logs" accent="#69d3a7" variant="provision" rows={prov.deployments} />
      <HistoryLogTable title="Deployment Logs" accent="#8ab4f8" variant="deploy" rows={dep.deployments} />
    </div>
  );
}
