import Link from "next/link";
import { getLifecycleDetail, type LifecyclePhase } from "@/lib/activity-data";
import type { AgentActivity } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import { DataSourceBadge } from "@/components/data-source-badge";
import { Markdown } from "@/components/markdown";

export const dynamic = "force-dynamic";

const statusBadge: Record<string, string> = {
  success: "bg-emerald-400/12 text-[var(--success)] border-emerald-500/40",
  failed: "bg-red-400/12 text-[var(--danger)] border-red-500/40",
  "rolling-back": "bg-amber-400/12 text-[var(--warning)] border-amber-500/40",
  "rolled-back": "bg-amber-400/12 text-[var(--warning)] border-amber-500/40",
};

function stepOk(result: unknown): boolean {
  return !(result && typeof result === "object" && "error" in result && (result as { error: unknown }).error);
}

function fmt(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

// kubectl-style tool result: { ok, output, error }
function asCommandResult(r: unknown): { output: string; error?: string | null } | null {
  if (r && typeof r === "object" && typeof (r as { output?: unknown }).output === "string") {
    return { output: (r as { output: string }).output, error: (r as { error?: string | null }).error ?? null };
  }
  return null;
}

export default async function DeploymentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { cluster, provisioning, deployments, focusId, found, source } = await getLifecycleDetail(id);

  if (!found) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Link href="/history" className="text-xs text-[var(--muted)] hover:text-white">← History</Link>
        <div className="surface p-8 text-center text-sm text-[var(--muted)]">
          No run found for <code className="text-[#cbd6e9]">{id}</code>.
        </div>
      </div>
    );
  }

  const head = provisioning?.deployment ?? deployments[0]?.deployment;
  const provider = head?.provider ?? "onprem";
  const environment = head?.environment ?? "dev";

  return (
    <div className="mx-auto max-w-5xl space-y-7">
      <div className="flex items-center justify-between gap-4">
        <Link href="/history" className="text-xs text-[#8ab4f8] hover:underline">← History</Link>
        <DataSourceBadge source={source} />
      </div>

      {/* Header — the cluster lifecycle */}
      <div className="space-y-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#8ab4f8]">Cluster lifecycle</p>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-semibold tracking-tight text-[#e6edf7]">{cluster || "Agent run"}</h2>
          <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${providerBadgeStyles[provider]}`}>
            <ProviderLogo provider={provider} size="sm" />
            {provider.toUpperCase()}
          </span>
          <span className="text-xs text-[var(--muted)]">{environment}</span>
        </div>
        <p className="text-xs text-[var(--muted)]">
          Provisioning and the deployments that landed on this cluster, in one place.
        </p>
      </div>

      {/* Provisioning (top level) */}
      <section className="space-y-2">
        <SectionTitle accent="#69d3a7">Provisioning</SectionTitle>
        {provisioning ? (
          <PhaseCard phase={provisioning} kind="provision" focusId={focusId} />
        ) : (
          <div className="surface p-4 text-xs text-[var(--muted)]">
            No provisioning run recorded for <code className="text-[#cbd6e9]">{cluster}</code> (the cluster may have
            pre-existed this activity log).
          </div>
        )}
      </section>

      {/* Deployments on this cluster (nested, collapsible) */}
      <section className="space-y-2">
        <SectionTitle accent="#8ab4f8">
          Deployments on this cluster <span className="font-normal text-[var(--muted)]">— {deployments.length}</span>
        </SectionTitle>
        {deployments.length === 0 ? (
          <div className="surface p-4 text-xs text-[var(--muted)]">No app deployments recorded on this cluster yet.</div>
        ) : (
          <div className="space-y-2">
            {deployments.map((phase) => (
              <PhaseCard key={phase.deployment.id} phase={phase} kind="deploy" focusId={focusId} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// A collapsible lifecycle phase (provisioning or one deployment). The focused row —
// or the provisioning at the top — opens by default; the rest stay folded.
function PhaseCard({
  phase,
  kind,
  focusId,
}: {
  phase: LifecyclePhase;
  kind: "provision" | "deploy";
  focusId: string;
}) {
  const { deployment: dep, activity } = phase;
  // Only the focused row opens: click a deploy → its trace expands, provisioning stays folded.
  const open = dep.id === focusId;
  const model = activity?.model ?? modelIdFromAgent(dep.agent);
  const primary = kind === "provision" ? dep.service : dep.service;
  const secondary = kind === "provision" ? `mode ${dep.version}` : dep.version;

  return (
    <details open={open} className="surface group overflow-hidden [&_summary]:list-none">
      <summary className="flex cursor-pointer flex-wrap items-center gap-3 p-4 hover:bg-white/[0.02]">
        <span className="text-[var(--muted)] transition-transform group-open:rotate-90">▸</span>
        <span className="font-medium text-[#e6edf7]">{primary}</span>
        <code className="text-xs text-[#8ab4f8]">{secondary}</code>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${statusBadge[dep.status] ?? statusBadge.success}`}>
          {dep.status.toUpperCase()}
        </span>
        <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
          <ModelLogo model={model} />
          <span className="font-mono text-[#a9c7ff]">{dep.id}</span>
          <span suppressHydrationWarning>{dep.created_at ? new Date(dep.created_at).toLocaleString() : ""}</span>
        </span>
      </summary>
      <div className="border-t border-white/6 p-4">
        <PhaseBody activity={activity} toolCalls={activity?.tool_calls} />
      </div>
    </details>
  );
}

