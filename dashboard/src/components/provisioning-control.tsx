"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import type { Deployment } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";

const statusStyle: Record<string, string> = {
  success: "text-[var(--success)]",
  failed: "text-[var(--danger)]",
  "rolling-back": "text-[var(--warning)]",
  "rolled-back": "text-[var(--warning)]",
};

const providerLabel: Record<string, string> = { gcp: "GCP", azure: "Azure", onprem: "On-Premise", aws: "AWS" };

export function ProvisioningControl({ initialDeployments }: { initialDeployments: Deployment[] }) {
  const router = useRouter();
  const { data: session } = useSession();
  const [rows, setRows] = useState<Deployment[]>(initialDeployments);
  const [teardownTarget, setTeardownTarget] = useState<Deployment | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const role = (session?.user as any)?.role || "viewer";
  const isAllowed = role === "admin" || role === "operator";

  const confirmTeardown = async () => {
    const dep = teardownTarget;
    if (!dep || !isAllowed) return;
    setActionLoadingId(dep.id);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`/api/dashboard/deployments/${dep.id}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "onprem",
          scope: "cluster",
          service_name: dep.service,
          cluster_name: dep.service,
          version: dep.version,
          environment: dep.environment,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to tear down cluster");
      setSuccessMsg(data.summary || `Cluster ${dep.service} torn down`);
      // Single-row lifecycle: flip the provision row in place; its button disappears.
      setRows((current) => current.map((d) => (d.id === dep.id ? { ...d, status: "rolled-back" } : d)));
      setTeardownTarget(null);
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred");
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {(errorMsg || successMsg) && (
        <div className="flex items-center gap-3 rounded-lg border border-white/8 px-4 py-3 text-sm">
          {errorMsg && <div className="flex-1 text-[var(--danger)]">⚠️ <strong>Error:</strong> {errorMsg}</div>}
          {successMsg && <div className="flex-1 text-[var(--success)]">✓ <strong>Success:</strong> {successMsg}</div>}
          <button onClick={() => { setErrorMsg(null); setSuccessMsg(null); }} className="text-xs text-[var(--muted)] hover:text-white">
            Dismiss
          </button>
        </div>
      )}

      {teardownTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="surface w-full max-w-md border border-white/10 p-6 space-y-4 shadow-[0_25px_60px_rgba(0,0,0,0.5)]">
            <div className="flex justify-between items-center border-b border-white/6 pb-3">
              <h3 className="text-base font-semibold text-[#cbd6e9]">Tear Down Cluster</h3>
              <button type="button" onClick={() => setTeardownTarget(null)} className="text-xs text-[var(--muted)] hover:text-white">✕</button>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2 text-xs text-[var(--muted)]">
              <span className="font-medium text-[#cbd6e9]">{teardownTarget.service}</span>
              <span className="opacity-60"> · </span>
              <code className="text-[11px]">{teardownTarget.version}</code>
              <span className="opacity-60"> · </span>
              {teardownTarget.environment}
            </div>
            <p className="rounded-lg border border-red-500/35 bg-red-950/20 px-3 py-2.5 text-[11px] text-[var(--muted)]">
              Tears down the entire <span className="font-semibold text-red-200">{teardownTarget.service}</span> cluster
              (all workloads on it go with it). Destructive &amp; not reversible.
            </p>
            <div className="flex justify-end gap-3 pt-3 border-t border-white/6">
              <button type="button" onClick={() => setTeardownTarget(null)} className="rounded-lg border border-white/10 bg-white/[0.025] px-4 py-2 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 hover:text-white">
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmTeardown}
                disabled={actionLoadingId === teardownTarget.id}
                className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-red-500 disabled:opacity-50"
              >
                {actionLoadingId === teardownTarget.id ? "Tearing down..." : "Tear Down Cluster"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              <th className="p-3 text-left">ID</th>
              <th className="p-3 text-left">Cluster</th>
              <th className="p-3 text-left">Mode</th>
              <th className="p-3 text-left">Provider</th>
              <th className="p-3 text-left">Environment</th>
              <th className="p-3 text-left">Agent</th>
              <th className="p-3 text-left">Status</th>
              {isAllowed && <th className="p-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={isAllowed ? 8 : 7} className="p-8 text-center text-xs text-[var(--muted)]">
                  No provisioning activity recorded yet.
                </td>
              </tr>
            ) : (
              rows.map((dep) => {
                const canTeardown = dep.provider === "onprem" && dep.status === "success";
                return (
                  <tr
                    key={dep.id}
                    onClick={() => router.push(`/deployments/${dep.id}`)}
                    className="cursor-pointer border-t border-white/6 transition-colors hover:bg-white/[0.025]"
                  >
                    <td className="p-3">
                      <span className="font-mono text-xs text-[#8ab4f8]">{dep.id}</span>
                    </td>
                    <td className="p-3 font-medium">{dep.service}</td>
                    <td className="p-3"><code className="text-xs">{dep.version}</code></td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px] font-semibold ${providerBadgeStyles[dep.provider]}`}>
                        <ProviderLogo provider={dep.provider} size="sm" />
                        {providerLabel[dep.provider] ?? dep.provider}
                      </span>
                    </td>
                    <td className="p-3 text-[var(--muted)]">{dep.environment}</td>
                    <td className="p-3 text-xs text-[var(--muted)]">{dep.agent}</td>
                    <td className="p-3">
                      <span className={statusStyle[dep.status] ?? "text-[var(--muted)]"}>{dep.status}</span>
                    </td>
                    {isAllowed && (
                      <td className="p-3 text-right">
                        {canTeardown ? (
                          <button
                            disabled={actionLoadingId === dep.id}
                            onClick={(e) => { e.stopPropagation(); setErrorMsg(null); setSuccessMsg(null); setTeardownTarget(dep); }}
                            className="rounded border border-red-500/35 bg-red-950/20 px-2.5 py-1 text-[10px] font-bold text-red-200 hover:bg-red-900/40 transition-colors disabled:opacity-50"
                          >
                            {actionLoadingId === dep.id ? "Running..." : "Rollback"}
                          </button>
                        ) : (
                          <span className="text-[10px] text-[var(--muted)]">-</span>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
