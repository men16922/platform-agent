"use client";

import { useEffect, useState } from "react";

type RuntimeStatus = { router: "connected" | "offline"; runtime: string; path: string };

export function OnPremRuntimePanel() {
  const [status, setStatus] = useState<RuntimeStatus>({ router: "offline", runtime: "Local Qwen", path: "Qwen → supervisor → kagent" });

  useEffect(() => {
    fetch("/api/dashboard/agents/onprem-status", { cache: "no-store" })
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => undefined);
  }, []);

  const online = status.router === "connected";
  return (
    <section className="surface relative overflow-hidden border-emerald-400/20 bg-[radial-gradient(circle_at_84%_0%,rgba(105,211,167,0.17),transparent_30rem),linear-gradient(145deg,rgba(42,65,57,0.98),rgba(48,49,52,0.96))] p-5 sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="eyebrow text-emerald-200/70">On-prem control plane</p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight">A local runtime you can inspect before it acts.</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Local Qwen handles the request, the supervisor selects the specialist, and kagent owns Kubernetes diagnostics.
          </p>
        </div>
        <div className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${online ? "border-emerald-300/30 bg-emerald-400/10 text-[var(--success)]" : "border-white/10 bg-black/15 text-[var(--muted)]"}`}>
          <span className={online ? "pulse-dot" : "h-2 w-2 rounded-full bg-[var(--muted)]"} />
          Router {online ? "connected" : "offline"}
        </div>
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {["Local Qwen", "Supervisor", "kagent A2A"].map((step, index) => (
          <div key={step} className="rounded-xl border border-white/8 bg-black/15 p-3">
            <div className="flex items-center justify-between text-[10px] font-bold tracking-[0.12em] text-emerald-100/60"><span>0{index + 1}</span><span>READY PATH</span></div>
            <div className="mt-2 text-sm font-semibold">{step}</div>
            <div className="mt-1 text-[11px] text-[var(--muted)]">{index === 0 ? status.runtime : index === 1 ? "Route + policy boundary" : "Kubernetes tools + trace"}</div>
          </div>
        ))}
      </div>
      <p className="mt-4 font-mono text-[10px] text-emerald-100/55">{status.path}</p>
    </section>
  );
}
