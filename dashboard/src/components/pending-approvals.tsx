"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import type { ApprovalRequest } from "@/lib/approval-data";
import { canApprove } from "@/lib/auth";

interface PendingApprovalsProps {
  initialApprovals: ApprovalRequest[];
}

export function PendingApprovals({ initialApprovals }: PendingApprovalsProps) {
  const { data: session } = useSession();
  const router = useRouter();
  const [approvals, setApprovals] = useState<ApprovalRequest[]>(initialApprovals);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const userRole = (session?.user as any)?.role || "viewer";

  const handleDecision = async (approvalId: string, decision: "approve" | "reject", severity: "P1" | "P2" | "P3", reason = "") => {
    if (loadingId) return;
    if (!session?.user) {
      setErrorMsg("Please sign in to perform actions.");
      return;
    }

    if (!canApprove(userRole, severity)) {
      setErrorMsg(`Your role (${userRole}) is not authorized to approve ${severity} incidents.`);
      return;
    }

    setLoadingId(approvalId);
    setErrorMsg(null);

    try {
      const res = await fetch(`/api/dashboard/incidents/${approvalId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to process approval");
      }

      // Remove approved/rejected item from view
      setApprovals((current) => current.filter((a) => a.approval_id !== approvalId));
      setRejectingId(null);
      setRejectionReason("");
      router.refresh();
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred");
    } finally {
      setLoadingId(null);
    }
  };

  if (approvals.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#ffb4ae] flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
          Pending Remediation Approvals
        </h3>
        {errorMsg && (
          <span className="text-xs font-medium text-[var(--danger)] bg-red-950/40 border border-red-500/25 px-2.5 py-1 rounded-md">
            ⚠️ {errorMsg}
          </span>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {approvals.map((req) => {
          const isAllowed = canApprove(userRole, req.severity);
          const isPending = loadingId === req.approval_id;

          return (
            <div
              key={req.approval_id}
              className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-red-500/40 bg-[linear-gradient(115deg,rgba(127,29,29,0.30),rgba(32,33,36,0.95)_45%)] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_15px_40px_rgba(239,68,68,0.12)]"
            >
              <div className="absolute top-0 left-0 bottom-0 w-1 bg-red-500" />
              <div>
                <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-red-500/20 border border-red-500/45 px-2.5 py-0.5 text-xs font-bold text-red-200">
                      {req.severity}
                    </span>
                    <span className="rounded bg-white/5 border border-white/10 px-2 py-0.5 text-[10px] font-mono text-[var(--muted)]">
                      {req.approval_id}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold border ${
                        req.source === "onprem"
                          ? "bg-sky-500/15 border-sky-400/40 text-sky-200"
                          : "bg-amber-500/15 border-amber-400/40 text-amber-200"
                      }`}
                      title={req.source === "onprem" ? "On-Prem webhook (offline)" : "AWS Step Functions"}
                    >
                      {req.source === "onprem" ? "On-Prem" : "AWS"}
                    </span>
                  </div>
                  <div className="text-[10px] font-semibold text-red-300/80">
                    Confidence: {(req.confidence * 100).toFixed(0)}%
                  </div>
                </div>

                <h4 className="font-semibold text-sm text-[#cbd6e9] mb-1">{req.alarm_name}</h4>
                <p className="text-xs text-[var(--muted)] leading-relaxed mb-4">{req.root_cause}</p>

                <div className="mb-4">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--muted)] block mb-1.5">
                    Proposed Actions:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {req.actions.map((act) => (
                      <code
                        key={act}
                        className="rounded border border-red-500/15 bg-red-950/20 px-1.5 py-0.5 font-mono text-[10px] text-[#ffc6c1]"
                      >
                        {act}
                      </code>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/5 pt-3">
                <span className="text-[10px] text-[var(--muted)]" suppressHydrationWarning>
                  {new Date(req.created_at).toLocaleString()}
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={loadingId !== null || !isAllowed}
                    aria-expanded={rejectingId === req.approval_id}
                    aria-controls={`reject-${req.approval_id}`}
                    onClick={() => {
                      setRejectingId(req.approval_id);
                      setRejectionReason("");
                      setErrorMsg(null);
                    }}
                    className="rounded-lg border border-white/10 bg-white/[0.025] px-3 py-1.5 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 hover:text-white transition-all disabled:opacity-50 disabled:pointer-events-none"
                  >
                    Reject
                  </button>
                  <button
                    disabled={loadingId !== null || rejectingId === req.approval_id || !isAllowed}
                    onClick={() => handleDecision(req.approval_id, "approve", req.severity)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold shadow-sm transition-all disabled:opacity-50 disabled:pointer-events-none ${
                      isAllowed
                        ? "bg-red-600 hover:bg-red-500 text-white"
                        : "bg-white/5 border border-white/10 text-[var(--muted)] cursor-not-allowed"
                    }`}
                    title={!isAllowed ? `Requires ${req.severity === "P1" ? "Admin" : "Operator"} role` : undefined}
                  >
                    {isPending ? "Processing..." : "Approve"}
                  </button>
                </div>
              </div>
              {rejectingId === req.approval_id && (
                <form
                  id={`reject-${req.approval_id}`}
                  className="mt-4 space-y-3 border-t border-white/10 pt-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleDecision(req.approval_id, "reject", req.severity, rejectionReason);
                  }}
                >
                  <p className="text-xs text-[var(--muted)]">
                    Reject {req.approval_id}? Its proposed remediation will not run.
                  </p>
                  <label className="block text-xs text-[#cbd6e9]">
                    Rejection reason (optional)
                    <textarea
                      autoFocus
                      value={rejectionReason}
                      maxLength={2000}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      disabled={isPending}
                      rows={2}
                      className="mt-2 w-full rounded-lg border border-white/15 bg-black/20 p-2 text-sm text-white focus:border-sky-400 focus:outline-none"
                    />
                  </label>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => { setRejectingId(null); setRejectionReason(""); }}
                      className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-[var(--muted)] disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isPending || !isAllowed}
                      className="rounded-lg border border-red-400/40 bg-red-950/30 px-3 py-1.5 text-xs font-semibold text-red-200 disabled:opacity-50"
                    >
                      {isPending ? "Rejecting…" : "Confirm rejection"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
