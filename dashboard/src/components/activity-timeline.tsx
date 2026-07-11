"use client";

import { useState } from "react";
import Link from "next/link";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import type { AgentActivity } from "@/lib/mock-data";

const PAGE_SIZE = 10;

export function ActivityTimeline({ activities }: { activities: AgentActivity[] }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(activities.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const slice = activities.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="eyebrow">Live activity timeline</h3>
        <span className="text-xs text-[var(--muted)]">{activities.length} verified actions</span>
      </div>

      <div className="space-y-3">
        {slice.length === 0 && (
          <p className="text-xs text-[var(--muted)] py-6 text-center">No activity yet.</p>
        )}
        {slice.map((activity) => {
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

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-xs">
          <button
            onClick={() => setPage(current - 1)}
            disabled={current === 0}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[var(--muted)] transition-colors hover:text-white disabled:opacity-40 disabled:hover:text-[var(--muted)]"
          >
            ← Prev
          </button>
          <span className="text-[var(--muted)]">
            {current + 1} <span className="opacity-50">/ {pages}</span>
          </span>
          <button
            onClick={() => setPage(current + 1)}
            disabled={current >= pages - 1}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[var(--muted)] transition-colors hover:text-white disabled:opacity-40 disabled:hover:text-[var(--muted)]"
          >
            Next →
          </button>
        </div>
      )}
    </section>
  );
}
