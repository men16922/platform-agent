"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { ModelLogo } from "@/components/model-logo";
import { Markdown } from "@/components/markdown";
import { InspectionResult, ModelInterpretation } from "@/components/inspection-result";
import { runView, type Block, type RunEvent, type RunSnapshot, type StepStatus, type Inspection, type ModelCompletion, type SnapshotAnalysis } from "@/lib/agent-run-view";

type Verdict = "recommended" | "allowed" | "discouraged";

interface ModelOption {
  id: string;
  label: string;
  llm: string;
  framework: string;
  verdict: Verdict;
  reason: string;
}

interface ChatMessage {
  id: number;
  role: "user" | "agent";
  text: string;
  model?: string;
  provider?: string;
  ok?: boolean;
  blocks?: Block[];
  streaming?: boolean;
  error?: string;
  hint?: string;
  inspection?: Inspection[];
  modelCompletion?: ModelCompletion;
  readOnly?: boolean;
  snapshotAnalysis?: SnapshotAnalysis;
}

interface ActiveRun {
  id: string;
  userId: number;
  agentId: number;
  lookup: boolean;
}

const verdictStyle: Record<Verdict, string> = {
  recommended: "bg-emerald-400/10 text-[var(--success)] border-emerald-500/30",
  allowed: "bg-amber-400/10 text-[var(--warning)] border-amber-500/30",
  discouraged: "bg-red-400/10 text-[var(--danger)] border-red-500/30",
};

const stepMark: Record<StepStatus, { icon: string; cls: string }> = {
  running: { icon: "◐", cls: "text-[#8ab4f8] animate-pulse" },
  ok: { icon: "✓", cls: "text-[var(--success)]" },
  fail: { icon: "✗", cls: "text-[var(--danger)]" },
};