function PhaseBody({ activity, toolCalls }: { activity: AgentActivity | null; toolCalls?: string[] }) {
  const trace = activity?.trace ?? [];
  return (
    <div className="space-y-4">
      {(activity?.instruction || activity?.action) && (
        <div className="rounded-lg border-l-2 border-[#8ab4f8]/50 bg-[#8ab4f8]/[0.06] p-3 text-xs text-[#e6edf7]">
          {activity?.instruction || activity?.action}
        </div>
      )}

      {trace.length === 0 ? (
        <div className="text-xs text-[var(--muted)]">
          {toolCalls?.length
            ? `Tools: ${toolCalls.join(" → ")} (detailed args/results not recorded for this run)`
            : "No execution trace recorded."}
        </div>
      ) : (
        <ol className="space-y-2.5">
          {trace.map((item, i) => {
            if (item.kind === "reasoning") {
              return (
                <li key={i} className="rounded-xl border-l-2 border-[#8ab4f8]/50 bg-[#8ab4f8]/[0.05] p-3.5">
                  <div className="mb-1 text-[9px] font-bold uppercase tracking-wider text-[#8ab4f8]">🧠 reasoning</div>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-[#cbd6e9]">{item.text}</p>
                </li>
              );
            }
            if (item.kind === "consensus") {
              return (
                <li key={i} className="rounded-xl border-l-2 border-[#c4b5fd]/50 bg-[#c4b5fd]/[0.06] p-3.5">
                  <div className="mb-1 flex items-center gap-2 text-[9px] font-bold uppercase tracking-wider text-[#c4b5fd]">
                    <span>🗳️ self-consistency route</span>
                    {typeof item.agreement === "number" && (
                      <span className="rounded bg-[#c4b5fd]/15 px-1.5 py-0.5 font-mono text-[9px] text-[#d9ccff]">
                        {item.role} · agreement {item.agreement.toFixed(2)}
                      </span>
                    )}
                    {item.fell_back && (
                      <span className="rounded bg-amber-400/20 px-1.5 py-0.5 font-mono text-[9px] text-amber-100">
                        fell back → deterministic
                      </span>
                    )}
                  </div>
                  {item.votes && (
                    <p className="font-mono text-[11px] text-[#cbd6e9]">votes: {JSON.stringify(item.votes)}</p>
                  )}
                </li>
              );
            }
            if (item.kind === "plan") {
              return (
                <li key={i} className="rounded-xl border-l-2 border-[#8ab4f8]/50 bg-[#8ab4f8]/[0.05] p-3.5">
                  <div className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-[#8ab4f8]">🧭 orchestration plan</div>
                  <ol className="flex flex-wrap items-center gap-1.5">
                    {(item.steps ?? []).map((step, j) => (
                      <li key={j} className="flex items-center gap-1.5">
                        {j > 0 && <span className="text-[#8ab4f8]">→</span>}
                        <span className={`rounded border px-2 py-0.5 font-mono text-[10px] ${step.delegated ? "border-emerald-400/40 bg-emerald-400/10 text-[var(--success)]" : "border-white/10 bg-white/5 text-[#cbd6e9]"}`}>
                          {step.role}
                        </span>
                      </li>
                    ))}
                  </ol>
                </li>
              );
            }
            const ok = stepOk(item.result);
            const cmd = asCommandResult(item.result);
            return (
              <li className={`space-y-2.5 rounded-xl border border-white/6 border-l-2 p-4 ${ok ? "border-l-emerald-500/50" : "border-l-red-500/60"}`} key={i}>
                <div className="flex items-center gap-2">
                  <span className="text-[#c4b5fd]">🔧</span>
                  <code className="rounded border border-[#c4b5fd]/25 bg-[#c4b5fd]/10 px-2 py-0.5 text-xs font-semibold text-[#d9ccff]">{item.tool}</code>
                  <span className={`ml-auto rounded px-1.5 py-0.5 text-[9px] font-bold ${ok ? "bg-emerald-400/12 text-[var(--success)]" : "bg-red-400/12 text-[var(--danger)]"}`}>
                    {ok ? "OK" : "ERROR"}
                  </span>
                </div>
                {item.args && Object.keys(item.args).length > 0 && (
                  <TracePane label="args (in)" body={fmt(item.args)} tone="args" />
                )}
                {cmd ? (
                  <>
                    {cmd.output && <TracePane label="output" body={cmd.output} tone="output" />}
                    {cmd.error && <TracePane label="error" body={cmd.error} tone="error" />}
                  </>
                ) : (
                  <TracePane label="result (out)" body={fmt(item.result)} tone="result" />
                )}
              </li>
            );
          })}
        </ol>
      )}

      {activity?.cost_metrics && (activity.cost_metrics.tool_calls_total > 0 || activity.cost_metrics.total_tokens > 0) && (
        <div className="rounded-lg border border-white/6 bg-white/[0.02] p-3">
          <div className="mb-2 text-[9px] font-bold uppercase tracking-wider text-[var(--muted)]">💰 cost / usage sub-metrics</div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="rounded bg-white/5 px-2 py-1 font-mono text-[#cbd6e9]">tool calls {activity.cost_metrics.tool_calls_total}</span>
            <span className="rounded bg-white/5 px-2 py-1 font-mono text-[#cbd6e9]">reasoning {activity.cost_metrics.reasoning_steps}</span>
            {activity.cost_metrics.total_tokens > 0 && (
              <span className="rounded bg-white/5 px-2 py-1 font-mono text-[#cbd6e9]">
                tokens {activity.cost_metrics.total_tokens} ({activity.cost_metrics.input_tokens} in / {activity.cost_metrics.output_tokens} out)
              </span>
            )}
          </div>
          {Object.keys(activity.cost_metrics.tool_calls_by_name).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(activity.cost_metrics.tool_calls_by_name).map(([name, count]) => (
                <span key={name} className="rounded border border-white/6 bg-white/[0.035] px-1.5 py-0.5 font-mono text-[10px] text-[#cbd6e9]">
                  {name} ×{count}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {activity?.summary && (
        <div className="rounded-lg border-l-2 border-emerald-500/40 bg-emerald-500/[0.05] p-3 text-xs leading-relaxed text-[#e6edf7]">
          <Markdown text={activity.summary} />
        </div>
      )}
    </div>
  );
}

function SectionTitle({ children, accent }: { children: React.ReactNode; accent: string }) {
  return (
    <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[#9fb0c9]">
      <span className="h-3 w-0.5 rounded" style={{ background: accent }} />
      {children}
    </h3>
  );
}

const paneTone: Record<string, string> = {
  args: "text-[#7fd1b9]",
  result: "text-[#a9c7ff]",
  output: "text-[#cbd6e9]",
  error: "text-[#ffb4ab]",
};

function TracePane({ label, body, tone = "result" }: { label: string; body: string; tone?: string }) {
  return (
    <div className="space-y-1">
      <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <pre className={`overflow-x-auto rounded-lg border border-white/6 bg-black/30 p-2.5 text-[11px] leading-relaxed ${paneTone[tone] ?? paneTone.result}`}>{body}</pre>
    </div>
  );
}
