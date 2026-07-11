"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import type { Deployment } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";
import { ModelLogo, modelIdFromAgent } from "@/components/model-logo";

const statusIcon = {
  success: { icon: "✓", color: "text-[var(--success)]" },
  failed: { icon: "✗", color: "text-[var(--danger)]" },
  "rolling-back": { icon: "↺", color: "text-[var(--warning)]" },
  "rolled-back": { icon: "↺", color: "text-[var(--warning)]" },
};

const PAGE_SIZE = 10;

interface DeploymentsControlProps {
  initialDeployments: Deployment[];
  // Clusters whose provisioning was torn down — their apps can't be rolled back.
  tornDownClusters?: string[];
}

export function DeploymentsControl({ initialDeployments, tornDownClusters = [] }: DeploymentsControlProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const [deployments, setDeployments] = useState<Deployment[]>(initialDeployments);
  const [page, setPage] = useState(0);
  
  // Modal states
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [serviceName, setServiceName] = useState("orders-api");
  const [version, setVersion] = useState("v1.5.0");
  const [provider, setProvider] = useState("aws");
  const [environment, setEnvironment] = useState("production");

  // Rollback modal state (Deployments = app rollback only)
  const [rollbackTarget, setRollbackTarget] = useState<Deployment | null>(null);
  const [rollbackVersion, setRollbackVersion] = useState("v1.4.9");
  
  // Loading & error states
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const userRole = (session?.user as any)?.role || "viewer";
  const isAllowed = userRole === "admin" || userRole === "operator";
  const pages = Math.max(1, Math.ceil(deployments.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const currentDeployments = deployments.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  const triggerDeployment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAllowed) return;

    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetch("/api/dashboard/deployments/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName, version, provider, environment }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to trigger deployment");

      setSuccessMsg(`Successfully triggered deployment ${data.deployment_id}`);
      setShowTriggerModal(false);
      
      // Add simulated temporary deployment to list (or reload)
      const newDep: Deployment = {
        id: data.deployment_id,
        type: "deploy",
        cluster: provider === "onprem" ? "platform-agent" : "",
        service: serviceName,
        version,
        provider: provider as any,
        environment,
        status: "rolling-back", // show as processing status
        duration_sec: 0,
        agent: "Strands Agent (Bedrock)",
        created_at: new Date().toISOString(),
      };
      setDeployments((current) => [newDep, ...current]);
      setPage(0);
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const openRollback = (dep: Deployment) => {
    if (!isAllowed) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    setRollbackVersion("v1.4.9");
    setRollbackTarget(dep);
  };

  const confirmRollback = async () => {
    const dep = rollbackTarget;
    if (!dep || !isAllowed) return;

    // On-prem rolls back the real kind/k3s cluster via the local router; the
    // cloud path takes a target version for the AWS Step Functions pipeline.
    let payload: Record<string, unknown>;
    if (dep.provider === "onprem") {
      // Deployments rolls back the app only (previous revision); cluster teardown
      // lives on the Provisioning page.
      payload = { service_name: dep.service, version: dep.version, provider: "onprem", environment: dep.environment, scope: "app", namespace: "default", cluster_name: "platform-agent" };
    } else {
      const target = rollbackVersion.trim();
      if (!target) return;
      payload = { service_name: dep.service, rollback_version: target, provider: dep.provider, environment: dep.environment };
    }

    setActionLoadingId(dep.id);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetch(`/api/dashboard/deployments/${dep.id}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to execute rollback");

      setSuccessMsg(data.summary || `Successfully executed rollback request ${data.rollback_id}`);

      // Single-row lifecycle: flip the original deployment in place (the recorder
      // superseded its row server-side) — no duplicate row, and its Rollback button
      // disappears since it only shows for status "success".
      setDeployments((current) =>
        current.map((d) => (d.id === dep.id ? { ...d, status: "rolled-back" } : d)),
      );
      setRollbackTarget(null);
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred");
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {(errorMsg || successMsg) && (
        <div className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm">
          {errorMsg && (
            <div className="flex-1 text-[var(--danger)] border-red-500/25">
              ⚠️ <strong>Error:</strong> {errorMsg}
            </div>
          )}
          {successMsg && (
            <div className="flex-1 text-[var(--success)] border-emerald-500/25">
              ✓ <strong>Success:</strong> {successMsg}
            </div>
          )}
          <button
            onClick={() => {
              setErrorMsg(null);
              setSuccessMsg(null);
            }}
            className="text-xs text-[var(--muted)] hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="eyebrow text-xs uppercase tracking-wider text-[var(--muted)]">
          Deployment logs ({deployments.length} runs)
        </p>
        {isAllowed ? (
          <button
            onClick={() => setShowTriggerModal(true)}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 transition-all"
          >
            ✦ Trigger Deployment
          </button>
        ) : (
          <span className="text-[10px] text-[var(--muted)] italic bg-white/[0.02] border border-white/5 px-2.5 py-1 rounded-md">
            Sign in as Operator/Admin to trigger deployments or rollbacks.
          </span>
        )}
      </div>

      {/* Trigger Modal */}
      {showTriggerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <form
            onSubmit={triggerDeployment}
            className="surface w-full max-w-md border border-white/10 p-6 space-y-4 shadow-[0_25px_60px_rgba(0,0,0,0.5)]"
          >
            <div className="flex justify-between items-center border-b border-white/6 pb-3">
              <h3 className="text-base font-semibold text-[#cbd6e9]">Trigger Guarded Delivery</h3>
              <button
                type="button"
                onClick={() => setShowTriggerModal(false)}
                className="text-xs text-[var(--muted)] hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                Service Name
              </label>
              <select
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
              >
                <option value="orders-api">orders-api (EKS/GKE)</option>
                <option value="payment-service">payment-service (Lambda)</option>
                <option value="auth-service">auth-service (Cloud Run)</option>
                <option value="catalog-db">catalog-db (On-Premise)</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                  Target Provider
                </label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
                >
                  <option value="aws">AWS</option>
                  <option value="gcp">Google Cloud</option>
                  <option value="azure">Azure</option>
                  <option value="onprem">On-Premise</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                  Target Environment
                </label>
                <select
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
                >
                  <option value="production">Production</option>
                  <option value="staging">Staging</option>
                  <option value="dev">Dev</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                Release Version
              </label>
              <input
                type="text"
                required
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="e.g. v1.5.0"
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
              />
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-white/6">
              <button
                type="button"
                onClick={() => setShowTriggerModal(false)}
                className="rounded-lg border border-white/10 bg-white/[0.025] px-4 py-2 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50"
              >
                {loading ? "Triggering..." : "Start Release"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Rollback Modal */}
      {rollbackTarget && (() => {
        const dep = rollbackTarget;
        const isOnprem = dep.provider === "onprem";
        const busy = actionLoadingId === dep.id;
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
            <div className="surface w-full max-w-md border border-white/10 p-6 space-y-4 shadow-[0_25px_60px_rgba(0,0,0,0.5)]">
              <div className="flex justify-between items-center border-b border-white/6 pb-3">
                <h3 className="text-base font-semibold text-[#cbd6e9]">Roll Back Deployment</h3>
                <button
                  type="button"
                  onClick={() => setRollbackTarget(null)}
                  className="text-xs text-[var(--muted)] hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2 text-xs text-[var(--muted)]">
                <span className="font-medium text-[#cbd6e9]">{dep.service}</span>
                <span className="opacity-60"> · </span>
                <code className="text-[11px]">{dep.version}</code>
                <span className="opacity-60"> · </span>
                {dep.environment}
                <span className="opacity-60"> · </span>
                {dep.provider === "onprem" ? "On-Premise" : dep.provider.toUpperCase()}
              </div>

              {isOnprem ? (
                <p className="rounded-lg border border-[#8ab4f8]/25 bg-[#8ab4f8]/[0.06] px-3 py-2.5 text-[11px] text-[var(--muted)]">
                  Rolls <span className="font-semibold text-[#cbd6e9]">{dep.service}</span> back to its previous
                  revision (<code>kubectl rollout undo</code>). Safe &amp; reversible. To tear down the whole
                  cluster, use the <span className="text-[#cbd6e9]">Provisioning</span> page instead.
                </p>
              ) : (
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                    Target Rollback Version
                  </label>
                  <input
                    type="text"
                    value={rollbackVersion}
                    onChange={(e) => setRollbackVersion(e.target.value)}
                    placeholder="e.g. v1.4.9"
                    className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
                  />
                  <p className="text-[11px] text-[var(--muted)]">Current version: <code>{dep.version}</code></p>
                </div>
              )}

              {errorMsg && (
                <p className="text-[11px] text-[var(--danger)]">⚠️ {errorMsg}</p>
              )}

              <div className="flex justify-end gap-3 pt-3 border-t border-white/6">
                <button
                  type="button"
                  onClick={() => setRollbackTarget(null)}
                  className="rounded-lg border border-white/10 bg-white/[0.025] px-4 py-2 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={confirmRollback}
                  disabled={busy || (!isOnprem && !rollbackVersion.trim())}
                  className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-500 disabled:opacity-50"
                >
                  {busy ? "Rolling back..." : "Confirm Rollback"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Deployments Table */}
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              <th className="text-left p-3">ID</th>
              <th className="text-left p-3">Service</th>
              <th className="text-left p-3">Version</th>
              <th className="text-left p-3">Provider</th>
              <th className="text-left p-3">Environment</th>
              <th className="text-left p-3">Agent</th>
              <th className="text-left p-3">Status</th>
              <th className="text-right p-3">Duration</th>
              <th className="text-right p-3">Time</th>
              {isAllowed && <th className="text-right p-3">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {currentDeployments.map((dep) => {
              const status = statusIcon[dep.status as keyof typeof statusIcon] || { icon: "●", color: "text-[var(--warning)]" };
              const isActionLoading = actionLoadingId === dep.id;
              // No cluster (can't correlate) or a torn-down cluster → rollback unavailable.
              const clusterDown = !dep.cluster || tornDownClusters.includes(dep.cluster);

              return (
                <tr
                  key={dep.id}
                  onClick={() => router.push(`/deployments/${dep.id}`)}
                  className="cursor-pointer border-t border-white/6 transition-colors hover:bg-white/[0.025]"
                >
                  <td className="p-3">
                    <span className="text-xs font-mono text-[#8ab4f8]">{dep.id}</span>
                  </td>
                  <td className="p-3 font-medium">{dep.service}</td>
                  <td className="p-3">
                    <code className="text-xs">{dep.version}</code>
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px] font-semibold ${providerBadgeStyles[dep.provider]}`}>
                      <ProviderLogo provider={dep.provider} size="sm" />
                      {dep.provider === "gcp" ? "GCP" : dep.provider === "azure" ? "Azure" : dep.provider === "onprem" ? "On-Premise" : "AWS"}
                    </span>
                  </td>
                  <td className="p-3 text-[var(--muted)]">{dep.environment}</td>
                  <td className="p-3 text-xs text-[var(--muted)]">
                    <span className="inline-flex items-center gap-1.5">
                      <ModelLogo model={modelIdFromAgent(dep.agent)} />
                      {dep.agent}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={status.color}>
                      {status.icon} {dep.status}
                    </span>
                  </td>
                  <td className="p-3 text-right text-[var(--muted)]">{dep.duration_sec}s</td>
                  <td className="p-3 text-right text-[var(--muted)] text-xs" suppressHydrationWarning>
                    {new Date(dep.created_at).toLocaleTimeString()}
                  </td>
                  {isAllowed && (
                    <td className="p-3 text-right">
                      {dep.status === "success" ? (
                        clusterDown ? (
                          <span
                            title={dep.cluster ? "Cluster torn down — re-provision first" : "No linked cluster — rollback unavailable"}
                            className="cursor-not-allowed rounded border border-white/10 bg-white/[0.02] px-2.5 py-1 text-[10px] font-bold text-[var(--muted)]"
                          >
                            Rollback
                          </span>
                        ) : (
                          <button
                            disabled={isActionLoading}
                            onClick={(e) => { e.stopPropagation(); openRollback(dep); }}
                            className="rounded border border-red-500/35 bg-red-950/20 px-2.5 py-1 text-[10px] font-bold text-red-200 hover:bg-red-900/40 transition-colors disabled:opacity-50"
                          >
                            {isActionLoading ? "Running..." : "Rollback"}
                          </button>
                        )
                      ) : (
                        <span className="text-[10px] text-[var(--muted)]">-</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-xs">
          <button
            onClick={() => setPage(currentPage - 1)}
            disabled={currentPage === 0}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[var(--muted)] transition-colors hover:text-white disabled:opacity-40 disabled:hover:text-[var(--muted)]"
          >
            ← Prev
          </button>
          <span className="text-[var(--muted)]">
            {currentPage + 1} <span className="opacity-50">/ {pages}</span>
          </span>
          <button
            onClick={() => setPage(currentPage + 1)}
            disabled={currentPage >= pages - 1}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[var(--muted)] transition-colors hover:text-white disabled:opacity-40 disabled:hover:text-[var(--muted)]"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