export function AgentDeployChat({ selectedProvider, agentName, modelId, model }: { selectedProvider: string; agentName: string; modelId: string; model: ModelOption | null }) {
  const { data: session } = useSession();
  const role = (session?.user as { role?: string } | undefined)?.role || "viewer";
  const canDeploy = role === "admin" || role === "operator";

  const provider = selectedProvider;
  const [instruction, setInstruction] = useState("");
  const [readOnly, setReadOnly] = useState(false);
  const [snapshotMode, setSnapshotMode] = useState(false);
  const [snapshotText, setSnapshotText] = useState("");
  const [snapshotError, setSnapshotError] = useState("");
  const supportsInspection = provider === "onprem" && modelId === "local-qwen";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [needsReview, setNeedsReview] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [lookupMessage, setLookupMessage] = useState("");
  const username = session?.user?.username;
  const storageKey = username ? `platform-agent:last-run:${username}` : null;
  const idRef = useRef(0);
  const logRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<AbortController | null>(null);

  // Store only the request ID. Reloading observes the durable run; it never POSTs.
  useEffect(() => {
    const cleanup = () => { streamRef.current?.abort(); streamRef.current = null; };
    streamRef.current?.abort();
    streamRef.current = null;
    setMessages([]);
    setActiveRun(null);
    setLoading(false);
    setUnconfirmed(false);
    setNeedsReview(false);
    setReviewed(false);
    setLookupMessage("");
    if (!storageKey || !canDeploy) return cleanup;
    let id: string | null = null;
    try { id = sessionStorage.getItem(storageKey); } catch { /* New requests check storage before dispatch. */ }
    if (!id) return cleanup;
    const userId = ++idRef.current;
    const agentId = ++idRef.current;
    setMessages([
      { id: userId, role: "user", text: "Restoring the previous request…" },
      { id: agentId, role: "agent", text: "Checking the recorded result…" },
    ]);
    setUnconfirmed(true);
    setActiveRun({ id, userId, agentId, lookup: true });
    return cleanup;
  }, [storageKey, canDeploy]);

  useEffect(() => {
    if (!activeRun?.lookup || !canDeploy) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/dashboard/agents/runs/${activeRun.id}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 404
          ? "The request is not visible yet. Check again before submitting any new work."
          : "Run state is unavailable. Check again; the request has not been re-submitted.");
        const snapshot: RunSnapshot = await response.json();
        if (snapshot.request_id !== activeRun.id || !Array.isArray(snapshot.events) ||
            !["running", "succeeded", "failed", "unknown"].includes(snapshot.status) || !snapshot.request) {
          throw new Error("Run state could not be verified.");
        }
        if (controller.signal.aborted) return;
        const view = runView(snapshot.events, snapshot.status, snapshot.error);
        setMessages((previous) => previous.map((message) => message.id === activeRun.agentId
          ? { ...message, ...view, model: snapshot.request.model, provider: snapshot.request.provider }
          : message.id === activeRun.userId ? { ...message, text: snapshot.request.instruction, model: snapshot.request.model, provider: snapshot.request.provider, readOnly: snapshot.request.read_only } : message));
        setLookupMessage(snapshot.status === "running" ? "Observing the existing request. No re-submission." : "");
        setUnconfirmed(snapshot.status === "running" || snapshot.status === "unknown" || view.ok === undefined);
        setNeedsReview(snapshot.status === "unknown");
        setReviewed(false);
        if (snapshot.status === "running") timer = setTimeout(read, 1_000);
        else {
          setLoading(false);
          setActiveRun((run) => run?.id === activeRun.id ? { ...run, lookup: false } : run);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setLoading(false);
        setUnconfirmed(true);
        setNeedsReview(false);
        setLookupMessage(error instanceof Error ? error.message : "Run state is unconfirmed.");
        setActiveRun((run) => run?.id === activeRun.id ? { ...run, lookup: false } : run);
        setMessages((previous) => previous.map((message) => message.id === activeRun.agentId ? { ...message, streaming: false } : message));
      }
    };
    void read();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [activeRun, canDeploy]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    let snapshot: Record<string, unknown> | undefined;
    let text = instruction.trim();
    setSnapshotError("");
    if (snapshotMode) {
      if (!readOnly || !supportsInspection) return;
      try {
        const parsed: unknown = JSON.parse(snapshotText);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) ||
            typeof (parsed as Record<string, unknown>).question !== "string") throw new Error();
        snapshot = parsed as Record<string, unknown>;
        text = snapshot.question as string;
      } catch {
        setSnapshotError("Enter a snapshot JSON object with a question, target, observation window and sources.");
        return;
      }
    }
    if (!text || !canDeploy || loading || unconfirmed || !storageKey || streamRef.current || (readOnly && !supportsInspection)) return;

    const requestId = crypto.randomUUID();
    try { sessionStorage.setItem(storageKey, requestId); }
    catch {
      setLookupMessage("Browser storage is unavailable. Enable it before starting a request so its result can be recovered.");
      return;
    }
    const controller = new AbortController();
    streamRef.current = controller;

    const userId = ++idRef.current;
    const agentId = ++idRef.current;
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text, model: modelId, provider, readOnly },
      { id: agentId, role: "agent", text: "", blocks: [], streaming: true, model: modelId, provider },
    ]);
    setLoading(true);
    setUnconfirmed(true);
    setNeedsReview(false);
    setReviewed(false);
    setLookupMessage("");
    setActiveRun({ id: requestId, userId, agentId, lookup: false });

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      { if (streamRef.current === controller) setMessages((prev) => prev.map((m) => (m.id === agentId ? fn(m) : m))); };

    let confirmed = false;

    try {
      const res = await fetch("/api/dashboard/agents/deploy/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: text, model: modelId, provider, request_id: requestId, read_only: readOnly, ...(snapshot ? { snapshot } : {}) }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({ error: "Deploy stream failed." }));
        patch((m) => ({ ...m, streaming: false, error: d.error, text: d.error || "failed", hint: d.hint }));
        if ([400, 401, 403, 422].includes(res.status)) {
          // These validation/auth gates reject before a durable run is claimed.
          // Conflict, unavailable storage and transport loss still need readback.
          confirmed = true;
          try { sessionStorage.removeItem(storageKey); } catch { /* No action was accepted. */ }
          setActiveRun(null);
        }
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      const events: RunEvent[] = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split("\n\n");
        buf = chunks.pop() || "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          let ev: Record<string, unknown>;
          try {
            ev = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (ev.request_id !== requestId) continue;
          events.push(ev);
          const view = runView(events);
          patch((message) => ({ ...message, ...view }));
          confirmed = !view.streaming && view.ok !== undefined;
        }
      }
    } catch (err: unknown) {
      if (!confirmed) patch((m) => ({ ...m, streaming: false, error: String(err), text: "Connection lost. Checking the recorded result." }));
    } finally {
      if (streamRef.current === controller) {
        patch((message) => ({ ...message, streaming: false }));
        streamRef.current = null;
        setLoading(false);
        setUnconfirmed(!confirmed);
        if (!confirmed) {
          setLookupMessage("Connection ended. Checking the existing request…");
          setActiveRun((run) => run?.id === requestId ? { ...run, lookup: true } : run);
        }
      }
    }
  };

  return (
    <section className="surface p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-semibold text-[#cbd6e9]">Ask {agentName}</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Runs with the Agent and AI Model selected above. Investigate, deploy, or recover with a live trace.
          </p>
        </div>
        {!canDeploy && (
          <span className="text-[10px] text-[var(--muted)] italic bg-white/[0.02] border border-white/5 px-2.5 py-1 rounded-md">
            Sign in as Operator/Admin to deploy.
          </span>
        )}
      </div>

      {model && <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[11px] ${verdictStyle[model.verdict]}`}><ModelLogo model={model.id} /><span className="font-bold uppercase tracking-wide">{model.verdict}</span><span className="opacity-90">{model.reason}</span></div>}

      <div ref={logRef} className="max-h-[75vh] min-h-[34rem] overflow-y-auto space-y-3 rounded-lg border border-white/6 bg-black/20 p-3">
        {messages.length === 0 && (
          <p className="text-xs text-[var(--muted)] py-6 text-center">
            Describe an operational goal. The selected agent can inspect systems, provision infrastructure, deploy services, diagnose incidents, and run governed recovery actions — every reasoning step and tool call streams here.
          </p>
        )}
        {messages.map((msg) => (
          <ChatBubble key={msg.id} msg={msg} />
        ))}
      </div>

      <div className="space-y-1 text-xs text-[var(--muted)]">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={readOnly} disabled={!canDeploy || loading || unconfirmed}
            onChange={(event) => setReadOnly(event.target.checked)} />
          Read-only inspection
        </label>
        <p>{readOnly
          ? "Only inspection tools are available for this request. Deploy, rollback and provisioning are disabled."
          : "Operational actions are available when requested. Select read-only inspection to limit this request."}</p>
        {readOnly && !supportsInspection && <p className="text-[var(--warning)]">Select On-Prem and Local Qwen to use read-only inspection.</p>}
      </div>
      <div className="space-y-2 text-xs text-[var(--muted)]">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={snapshotMode} disabled={!canDeploy || loading || unconfirmed || !readOnly || !supportsInspection}
            onChange={(event) => setSnapshotMode(event.target.checked)} />
          Analyze supplied snapshot
        </label>
        {snapshotMode && <>
          <p>Checks each source against the declared target and time window. No tools run. Supplied records are not verified live observations.</p>
          <label className="block">Snapshot JSON
            <textarea value={snapshotText} onChange={(event) => setSnapshotText(event.target.value)}
              disabled={!canDeploy || loading || unconfirmed} rows={7} maxLength={80000}
              className="mt-1 w-full rounded border border-white/10 bg-white/5 p-2 font-mono text-xs" />
          </label>
          <p>Include question, target (cluster, namespace, service), window_start, as_of, and sources with source_id, target, observed_at, provenance (supplied_snapshot), and text.</p>
        </>}
        {snapshotError && <p role="alert" className="text-[var(--danger)]">{snapshotError}</p>}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={instruction}
          disabled={!canDeploy || loading || unconfirmed || snapshotMode}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask the agent — e.g. 'list pods in default' or 'deploy orders-api v1.4.2 with 2 replicas'"
          className="flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8] disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={!canDeploy || loading || unconfirmed || !(snapshotMode ? snapshotText.trim() : instruction.trim()) || (readOnly && !supportsInspection) || (snapshotMode && !readOnly)}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>
      {activeRun && <div className="space-y-2 text-xs text-[var(--muted)]">
        <p className="break-all">Request: {activeRun.id}</p>
        {unconfirmed && <p>Result unconfirmed. Check this request and the workload before starting new work.</p>}
        <button disabled={loading} onClick={() => setActiveRun({ ...activeRun, lookup: true })}
          className="rounded border border-white/10 px-3 py-1.5 disabled:opacity-50">Check recorded result</button>
        {needsReview && !loading && <div className="space-y-2">
          <label className="flex items-center gap-2"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} />
            I checked the workload and confirmed that the original worker is no longer running.</label>
          <button disabled={!reviewed} onClick={() => {
            if (!storageKey) return;
            try { sessionStorage.removeItem(storageKey); } catch { return; }
            setActiveRun(null); setUnconfirmed(false); setNeedsReview(false); setReviewed(false);
            setLookupMessage("The previous result remains unknown in the record. A new request will receive a new ID.");
          }} className="rounded border border-white/10 px-3 py-1.5 disabled:opacity-50">Allow a new request after review</button>
        </div>}
      </div>}
      {lookupMessage && <p role="status" className="text-xs text-[var(--warning)]">{lookupMessage}</p>}
    </section>
  );
}


function ToolBlock({ block }: { block: { tool: string; status: StepStatus; args?: Record<string, unknown>; result?: unknown } }) {
  const [open, setOpen] = useState(false);
  const hasArgs = block.args && Object.keys(block.args).length > 0;
  const hasResult = block.result !== undefined && block.result !== null;
  const hasDetail = hasArgs || hasResult;
  const mark = stepMark[block.status];
  return (
    <div>
      <button
        type="button"
        onClick={() => hasDetail && setOpen((o) => !o)}
        className={`flex items-center gap-2 ${hasDetail ? "cursor-pointer" : "cursor-default"}`}
      >
        <span className={mark.cls}>{mark.icon}</span>
        <code className="rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-[var(--muted)]">{block.tool}</code>
        {hasDetail && <span className="text-[9px] text-[var(--muted)]">{open ? "▾" : "▸"}</span>}
      </button>
      {open && (
        <div className="mt-1 ml-6 space-y-1">
          {hasArgs && (
            <pre className="overflow-x-auto rounded border border-white/6 bg-black/25 p-1.5 text-[10px] text-[#a9c7ff]">
              args: {JSON.stringify(block.args)}
            </pre>
          )}
          {hasResult && (
            <pre className="max-h-44 overflow-auto rounded border border-white/6 bg-black/25 p-1.5 text-[10px] text-[#a9c7ff]">
              {typeof block.result === "string" ? block.result : JSON.stringify(block.result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const noToolCalls = msg.modelCompletion?.status === "complete" && msg.modelCompletion.toolCallAttempts === 0;
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg rounded-br-sm bg-[#8ab4f8]/10 border border-[#8ab4f8]/25 px-3 py-2 text-xs text-[#cbd6e9]">
          <div className="mb-1 flex gap-1.5 text-[9px] uppercase tracking-wide text-[var(--muted)]">
            <span>{msg.provider}</span>·<span>{msg.model}</span>{msg.readOnly === true && <span>· Read-only requested</span>}
          </div>
          {msg.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-lg rounded-bl-sm border border-white/8 bg-white/[0.03] px-3 py-2.5 text-xs text-[#cbd6e9] space-y-2">
        <div className="flex items-center gap-2">
          {msg.readOnly === true && <span className="text-[9px] font-bold text-[#8ab4f8]">READ-ONLY TOOLS</span>}
          {msg.streaming ? (
            <span className="text-[9px] font-bold text-[#8ab4f8] flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[#8ab4f8]" /> RUNNING
            </span>
          ) : msg.ok !== undefined ? (
            <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${noToolCalls || msg.snapshotAnalysis ? "bg-white/5 text-[var(--muted)]" : msg.ok ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"}`}>
              {msg.snapshotAnalysis ? "SNAPSHOT REVIEW" : noToolCalls ? "NO TOOL CALLS" : msg.ok ? (msg.inspection ? "OBSERVATIONS RECORDED" : "SUCCESS") : "FAILED"}
            </span>
          ) : null}
          {msg.model && (
            <span className="inline-flex items-center gap-1 text-[9px] uppercase tracking-wide text-[var(--muted)]">
              <ModelLogo model={msg.model} /> {msg.model}
            </span>
          )}
        </div>

        {(msg.blocks?.length ?? 0) > 0 && (
          <div className="space-y-1.5">
            {msg.blocks!.map((block, i) =>
              block.type === "reasoning" ? (
                <details key={i} className="border-l-2 border-[#8ab4f8]/30 pl-2 text-[11px] text-[var(--muted)]">
                  <summary className="cursor-pointer">Model draft · Unverified</summary>
                  <p className="max-h-64 overflow-auto whitespace-pre-wrap leading-relaxed">{block.text}</p>
                </details>
              ) : (
                <ToolBlock key={i} block={block} />
              ),
            )}
          </div>
        )}

        {msg.snapshotAnalysis && <div className="space-y-2 rounded border border-white/10 p-2">
          <p className="font-semibold">Supplied snapshot · No execution authorized</p>
          <p>{msg.snapshotAnalysis.target.cluster} / {msg.snapshotAnalysis.target.namespace} / {msg.snapshotAnalysis.target.service}</p>
          <p>Declared window: {msg.snapshotAnalysis.windowStart} → {msg.snapshotAnalysis.asOf}</p>
          <p>Applicable sources: {msg.snapshotAnalysis.sourceIds.join(", ") || "None"}</p>
          {msg.snapshotAnalysis.excluded.map(source => <p key={source.sourceId}>Excluded [{source.sourceId}]: {source.reasons.join(" ")}</p>)}
          <p>{msg.snapshotAnalysis.modelCalled ? "Model interpretation requires review. Source matching does not prove its conclusions." : "No model called: no source applies to this target and time window."}</p>
          {msg.snapshotAnalysis.error && <p className="text-[var(--warning)]">{msg.snapshotAnalysis.error}</p>}
        </div>}
        {msg.inspection && !msg.error && <InspectionResult reports={msg.inspection} />}
        {msg.modelCompletion && msg.inspection && !msg.error && <ModelInterpretation completion={msg.modelCompletion} />}
        {msg.modelCompletion && !msg.inspection && msg.modelCompletion.status !== "complete" && <p className="text-[var(--warning)]">Model response {msg.modelCompletion.status === "incomplete" ? "incomplete" : "completion not recorded"}. Tool execution results are separate.</p>}
        {msg.modelCompletion && !msg.inspection && !msg.error && <p className="text-[10px] text-[var(--muted)]">Model interpretation · Unverified</p>}
        {msg.text && (!msg.inspection || msg.error) && (
          msg.error ? (
            <p className="leading-relaxed whitespace-pre-wrap pt-1 text-[var(--danger)]">{msg.text}</p>
          ) : (
            <div className="pt-1"><Markdown text={msg.text} /></div>
          )
        )}
        {msg.hint && <p className="text-[10px] text-[var(--warning)] pt-1">💡 {msg.hint}</p>}
      </div>
    </div>
  );
}
