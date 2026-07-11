"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { ModelLogo } from "@/components/model-logo";

type Verdict = "recommended" | "allowed" | "discouraged";
type StepStatus = "running" | "ok" | "fail";

interface ModelOption {
  id: string;
  label: string;
  llm: string;
  framework: string;
  verdict: Verdict;
  reason: string;
}

type Block =
  | { type: "reasoning"; text: string }
  | { type: "tool"; tool: string; status: StepStatus };

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
}

const ENVIRONMENTS: { id: string; label: string }[] = [
  { id: "onprem", label: "On-Prem" },
  { id: "aws", label: "AWS" },
  { id: "gcp", label: "Google Cloud" },
  { id: "azure", label: "Azure" },
];

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

export function AgentDeployChat() {
  const { data: session } = useSession();
  const role = (session?.user as { role?: string } | undefined)?.role || "viewer";
  const canDeploy = role === "admin" || role === "operator";

  const [provider, setProvider] = useState("onprem");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelId, setModelId] = useState("local-qwen");
  const [modelsNotice, setModelsNotice] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("Deploy orders-api v1.4.2 to the local cluster with 2 replicas");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const idRef = useRef(0);
  const logRef = useRef<HTMLDivElement>(null);

  const loadModels = useCallback(async (env: string) => {
    try {
      const res = await fetch(`/api/dashboard/agents/models?provider=${encodeURIComponent(env)}`, { cache: "no-store" });
      const data = await res.json();
      const opts: ModelOption[] = data.models || [];
      setModels(opts);
      setModelsNotice(data.source === "static-fallback" ? data.notice : null);
      if (opts.length && !opts.some((m) => m.id === modelId)) setModelId(opts[0].id);
    } catch {
      setModels([]);
      setModelsNotice("Could not load model options.");
    }
  }, [modelId]);

  useEffect(() => {
    loadModels(provider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const selected = models.find((m) => m.id === modelId);

  const send = async () => {
    const text = instruction.trim();
    if (!text || !canDeploy || loading) return;

    const userId = ++idRef.current;
    const agentId = ++idRef.current;
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text, model: modelId, provider },
      { id: agentId, role: "agent", text: "", blocks: [], streaming: true, model: modelId, provider },
    ]);
    setLoading(true);

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === agentId ? fn(m) : m)));

    try {
      const res = await fetch("/api/dashboard/agents/deploy/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: text, model: modelId, provider }),
      });

      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({ error: "Deploy stream failed." }));
        patch((m) => ({ ...m, streaming: false, error: d.error, text: d.error || "failed", hint: d.hint }));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
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
          if (ev.type === "reasoning") {
            const text = String(ev.text || "");
            if (text) {
              patch((m) => {
                const blocks = [...(m.blocks || [])];
                const last = blocks[blocks.length - 1];
                if (last && last.type === "reasoning") {
                  blocks[blocks.length - 1] = { type: "reasoning", text: last.text + text };
                } else {
                  blocks.push({ type: "reasoning", text });
                }
                return { ...m, blocks };
              });
            }
          } else if (ev.type === "tool_call") {
            patch((m) => ({ ...m, blocks: [...(m.blocks || []), { type: "tool", tool: String(ev.tool), status: "running" }] }));
          } else if (ev.type === "tool_result") {
            patch((m) => {
              const blocks = [...(m.blocks || [])];
              for (let i = blocks.length - 1; i >= 0; i--) {
                const b = blocks[i];
                if (b.type === "tool" && b.tool === ev.tool && b.status === "running") {
                  blocks[i] = { ...b, status: ev.ok ? "ok" : "fail" };
                  break;
                }
              }
              return { ...m, blocks };
            });
          } else if (ev.type === "done") {
            patch((m) => ({ ...m, streaming: false, ok: Boolean(ev.ok), text: String(ev.summary || "") }));
          } else if (ev.type === "error") {
            patch((m) => ({ ...m, streaming: false, error: String(ev.error), text: String(ev.error || "failed") }));
          }
        }
      }
    } catch (err: unknown) {
      patch((m) => ({ ...m, streaming: false, error: String(err), text: "Network error reaching the deploy stream." }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="surface p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-semibold text-[#cbd6e9]">Deploy via chat — AI Model Router</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Pick an environment and model, then describe the deploy — tool calls stream in live.
          </p>
        </div>
        {!canDeploy && (
          <span className="text-[10px] text-[var(--muted)] italic bg-white/[0.02] border border-white/5 px-2.5 py-1 rounded-md">
            Sign in as Operator/Admin to deploy.
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">Environment</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
          >
            {ENVIRONMENTS.map((env) => (
              <option key={env.id} value={env.id}>{env.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">AI Model</label>
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.label} — {m.verdict}</option>
            ))}
          </select>
        </div>
      </div>

      {selected && (
        <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[11px] ${verdictStyle[selected.verdict]}`}>
          <ModelLogo model={selected.id} />
          <span className="font-bold uppercase tracking-wide">{selected.verdict}</span>
          <span className="opacity-90">{selected.reason}</span>
        </div>
      )}
      {modelsNotice && <p className="text-[10px] text-[var(--warning)]">⚠️ {modelsNotice}</p>}

      <div ref={logRef} className="max-h-[24rem] overflow-y-auto space-y-3 rounded-lg border border-white/6 bg-black/20 p-3">
        {messages.length === 0 && (
          <p className="text-xs text-[var(--muted)] py-6 text-center">
            No deploys yet. Describe what to deploy and the selected model will run build → push → deploy → validate.
          </p>
        )}
        {messages.map((msg) => (
          <ChatBubble key={msg.id} msg={msg} />
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={instruction}
          disabled={!canDeploy || loading}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="e.g. Deploy orders-api v1.4.2 to the local cluster with 2 replicas"
          className="flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8] disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={!canDeploy || loading || !instruction.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Deploying…" : "Deploy"}
        </button>
      </div>
    </section>
  );
}

// Minimal, dependency-free markdown for the agent's summary (our own LLM output):
// **bold**, `code`, and `-`/`*` bullet lists. Text is rendered via React children,
// so it is escaped — no HTML injection.
function renderInline(text: string, keyBase: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const tok = match[0];
    if (tok.startsWith("**")) {
      nodes.push(<strong key={`${keyBase}-${i}`} className="font-semibold text-[#e6edf7]">{tok.slice(2, -2)}</strong>);
    } else {
      nodes.push(
        <code key={`${keyBase}-${i}`} className="rounded bg-white/[0.06] px-1 py-0.5 text-[10px] text-[#a9c7ff]">{tok.slice(1, -1)}</code>,
      );
    }
    last = match.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (key: string) => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={key} className="list-disc space-y-0.5 pl-4 marker:text-[var(--muted)]">
        {bullets.map((li, i) => <li key={i}>{renderInline(li, `${key}-${i}`)}</li>)}
      </ul>,
    );
    bullets = [];
  };
  lines.forEach((line, idx) => {
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }
    flush(`ul-${idx}`);
    if (line.trim() === "") {
      blocks.push(<div key={`sp-${idx}`} className="h-1" />);
      return;
    }
    blocks.push(<p key={`p-${idx}`} className="leading-relaxed">{renderInline(line, `p-${idx}`)}</p>);
  });
  flush("ul-end");
  return <div className="space-y-1">{blocks}</div>;
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg rounded-br-sm bg-[#8ab4f8]/10 border border-[#8ab4f8]/25 px-3 py-2 text-xs text-[#cbd6e9]">
          <div className="mb-1 flex gap-1.5 text-[9px] uppercase tracking-wide text-[var(--muted)]">
            <span>{msg.provider}</span>·<span>{msg.model}</span>
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
          {msg.streaming ? (
            <span className="text-[9px] font-bold text-[#8ab4f8] flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[#8ab4f8]" /> DEPLOYING
            </span>
          ) : msg.ok !== undefined ? (
            <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${msg.ok ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"}`}>
              {msg.ok ? "SUCCESS" : "FAILED"}
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
                <p key={i} className="border-l-2 border-[#8ab4f8]/30 pl-2 text-[11px] italic leading-relaxed text-[var(--muted)] whitespace-pre-wrap">
                  {block.text}
                </p>
              ) : (
                <div key={i} className="flex items-center gap-2">
                  <span className={stepMark[block.status].cls}>{stepMark[block.status].icon}</span>
                  <code className="rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-[var(--muted)]">
                    {block.tool}
                  </code>
                </div>
              ),
            )}
          </div>
        )}

        {msg.text && (
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
