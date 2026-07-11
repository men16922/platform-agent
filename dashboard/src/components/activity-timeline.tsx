"use client";

import Link from "next/link";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import type { AgentActivity } from "@/lib/mock-data";

const RECENT_ACTIVITY_LIMIT = 5;

export function ActivityTimeline({ activities }: { activities: AgentActivity[] }) {
  const recentActivities = activities.slice(0, RECENT_ACTIVITY_LIMIT);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="eyebrow">Recent activity</h3>
        <span className="text-xs text-[var(--muted)]">
          Latest {recentActivities.length} of {activities.length} verified actions
        </span>
      </div>

      <div className="space-y-3">
        {recentActivities.length === 0 && (
          <p className="text-xs text-[var(--muted)] py-6 text-center">No activity yet.</p>
        )}
        {recentActivities.map((activity) => {
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
                {/* Locale/timezone-dependent: server (UTC/en-US) and client (local) format
                    the same instant differently, so suppress the expected hydration diff. */}
                <span className="ml-auto text-xs text-[var(--muted)]" suppressHydrationWarning>
                  {new Date(activity.created_at).toLocaleTimeString()}
                </span>
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${activity.status === "success" ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"}`}>
                  {activity.status === "success" ? "COMPLETE" : "FAILED"}
                </span>
              </div>
              <div className="flex gap-1 flex-wrap items-center">
                {activity.tool_calls.map((tool, ti) => (
                  <code key={`${tool}-${ti}`} className="rounded-md border border-white/5 bg-white/[0.035] px-1.5 py-1 text-[10px] text-[var(--muted)]">
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
  );
}
