import Link from "next/link";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import { DataSourceBadge } from "@/components/data-source-badge";
import { AgentDeployChat } from "@/components/agent-deploy-chat";
import { AgentCard } from "@/components/agent-card";
import { getAgentActivityFeed } from "@/lib/activity-data";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const { activities, source } = await getAgentActivityFeed();

  return (
    <div className="mx-auto max-w-6xl space-y-7">
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
        <AgentCard name="On-Prem Agent" provider="On-Premise" llm="Any LLM" cloud="onprem" />
      </div>

      {/* Deploy via chat — AI Model Router */}
      <AgentDeployChat />

      {/* Activity timeline */}
      <section>
        <div className="mb-3 flex items-center justify-between"><h3 className="eyebrow">Live activity timeline</h3><span className="text-xs text-[var(--muted)]">{activities.length} verified actions</span></div>
        <div className="space-y-3">
          {activities.map((activity) => {
            const model = activity.model ?? modelIdFromAgent(activity.agent);
            const cls = "block surface relative overflow-hidden p-4 transition-colors hover:border-[#52647f]";
            const body = (
              <>
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${providerBadgeStyles[activity.provider]}`}>
                    <ProviderLogo provider={activity.provider} size="sm" />
                    {activity.provider.toUpperCase()}
                  </span>
                  <ModelLogo model={model} />
                  <span className="font-medium text-sm">{activity.agent}</span>
                  <span className="text-xs text-[var(--muted)]">—</span>
                  <span className="text-sm">{activity.action}</span>
                  <span className="ml-auto text-xs text-[var(--muted)]">
                    {new Date(activity.created_at).toLocaleTimeString()}
                  </span>
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${activity.status === "success" ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"}`}>
                    {activity.status === "success" ? "COMPLETE" : "FAILED"}
                  </span>
                </div>
                <div className="flex gap-1 flex-wrap items-center">
                  {activity.tool_calls.map((tool, ti) => (
                    <code
                      key={`${tool}-${ti}`}
                      className="rounded-md border border-white/5 bg-white/[0.035] px-1.5 py-1 text-[10px] text-[var(--muted)]"
                    >
                      {tool}
                    </code>
                  ))}
                  {activity.deployment_id && (
                    <span className="ml-auto text-[10px] font-medium text-[#8ab4f8]">View trace →</span>
                  )}
                </div>
              </>
            );
            return activity.deployment_id ? (
              <Link key={activity.id} href={`/deployments/${activity.deployment_id}`} className={cls}>
                {body}
              </Link>
            ) : (
              <div key={activity.id} className={cls}>{body}</div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
