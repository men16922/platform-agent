import Link from "next/link";
import { getDeploymentDetail } from "@/lib/activity-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import { DataSourceBadge } from "@/components/data-source-badge";
import { Markdown } from "@/components/markdown";

export const dynamic = "force-dynamic";

const statusBadge: Record<string, string> = {
  success: "bg-emerald-400/12 text-[var(--success)] border-emerald-500/40",
  failed: "bg-red-400/12 text-[var(--danger)] border-red-500/40",
  "rolling-back": "bg-amber-400/12 text-[var(--warning)] border-amber-500/40",
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
  const { deployment, activity, source } = await getDeploymentDetail(id);

  if (!deployment && !activity) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Link href="/deployments" className="text-xs text-[var(--muted)] hover:text-white">← Deployments</Link>
        <div className="surface p-8 text-center text-sm text-[var(--muted)]">
          No run found for <code className="text-[#cbd6e9]">{id}</code>.
        </div>
      </div>
    );
  }

  const provider = deployment?.provider ?? activity?.provider ?? "onprem";
  const status = deployment?.status ?? activity?.status ?? "success";
  const agent = deployment?.agent ?? activity?.agent ?? "Unknown agent";
  const model = activity?.model ?? modelIdFromAgent(agent);
  const service = deployment?.service ?? "";
  const version = deployment?.version ?? "";
  const createdAt = deployment?.created_at ?? activity?.created_at ?? "";
  const trace = activity?.trace ?? [];

  const isDeploy = !!service && !["unknown", "service", ""].includes(service);
  const toolNames = trace.filter((t) => t.kind === "tool").map((t) => t.tool!).filter(Boolean);
  const uniqueTools = [...new Set(toolNames.length ? toolNames : activity?.tool_calls ?? [])];

  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <div className="flex items-center justify-between gap-4">
        <Link href="/deployments" className="text-xs text-[#8ab4f8] hover:underline">← Deployments</Link>
        <DataSourceBadge source={source} />
      </div>

      {/* Header */}
      <div className="space-y-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#8ab4f8]">Reasoning &amp; execution trace</p>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-semibold tracking-tight text-[#e6edf7]">
            {isDeploy ? service : "Agent run"}
            {isDeploy && version && <span className="ml-2 font-mono text-lg text-[#8ab4f8]">{version}</span>}
          </h2>
          <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-bold ${statusBadge[status] ?? statusBadge.success}`}>
            {status.toUpperCase()}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
          <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${providerBadgeStyles[provider]}`}>
            <ProviderLogo provider={provider} size="sm" />
            {provider.toUpperCase()}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ModelLogo model={model} />
            {agent}
          </span>
          {uniqueTools.map((t) => (
            <code key={t} className="rounded border border-[#8ab4f8]/25 bg-[#8ab4f8]/10 px-1.5 py-0.5 text-[10px] text-[#a9c7ff]">{t}</code>
          ))}
        </div>
      </div>

      {/* Meta */}
      <div className="surface grid grid-cols-2 gap-x-6 gap-y-3 p-5 sm:grid-cols-4">
        <Meta label="Run ID" value={deployment?.id ?? id} mono />
        <Meta label="Environment" value={deployment?.environment ?? provider} />
        <Meta label="Started" value={createdAt ? new Date(createdAt).toLocaleString() : "—"} />
        <Meta label="Activity ID" value={activity?.id ?? "—"} mono />
      </div>

      {/* Instruction */}
      {(activity?.instruction || activity?.action) && (
        <section className="space-y-2">
          <SectionTitle accent="#8ab4f8">Instruction (natural language)</SectionTitle>
          <div className="rounded-xl border-l-2 border-[#8ab4f8]/50 bg-[#8ab4f8]/[0.06] p-4 text-sm text-[#e6edf7]">
            {activity?.instruction || activity?.action}
          </div>
        </section>
      )}

      {/* Execution trace */}
      <section className="space-y-2">
        <SectionTitle accent="#c4b5fd">
          Execution trace <span className="font-normal text-[var(--muted)]">— what the model actually did</span>
        </SectionTitle>
        {trace.length === 0 ? (
          <div className="surface p-4 text-xs text-[var(--muted)]">
            {activity?.tool_calls?.length
              ? `Tools: ${activity.tool_calls.join(" → ")} (detailed args/results not recorded for this run)`
              : "No execution trace recorded."}
          </div>
        ) : (
          <ol className="space-y-2.5">
            {trace.map((item, i) => {
              if (item.kind === "reasoning") {
                return (
                  <li key={i} className="rounded-xl border-l-2 border-[#8ab4f8]/50 bg-[#8ab4f8]/[0.05] p-3.5">
                    <div className="mb-1 text-[9px] font-bold uppercase tracking-wider text-[#8ab4f8]">🧠 reasoning</div>
                    <p className="text-xs leading-relaxed text-[#cbd6e9] whitespace-pre-wrap">{item.text}</p>
                  </li>
                );
              }
              const ok = stepOk(item.result);
              const cmd = asCommandResult(item.result);
              return (
                <li className={`rounded-xl border border-white/6 border-l-2 p-4 space-y-2.5 ${ok ? "border-l-emerald-500/50" : "border-l-red-500/60"}`} key={i}>
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
      </section>

      {/* Summary */}
      {activity?.summary && (
        <section className="space-y-2">
          <SectionTitle accent="#69d3a7">Agent summary</SectionTitle>
          <div className="rounded-xl border-l-2 border-emerald-500/40 bg-emerald-500/[0.05] p-4 text-sm leading-relaxed text-[#e6edf7]">
            <Markdown text={activity.summary} />
          </div>
        </section>
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

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <div className={`text-xs text-[#cbd6e9] ${mono ? "font-mono text-[#a9c7ff]" : ""}`}>{value}</div>
    </div>
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
