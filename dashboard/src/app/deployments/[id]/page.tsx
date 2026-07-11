import Link from "next/link";
import { getDeploymentDetail } from "@/lib/activity-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";
import { DataSourceBadge } from "@/components/data-source-badge";

export const dynamic = "force-dynamic";

const statusBadge: Record<string, string> = {
  success: "bg-emerald-400/10 text-[var(--success)] border-emerald-500/30",
  failed: "bg-red-400/10 text-[var(--danger)] border-red-500/30",
  "rolling-back": "bg-amber-400/10 text-[var(--warning)] border-amber-500/30",
};

function stepOk(result: unknown): boolean {
  return !(result && typeof result === "object" && "error" in result && (result as { error: unknown }).error);
}

function fmt(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export default async function DeploymentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { deployment, activity, source } = await getDeploymentDetail(id);

  if (!deployment && !activity) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Link href="/deployments" className="text-xs text-[var(--muted)] hover:text-white">← Deployments</Link>
        <div className="surface p-8 text-center text-sm text-[var(--muted)]">
          No deployment found for <code className="text-[#cbd6e9]">{id}</code>.
        </div>
      </div>
    );
  }

  const provider = deployment?.provider ?? activity?.provider ?? "onprem";
  const status = deployment?.status ?? activity?.status ?? "success";
  const agent = deployment?.agent ?? activity?.agent ?? "Unknown agent";
  const model = activity?.model ?? modelIdFromAgent(agent);
  const service = deployment?.service ?? "service";
  const version = deployment?.version ?? "";
  const createdAt = deployment?.created_at ?? activity?.created_at ?? "";
  const trace = activity?.trace ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <div className="flex items-center justify-between gap-4">
        <Link href="/deployments" className="text-xs text-[var(--muted)] hover:text-white">← Deployments</Link>
        <DataSourceBadge source={source} />
      </div>

      {/* Header */}
      <div className="space-y-3">
        <p className="eyebrow">Reasoning and execution trace</p>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-semibold tracking-tight">
            {service} <span className="text-[var(--muted)] font-mono text-lg">{version}</span>
          </h2>
          <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-bold ${statusBadge[status] ?? statusBadge.success}`}>
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
        </div>
      </div>

      {/* Meta */}
      <div className="surface grid grid-cols-2 gap-x-6 gap-y-3 p-5 sm:grid-cols-4">
        <Meta label="Deployment ID" value={deployment?.id ?? id} mono />
        <Meta label="Environment" value={deployment?.environment ?? provider} />
        <Meta label="Started" value={createdAt ? new Date(createdAt).toLocaleString() : "—"} />
        <Meta label="Activity ID" value={activity?.id ?? "—"} mono />
      </div>

      {/* Instruction */}
      {(activity?.instruction || activity?.action) && (
        <section className="space-y-2">
          <h3 className="eyebrow">Instruction (natural language)</h3>
          <div className="surface p-4 text-sm text-[#cbd6e9]">{activity?.instruction || activity?.action}</div>
        </section>
      )}

      {/* Execution trace */}
      <section className="space-y-2">
        <h3 className="eyebrow">Execution trace <span className="text-[var(--muted)]">— what the model actually did</span></h3>
        {trace.length === 0 ? (
          <div className="surface p-4 text-xs text-[var(--muted)]">
            {activity?.tool_calls?.length
              ? `Tools: ${activity.tool_calls.join(" → ")} (detailed args/results not recorded for this run)`
              : "No execution trace recorded."}
          </div>
        ) : (
          <ol className="space-y-3">
            {trace.map((step, i) => {
              const ok = stepOk(step.result);
              return (
                <li key={i} className="surface p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/8 text-[10px] font-bold text-[var(--muted)]">{i + 1}</span>
                    <code className="rounded border border-white/8 bg-white/[0.04] px-2 py-0.5 text-xs font-semibold text-[#cbd6e9]">{step.tool}</code>
                    <span className={`ml-auto rounded px-1.5 py-0.5 text-[9px] font-bold ${ok ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"}`}>
                      {ok ? "OK" : "ERROR"}
                    </span>
                  </div>
                  {step.args && Object.keys(step.args).length > 0 && (
                    <TracePane label="args (in)" body={fmt(step.args)} />
                  )}
                  <TracePane label="result (out)" body={fmt(step.result)} />
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* Summary */}
      {activity?.summary && (
        <section className="space-y-2">
          <h3 className="eyebrow">Agent summary</h3>
          <div className="surface p-4 text-sm leading-relaxed text-[#cbd6e9] whitespace-pre-wrap">{activity.summary}</div>
        </section>
      )}
    </div>
  );
}

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <div className={`text-xs text-[#cbd6e9] ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function TracePane({ label, body }: { label: string; body: string }) {
  return (
    <div className="space-y-1">
      <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <pre className="overflow-x-auto rounded-lg border border-white/6 bg-black/25 p-2.5 text-[11px] leading-relaxed text-[#a9c7ff]">{body}</pre>
    </div>
  );
}
