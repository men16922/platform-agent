import { DataSourceBadge } from "@/components/data-source-badge";
import { AgentDeployChat } from "@/components/agent-deploy-chat";
import { AgentCard } from "@/components/agent-card";
import { ActivityTimeline } from "@/components/activity-timeline";
import { OnPremRuntimePanel } from "@/components/onprem-runtime-panel";
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

      {/* Agent summary */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <AgentCard name="Strands Agent" provider="AWS" llm="Bedrock Claude" cloud="aws" />
        <AgentCard name="ADK Agent" provider="Google Cloud" llm="Gemini 3.5 Flash" cloud="gcp" />
        <AgentCard name="MS Agent" provider="Microsoft Azure" llm="GPT-5.4" cloud="azure" />
        <AgentCard name="On-Prem Agent" provider="On-Premise" llm="Local Qwen + kagent" cloud="onprem" />
      </div>

      <OnPremRuntimePanel />

      {/* Deploy via chat — AI Model Router */}
      <AgentDeployChat />

      {/* Activity timeline (paginated, 10 per page) */}
      <ActivityTimeline activities={activities} />
    </div>
  );
}
