"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ProviderLogo } from "@/components/provider-logo";
import { AGENT_TOOLS, toolCount } from "@/lib/agent-tools";

type Cloud = "aws" | "gcp" | "azure" | "onprem";

export function AgentCard({ name, provider, llm, cloud, selected = false, onSelect }: { name: string; provider: string; llm: string; cloud: Cloud; selected?: boolean; onSelect?: () => void }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const groups = AGENT_TOOLS[cloud] ?? [];
  const count = toolCount(cloud);

  return (
    <div onClick={onSelect} className={`surface relative cursor-pointer p-4 transition-all duration-200 hover:-translate-y-0.5 ${selected ? "border-[#8ab4f8] bg-[var(--accent-soft)] shadow-[0_0_0_2px_rgba(138,180,248,0.55)]" : ""}`}>
      {selected && (
        <span className="absolute -top-2 -right-2 z-10 inline-flex items-center gap-1 rounded-full bg-[#8ab4f8] px-2 py-0.5 text-[10px] font-bold text-[#0b1220] shadow-[0_2px_8px_rgba(138,180,248,0.5)]">
          ✓ SELECTED
        </span>
      )}
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-8 w-10 shrink-0 items-center justify-center rounded-lg bg-white p-1">
          <ProviderLogo provider={cloud} />
        </span>
        <span className="font-semibold text-sm">{name}</span>
      </div>
      <div className="text-xs text-[var(--muted)]">{provider}</div>
      <div className="mt-1 text-xs text-[var(--muted)]">{llm}</div>

      <button
        onClick={(event) => { event.stopPropagation(); setOpen(true); }}
        className="mt-3 inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] font-semibold text-[var(--muted)] transition-colors hover:border-[#8ab4f8]/40 hover:text-white"
      >
        🔧 Tools <span className="text-[#8ab4f8]">{count}</span>
      </button>

      {open && mounted && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="surface w-full max-w-md max-h-[80vh] overflow-y-auto border border-white/10 p-5 space-y-4 shadow-[0_25px_60px_rgba(0,0,0,0.5)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/6 pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-9 items-center justify-center rounded-lg bg-white p-1">
                  <ProviderLogo provider={cloud} />
                </span>
                <div>
                  <div className="text-sm font-semibold text-[#cbd6e9]">{name}</div>
                  <div className="text-[10px] text-[var(--muted)]">{count} tools · {llm}</div>
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="text-sm text-[var(--muted)] hover:text-white">✕</button>
            </div>

            {groups.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">No tool catalog for this agent yet.</p>
            ) : (
              groups.map((g) => (
                <div key={g.label} className="space-y-1.5">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-[#8ab4f8]">{g.label}</div>
                  {g.tools.map((t) => (
                    <div key={t.name} className="flex items-start gap-2">
                      <code className="shrink-0 rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-[#a9c7ff]">
                        {t.name}
                      </code>
                      <span className="text-[11px] leading-relaxed text-[var(--muted)]">{t.desc}</span>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
