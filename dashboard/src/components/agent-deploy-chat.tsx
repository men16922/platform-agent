"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";

type Verdict = "recommended" | "allowed" | "discouraged";

interface ModelOption {
  id: string;
  label: string;
  llm: string;
  framework: string;
  verdict: Verdict;
  reason: string;
}

interface DeployStep {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
}

interface ChatMessage {
  role: "user" | "agent";
  text: string;
  model?: string;
  provider?: string;
  ok?: boolean;
  steps?: DeployStep[];
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

const stepOk = (result: unknown) =>
  !(result && typeof result === "object" && "error" in result && (result as { error: unknown }).error);

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
  const logRef = useRef<HTMLDivElement>(null);

  const loadModels = useCallback(async (env: string) => {
    try {
      const res = await fetch(`/api/dashboard/agents/models?provider=${encodeURIComponent(env)}`, { cache: "no-store" });
      const data = await res.json();
      const opts: ModelOption[] = data.models || [];
      setModels(opts);
      setModelsNotice(data.source === "static-fallback" ? data.notice : null);
      if (opts.length && !opts.some((m) => m.id === modelId)) {
        setModelId(opts[0].id);
      }
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
  }, [messages, loading]);

  const selected = models.find((m) => m.id === modelId);

  const send = async () => {
    const text = instruction.trim();
    if (!text || !canDeploy || loading) return;

    setMessages((prev) => [...prev, { role: "user", text, model: modelId, provider }]);
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard/agents/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: text, model: modelId, provider }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", text: data.error || "Deploy failed.", error: data.error, hint: data.hint },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            text: data.summary || "(no summary)",
            model: data.model,
            provider: data.provider,
            ok: data.ok,
            steps: data.steps || [],
          },
        ]);
      }
    } catch (err: unknown) {
      setMessages((prev) => [...prev, { role: "agent", text: "Network error reaching the deploy route.", error: String(err) }]);
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
            Pick an environment and model, then describe the deploy in natural language.
          </p>
        </div>
        {!canDeploy && (
          <span className="text-[10px] text-[var(--muted)] italic bg-white/[0.02] border border-white/5 px-2.5 py-1 rounded-md">
            Sign in as Operator/Admin to deploy.
          </span>
        )}
      </div>

      {/* Environment + model selectors */}
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
              <option key={m.id} value={m.id}>
                {m.label} — {m.verdict}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Suitability of the selected model */}
      {selected && (
        <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[11px] ${verdictStyle[selected.verdict]}`}>
          <span className="font-bold uppercase tracking-wide">{selected.verdict}</span>
          <span className="opacity-90">{selected.reason}</span>
        </div>
      )}
      {modelsNotice && (
        <p className="text-[10px] text-[var(--warning)]">⚠️ {modelsNotice}</p>
      )}

      {/* Chat log */}
      <div ref={logRef} className="max-h-[22rem] overflow-y-auto space-y-3 rounded-lg border border-white/6 bg-black/20 p-3">
        {messages.length === 0 && (
          <p className="text-xs text-[var(--muted)] py-6 text-center">
            No deploys yet. Describe what to deploy and the selected model will run build → push → deploy → validate.
          </p>
        )}
        {messages.map((msg, i) => (
          <ChatBubble key={i} msg={msg} />
        ))}
        {loading && (
          <div className="text-xs text-[var(--muted)] flex items-center gap-2">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[#8ab4f8]" />
            Agent is deploying…
          </div>
        )}
      </div>

      {/* Input */}
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
          {msg.ok !== undefined && (
            <span
              className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                msg.ok ? "bg-emerald-400/10 text-[var(--success)]" : "bg-red-400/10 text-[var(--danger)]"
              }`}
            >
              {msg.ok ? "SUCCESS" : "FAILED"}
            </span>
          )}
          {msg.model && <span className="text-[9px] uppercase tracking-wide text-[var(--muted)]">{msg.model}</span>}
        </div>

        <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>

        {msg.steps && msg.steps.length > 0 && (
          <div className="space-y-1 pt-1">
            {msg.steps.map((step, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className={stepOk(step.result) ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                  {stepOk(step.result) ? "✓" : "✗"}
                </span>
                <code className="rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-[var(--muted)]">
                  {step.tool}
                </code>
              </div>
            ))}
          </div>
        )}

        {msg.hint && <p className="text-[10px] text-[var(--warning)] pt-1">💡 {msg.hint}</p>}
      </div>
    </div>
  );
}
