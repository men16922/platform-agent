import { DataSourceBadge } from "@/components/data-source-badge";
import { ActivityTimeline } from "@/components/activity-timeline";
import { AgentsWorkspace } from "@/components/agents-workspace";
import { getAgentActivityFeed } from "@/lib/activity-data";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const { activities, source } = await getAgentActivityFeed();

  return (
    <div className="mx-auto max-w-[1800px] space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
        <p className="eyebrow mb-3">Reasoning and execution trace</p>
        <h2 className="text-3xl font-semibold tracking-tight">Agent activity</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          AI Agent autonomous tool-calling log — each agent selects and executes tools without human intervention
        </p>
        </div>
        <DataSourceBadge source={source} />
      </div>

      <AgentsWorkspace />

      {/* Activity timeline (paginated, 10 per page) */}
      <ActivityTimeline activities={activities} />
    </div>
  );
}
