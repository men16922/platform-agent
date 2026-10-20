import type { Inspection, ModelCompletion } from "@/lib/agent-run-view";

export function InspectionResult({ reports }: { reports: Inspection[] }) {
  return <div className="space-y-3" aria-label="Recorded observations">
    {reports.map((report, index) => <section key={index} className="rounded-lg border border-[#8ab4f8]/25 bg-[#8ab4f8]/5 p-3 space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-[#a9c7ff]">Recorded observations</div>
      <h4 className="font-semibold">{report.namespace}/{report.deployment}</h4>
      {!report.available ? <p className="text-[var(--warning)]">Structured observation unavailable. Recovery is not established. {report.error}</p> : <>
        <p className="text-[10px] text-[var(--muted)]">Context: {report.context || "not recorded"} · Observed: {report.observedAt || "time not recorded"}</p>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5">
          <dt>Current revision</dt><dd>{report.currentRevision ?? "Unknown"}</dd>
          <dt>Rollout</dt><dd>{report.rolloutComplete ? "Complete" : "Not confirmed complete"}</dd>
          {report.observationConsistency && <><dt>Observation consistency</dt><dd>{report.observationConsistency.status === "consistent" ? "No disagreement detected" : report.observationConsistency.status === "inconsistent" ? "Deployment, ReplicaSet and Pod observations disagree" : "Not established"}</dd></>}
          <dt>Available / desired</dt><dd>{report.availableReplicas ?? "?"} / {report.desiredReplicas ?? "?"} replicas</dd>
          <dt>Application health</dt><dd>{report.currentHealth === "kubernetes_readiness" ? "Kubernetes readiness observed" : "Not established"}</dd>
          <dt>Previous revision</dt><dd>{report.previousRevision ?? "Unknown"} · {report.previousHealth === "kubernetes_readiness" ? "Kubernetes readiness observed" : "health not established"}</dd>
        </dl>
        {report.observationConsistency?.status === "inconsistent" && <div className="text-[var(--warning)]">
          <p>Re-read the same target before concluding completion or reviewing recovery. These reads are not an atomic snapshot.</p>
          <ul className="list-disc pl-4">{report.observationConsistency.disagreements.map((d, i) => <li key={i}>{d.scope} · {d.field}: reported {d.reported}, observed {d.observed}</li>)}</ul>
        </div>}
        <div className="border-t border-white/10 pt-2">
          <h5 className="font-semibold">Recovery review</h5>
          <p>{report.recoveryStatus === "review_candidate" ? `Revision ${report.candidateRevision} is a review candidate.` : "No supported recovery candidate."}</p>
          {!!report.reasons.length && <ul className="list-disc pl-4 mt-1 space-y-1 text-[var(--muted)]">{report.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul>}
          <p className="mt-2 text-[var(--warning)]">This assessment does not authorize a change.</p>
        </div>
        <p className="text-[10px] text-[var(--muted)]">These are recorded observations, not a root-cause finding. External service health and recovery on new nodes have not been verified.</p>
        {!!report.sources.length && <details className="text-[10px] text-[var(--muted)]">
          <summary className="cursor-pointer">Observation sources ({report.sources.length})</summary>
          <ul className="mt-1 space-y-1">{report.sources.map((source, i) => <li key={i} className="break-all">{source.id} · {source.observedAt || "time unknown"}<br />SHA256: {source.sha256}</li>)}</ul>
        </details>}
      </>}
    </section>)}
  </div>;
}

export function ModelInterpretation({ completion }: { completion: ModelCompletion }) {
  const status = completion.status === "complete" ? "Response complete" : completion.status === "incomplete" ? "Response incomplete" : "Completion not recorded";
  return <details className="rounded border border-white/10 p-2 text-[11px] text-[var(--muted)]">
    <summary className="cursor-pointer">Model interpretation · {status} · Unverified</summary>
    <p className="mt-2 text-[var(--warning)]">This text may contain incorrect conclusions. Use the recorded observations for state and recovery review. It cannot authorize a change.</p>
    {completion.status !== "complete" && <p className="mt-1">The model did not confirm a completed response{completion.finishReason ? ` (${completion.finishReason})` : ""}. Tool results are recorded separately.</p>}
    <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-sans leading-relaxed">{completion.text || "No interpretation returned."}</pre>
  </details>;
}
