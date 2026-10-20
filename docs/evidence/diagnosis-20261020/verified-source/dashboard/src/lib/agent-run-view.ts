/** The same trace projection for live SSE and durable result readback. */
export type StepStatus = "running" | "ok" | "fail";
export type Block =
  | { type: "reasoning"; text: string }
  | { type: "tool"; tool: string; status: StepStatus; args?: Record<string, unknown>; result?: unknown };
export type RunEvent = Record<string, unknown>;
export type RunStatus = "running" | "succeeded" | "failed" | "unknown";
export interface ModelCompletion {
  status: "complete" | "incomplete" | "unknown";
  finishReason: string | null;
  text: string;
  toolCallAttempts?: number;
}
export interface Inspection {
  available: boolean;
  deployment: string;
  namespace: string;
  context?: string;
  observedAt?: string;
  currentRevision?: number;
  previousRevision?: number;
  rolloutComplete?: boolean;
  observationConsistency?: {
    status: "consistent" | "inconsistent" | "not_established";
    disagreements: { scope: string; field: string; reported: number; observed: number }[];
  };
  desiredReplicas?: number;
  availableReplicas?: number;
  currentHealth: "kubernetes_readiness" | "not_established";
  previousHealth: "kubernetes_readiness" | "not_established";
  recoveryStatus: "review_candidate" | "not_established";
  candidateRevision?: number;
  reasons: string[];
  sources: { id: string; observedAt: string | null; sha256: string }[];
  error?: string;
}

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function count(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : undefined;
}
function inspections(value: unknown): Inspection[] | undefined {
  if (!Array.isArray(value)) return;
  const results: Inspection[] = [];
  for (const item of value) {
    const row = object(item);
    if (typeof row.deployment !== "string" || typeof row.namespace !== "string") continue;
    const current = count(row.current_revision), previous = count(row.previous_revision), candidate = count(row.candidate_revision);
    const consistency = object(row.observation_consistency);
    const consistencyStatus = ["consistent", "inconsistent", "not_established"].includes(String(consistency.status))
      ? consistency.status as "consistent" | "inconsistent" | "not_established" : undefined;
    const hasConsistency = row.observation_consistency !== undefined && row.observation_consistency !== null;
    const allowsConclusion = !hasConsistency || consistencyStatus === "consistent";
    const validCandidate = allowsConclusion && row.available === true && row.recovery_status === "review_candidate" &&
      row.previous_health === "kubernetes_readiness" && candidate !== undefined && candidate > 0 &&
      candidate === previous && current !== undefined && candidate < current;
    results.push({
      available: row.available === true, deployment: row.deployment, namespace: row.namespace,
      context: typeof row.context === "string" ? row.context : undefined,
      observedAt: typeof row.observed_at === "string" ? row.observed_at : undefined,
      currentRevision: current, previousRevision: previous,
      rolloutComplete: allowsConclusion && row.rollout_complete === true, desiredReplicas: count(row.desired_replicas),
      observationConsistency: hasConsistency ? {
        status: consistencyStatus || "not_established",
        disagreements: Array.isArray(consistency.disagreements) ? consistency.disagreements.flatMap(item => {
          const d = object(item), reported = count(d.reported), observed = count(d.observed);
          return typeof d.scope === "string" && typeof d.field === "string" && reported !== undefined && observed !== undefined
            ? [{scope: d.scope, field: d.field, reported, observed}] : [];
        }) : [],
      } : undefined,
      availableReplicas: count(object(row.rollout_counts).availableReplicas),
      currentHealth: row.current_health === "kubernetes_readiness" ? "kubernetes_readiness" : "not_established",
      previousHealth: row.previous_health === "kubernetes_readiness" ? "kubernetes_readiness" : "not_established",
      recoveryStatus: validCandidate ? "review_candidate" : "not_established",
      candidateRevision: validCandidate ? candidate : undefined,
      reasons: Array.isArray(row.recovery_reasons) ? row.recovery_reasons.filter((s): s is string => typeof s === "string") : [],
      sources: Array.isArray(row.sources) ? row.sources.flatMap(source => {
        const s = object(source);
        return typeof s.source_id === "string" && typeof s.sha256 === "string"
          ? [{id:s.source_id, sha256:s.sha256, observedAt:typeof s.observed_at === "string" ? s.observed_at : null}] : [];
      }) : [],
      error: typeof row.error === "string" ? row.error : undefined,
    });
  }
  return results.length ? results : undefined;
}
export interface SnapshotAnalysis {
  status: string;
  target: { cluster: string; namespace: string; service: string };
  windowStart: string;
  asOf: string;
  sourceIds: string[];
  excluded: { sourceId: string; reasons: string[] }[];
  modelCalled: boolean;
  citationStatus: string;
  error?: string;
}
function snapshotAnalysis(value: unknown): SnapshotAnalysis | undefined {
  const row = object(value), target = object(row.target);
  if (!["insufficient_evidence", "interpreted", "invalid_model_output"].includes(String(row.status)) ||
      typeof target.cluster !== "string" || typeof target.namespace !== "string" || typeof target.service !== "string" ||
      typeof row.window_start !== "string" || typeof row.as_of !== "string") return;
  return {
    status: String(row.status), target: {cluster: target.cluster, namespace: target.namespace, service: target.service},
    windowStart: row.window_start, asOf: row.as_of,
    sourceIds: Array.isArray(row.applicable_source_ids) ? row.applicable_source_ids.filter((x): x is string => typeof x === "string") : [],
    excluded: Array.isArray(row.excluded) ? row.excluded.flatMap(item => {
      const e = object(item);
      return typeof e.source_id === "string" && Array.isArray(e.explanations)
        ? [{sourceId:e.source_id,reasons:e.explanations.filter((x):x is string=>typeof x === "string")}] : [];
    }) : [],
    modelCalled: row.model_called === true, citationStatus: String(row.citation_status || "unknown"),
    error: typeof row.error === "string" ? row.error : undefined,
  };
}

