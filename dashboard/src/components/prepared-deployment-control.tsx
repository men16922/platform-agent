"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { runView, type RunSnapshot } from "@/lib/agent-run-view";

type Prepared = {
  request_id: string; service_name: string; namespace: string;
  image_uri: string; replicas: number; environment: string;
};
const inputStyle = "mt-1 w-full rounded-lg border border-white/15 bg-[#101722] px-3 py-2 text-sm";
const buttonStyle = "rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50";

export function PreparedDeploymentControl({ username }: { username: string }) {
  const router = useRouter();
  const storageKey = `prepared-deployment:${username}`;
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState<Prepared | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checks, setChecks] = useState(0);

  useEffect(() => {
    try { setRequestId(sessionStorage.getItem(storageKey)); }
    catch { setError("Request recovery storage is unavailable. Enable session storage before deploying."); }
  }, [storageKey]);

  useEffect(() => {
    if (!requestId) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const read = async () => {
      try {
        const response = await fetch(`/api/dashboard/agents/runs/${requestId}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || data.detail || "Result is unavailable; check again.");
        if (disposed) return;
        setSnapshot(data); setError(null);
        if (data.status === "running") timer = setTimeout(read, 1000);
        else router.refresh();
      } catch (err) {
        if (!disposed) setError(`${err instanceof Error ? err.message : "Result unavailable."} No request was re-submitted.`);
      }
    };
    void read();
    return () => { disposed = true; clearTimeout(timer); };
  }, [requestId, checks, router]);

  const submit = async () => {
    if (!review || submitting) return;
    // Save before sending. A lost POST response must retain the same ID.
    try { sessionStorage.setItem(storageKey, review.request_id); }
    catch { setError("Cannot preserve the request ID. No deployment was submitted."); return; }
    setSubmitting(true); setSnapshot(null); setError(null);
    try {
      const response = await fetch("/api/dashboard/deployments/prepared", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(review),
      });
      const data = await response.json();
      if (!response.ok) {
        // Explicit pre-dispatch validation/auth rejection is safe to edit.
        if ([400, 401, 403, 422].includes(response.status)) {
          sessionStorage.removeItem(storageKey);
          setError(typeof data.detail === "string" ? data.detail : data.error || "Invalid deployment values. Check the fields.");
          return;
        }
        throw new Error(data.error || data.detail || "Acceptance is unconfirmed.");
      }
      setSnapshot(data);
      setRequestId(review.request_id); setOpen(false); setReview(null);
    } catch (err) {
      setRequestId(review.request_id); setOpen(false); setReview(null);
      setError(`${err instanceof Error ? err.message : "Acceptance is unconfirmed."} Check the saved request; do not submit again.`);
    } finally { setSubmitting(false); }
  };

  const view = snapshot ? runView(snapshot.events, snapshot.status, snapshot.error) : null;
  const unresolved = !!requestId && (!snapshot || ["running", "unknown"].includes(snapshot.status));

  return <section className="surface space-y-3 p-4">
    <div className="flex items-center justify-between gap-3">
      <div><p className="font-medium">Deploy a prepared image</p><p className="text-xs text-[var(--muted)]">On-Prem Executor · review exact values, then apply and verify rollout.</p></div>
      <button className={buttonStyle} disabled={unresolved || submitting} onClick={() => { setOpen(true); setReview(null); setError(null); }}>Deploy image</button>
    </div>
    {error && <p role="alert" className="text-sm text-[var(--danger)]">{error}</p>}
    {requestId && <div className="space-y-1 border-t border-white/10 pt-3 text-sm" aria-live="polite">
      <p>Request <code className="text-xs">{requestId}</code> · <strong>{snapshot?.status || "unconfirmed"}</strong></p>
      {view?.text && <p className="break-words">{view.text}</p>}
      <button className="text-xs underline" onClick={() => setChecks((n) => n + 1)}>Check saved result</button>
    </div>}
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="surface max-h-[90vh] w-full max-w-lg overflow-y-auto border border-white/15 bg-[#101722] p-6">
        {review ? <div className="space-y-4">
          <h3 className="text-lg font-semibold">Review deployment</h3>
          <dl className="space-y-2 text-sm">
            {Object.entries({ Service: review.service_name, Namespace: review.namespace, Image: review.image_uri, Replicas: review.replicas, Environment: review.environment }).map(([key, value]) => <div key={key}><dt className="text-xs text-[var(--muted)]">{key}</dt><dd className="break-all">{value}</dd></div>)}
          </dl>
          <p className="text-xs text-[var(--muted)]">Configured on-prem cluster · port 8080 · liveness /healthz. These values go directly to the executor. Application health is not established by rollout alone.</p>
          {error && <p role="alert" className="text-sm text-[var(--danger)]">{error}</p>}
          <div className="flex justify-end gap-3">
            <button type="button" disabled={submitting} onClick={() => setReview(null)}>Edit</button>
            <button type="button" disabled={submitting} onClick={() => { setOpen(false); setReview(null); }}>Cancel</button>
            <button className={buttonStyle} disabled={submitting} onClick={submit}>{submitting ? "Submitting…" : "Confirm deployment"}</button>
          </div>
        </div> : <form className="space-y-3" onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          setReview({ request_id: crypto.randomUUID(), service_name: String(data.get("service_name")), namespace: String(data.get("namespace")), image_uri: String(data.get("image_uri")), replicas: Number(data.get("replicas")), environment: String(data.get("environment")) });
        }}>
          <h3 className="text-lg font-semibold">Prepared on-prem image</h3>
          <label className="block text-xs">Service name<input className={inputStyle} name="service_name" required maxLength={63} pattern="[a-z0-9]([-a-z0-9]*[a-z0-9])?" /></label>
          <label className="block text-xs">Namespace<input className={inputStyle} name="namespace" required maxLength={63} pattern="[a-z0-9]([-a-z0-9]*[a-z0-9])?" /></label>
          <label className="block text-xs">Image URI<input className={inputStyle} name="image_uri" required placeholder="localhost:5001/service:version" /></label>
          <label className="block text-xs">Replicas<input className={inputStyle} name="replicas" type="number" required min={1} max={100} step={1} /></label>
          <label className="block text-xs">Environment<select className={inputStyle} name="environment" required defaultValue=""><option value="" disabled>Select environment</option><option value="dev">Dev</option><option value="staging">Staging</option><option value="production">Production</option></select></label>
          <div className="flex justify-end gap-3 pt-3"><button type="button" onClick={() => setOpen(false)}>Cancel</button><button className={buttonStyle} type="submit">Review deployment</button></div>
        </form>}
      </div>
    </div>}
  </section>;
}
