import { DataSourceBadge } from "@/components/data-source-badge";
import { getDeploymentFeed } from "@/lib/activity-data";
import { ProvisioningControl } from "@/components/provisioning-control";

export const dynamic = "force-dynamic";

export default async function ProvisioningPage() {
  const { deployments, source } = await getDeploymentFeed(["provision"]);

  return (
    <div className="mx-auto max-w-[1800px] space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="eyebrow mb-3">Cluster lifecycle</p>
          <h2 className="text-3xl font-semibold tracking-tight">Provisioning</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Cluster provisioning &amp; teardown across 4 infrastructure targets
          </p>
        </div>
        <DataSourceBadge source={source} />
      </div>

      <ProvisioningControl initialDeployments={deployments} />
    </div>
  );
}
