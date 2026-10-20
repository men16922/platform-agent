"use client";

import { useEffect, useState } from "react";
import { ModelLogo } from "@/components/model-logo";

type RuntimeStatus = { router: "checking" | "connected" | "unavailable"; checked_at?: string };
type Agent = { cloud: string; name: string; provider: string; llm: string; runtime: string; path: string };
type ModelOption = { id: string; label: string; llm: string; framework: string; verdict: "recommended" | "allowed" | "discouraged"; reason: string };
type Model = ModelOption | null;

export function OnPremRuntimePanel({ agent, model, models, modelId, onModelChange }: { agent: Agent; model: Model; models: ModelOption[]; modelId: string; onModelChange: (id: string) => void }) {
  const [status, setStatus] = useState<RuntimeStatus>({ router: "checking" });

  useEffect(() => {
    if (agent.cloud !== "onprem") return;
    const controller = new AbortController();
    setStatus({ router: "checking" });
    fetch("/api/dashboard/agents/onprem-status", { cache: "no-store", signal: controller.signal })
      .then(async (res) => res.ok ? res.json() : null)
      .then((data) => { if (!controller.signal.aborted) setStatus({
        router: data?.router === "connected" ? "connected" : "unavailable",
        checked_at: typeof data?.checked_at === "string" ? data.checked_at : undefined,
      }); })
      .catch(() => { if (!controller.signal.aborted) setStatus({ router: "unavailable" }); });
    return () => controller.abort();
  }, [agent.cloud]);

  const online = agent.cloud === "onprem" && status.router === "connected";
  return (
    <section className="surface relative overflow-hidden border-emerald-400/20 bg-[radial-gradient(circle_at_84%_0%,rgba(105,211,167,0.17),transparent_30rem),linear-gradient(145deg,rgba(42,65,57,0.98),rgba(48,49,52,0.96))] p-5 sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="eyebrow text-emerald-200/70">2. Model and connection</p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight">{agent.name} · {model?.label ?? agent.runtime}</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            {agent.cloud === "onprem" ? "The connection check reaches the local router. Model responses and Kubernetes access are verified by individual runs." : `${agent.provider} is the selected target. Model credentials and infrastructure access have not been checked here.`}
          </p>
        </div>
        <div className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${online ? "border-emerald-300/30 bg-emerald-400/10 text-[var(--success)]" : "border-white/10 bg-black/15 text-[var(--muted)]"}`}>
          <span className={online ? "pulse-dot" : "h-2 w-2 rounded-full bg-[var(--muted)]"} />
          {agent.cloud === "onprem" ? `Router ${status.router === "checking" ? "checking…" : online ? "connected" : "unavailable"}` : "Execution not checked"}
        </div>
      </div>
      <div className="mt-5 rounded-xl border border-white/8 bg-black/15 p-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
        <div className="flex items-center gap-2">
          <ModelLogo model={model?.id} size="md" />
          <div><div className="text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-100/60">Selected AI model</div><div className="mt-0.5 text-xs text-[var(--muted)]">Applies to new chat requests. Availability is established by the result of each run.</div></div>
        </div>
        <select value={modelId} onChange={(event) => onModelChange(event.target.value)} className="mt-3 w-full rounded-lg border border-emerald-300/20 bg-black/25 px-3 py-2 text-xs text-[#dceaff] focus:outline-none focus:border-emerald-300/50 sm:mt-0 sm:w-80">
          {models.map((option) => <option key={option.id} value={option.id}>{option.label} — {option.verdict}</option>)}
        </select>
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {[
          { title: model?.llm ?? agent.runtime, label: "SELECTED", detail: "Model selection is not a readiness check." },
          { title: agent.cloud === "onprem" ? "Local router" : `${agent.provider} access`, label: agent.cloud === "onprem" ? status.router.toUpperCase() : "NOT CHECKED", detail: agent.cloud === "onprem" && status.checked_at ? `Connection checked at ${status.checked_at}` : "No completed connection check is recorded here." },
          { title: "Request tools", label: "PER REQUEST", detail: "Select read-only inspection below to exclude operational actions. Completed calls appear in the run trace." },
        ].map((step, index) => (
          <div key={step.title} className="rounded-xl border border-white/8 bg-black/15 p-3">
            <div className="flex items-center justify-between text-[10px] font-bold tracking-[0.12em] text-emerald-100/60"><span>0{index + 1}</span><span>{step.label}</span></div>
            <div className="mt-2 flex items-center gap-2 text-sm font-semibold">{index === 0 && <ModelLogo model={model?.id} />}{step.title}</div>
            <div className="mt-1 text-[11px] text-[var(--muted)]">{step.detail}</div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-[11px] text-[var(--muted)]">Use the recorded request and tool trace to confirm what ran. This panel does not verify supervisor or specialist delegation.</p>
    </section>
  );
}