export interface RunSnapshot {
  request_id: string;
  request: { instruction: string; model: string; provider: string; read_only?: boolean };
  status: RunStatus;
  events: RunEvent[];
  error?: string;
}
export interface RunView {
  text: string;
  blocks: Block[];
  streaming: boolean;
  ok?: boolean;
  error?: string;
  inspection?: Inspection[];
  modelCompletion?: ModelCompletion;
  readOnly?: boolean;
  snapshotAnalysis?: SnapshotAnalysis;
}

export function runView(events: RunEvent[], status: RunStatus = "running", error?: string): RunView {
  const view: RunView = { text: "", blocks: [], streaming: true };
  const seen = new Set<number>();
  for (const event of events) {
    if (typeof event.seq === "number") {
      if (seen.has(event.seq)) continue;
      seen.add(event.seq);
    }
    if ((event.type === "ready" || event.type === "done") && typeof event.read_only === "boolean") {
      view.readOnly = event.read_only;
    }
    if (event.type === "reasoning") {
      const text = String(event.text || "");
      const last = view.blocks.at(-1);
      if (last?.type === "reasoning") last.text += text;
      else if (text) view.blocks.push({ type: "reasoning", text });
    } else if (event.type === "tool_call") {
      view.blocks.push({ type: "tool", tool: String(event.tool), status: "running", args: event.args as Record<string, unknown> });
    } else if (event.type === "tool_result") {
      for (let i = view.blocks.length - 1; i >= 0; i--) {
        const block = view.blocks[i];
        if (block.type === "tool" && block.tool === event.tool && block.status === "running") {
          view.blocks[i] = { ...block, status: event.ok === true ? "ok" : "fail", result: event.result };
          break;
        }
      }
    } else if (event.type === "done") {
      view.streaming = false;
      view.ok = typeof event.ok === "boolean" ? event.ok : undefined;
      view.text = String(event.summary || "");
      view.inspection = inspections(event.inspection);
      view.snapshotAnalysis = snapshotAnalysis(event.snapshot_analysis);
      const completion = object(event.model_completion);
      if (typeof completion.text === "string") {
        view.modelCompletion = {
          status: completion.status === "complete" ? "complete" : completion.status === "incomplete" ? "incomplete" : "unknown",
          finishReason: typeof completion.finish_reason === "string" ? completion.finish_reason : null,
          text: completion.text,
          toolCallAttempts: count(completion.tool_call_attempts),
        };
        const last = view.blocks.at(-1);
        if (last?.type === "reasoning" && last.text.trim() === completion.text.trim()) view.blocks.pop();
      }
    } else if (event.type === "error") {
      view.streaming = false;
      view.ok = undefined;
      view.error = String(event.error || "Execution result is unconfirmed.");
      view.text = view.error;
    }
  }
  if (status === "unknown") {
    view.streaming = false;
    view.ok = undefined;
    view.error = error || "Execution result is unconfirmed. Check the workload before starting another request.";
    view.text = view.error;
  } else if (status !== "running") {
    view.streaming = false;
    if ((status === "succeeded" && view.ok !== true) || (status === "failed" && view.ok !== false)) view.ok = undefined;
    // A terminal status without its result event is not evidence of success.
    if (view.ok === undefined) {
      view.error = "The final result is missing. Check the workload state.";
      view.text = view.error;
    }
  }
  return view;
}
