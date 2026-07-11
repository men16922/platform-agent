"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Deployment } from "@/lib/mock-data";
import { ProviderLogo, providerBadgeStyles } from "@/components/provider-logo";

const PAGE_SIZE = 10;

const statusStyle: Record<string, string> = {
  success: "text-[var(--success)]",
  failed: "text-[var(--danger)]",
  "rolling-back": "text-[var(--warning)]",
  "rolled-back": "text-[var(--warning)]",
};

const providerLabel: Record<string, string> = { gcp: "GCP", azure: "Azure", onprem: "On-Premise", aws: "AWS" };

function ProviderCell({ dep }: { dep: Deployment }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px] font-semibold ${providerBadgeStyles[dep.provider]}`}>
      <ProviderLogo provider={dep.provider} size="sm" />
      {providerLabel[dep.provider] ?? dep.provider}
    </span>
  );
}

const COLUMNS: Record<"provision" | "deploy", string[]> = {
  provision: ["ID", "Cluster", "Mode", "Provider", "Environment", "Status"],
  deploy: ["ID", "Service", "Version", "Cluster", "Provider", "Environment", "Status"],
};

export function HistoryLogTable({
  title,
  accent,
  variant,
  rows,
}: {
  title: string;
  accent: string;
  variant: "provision" | "deploy";
  rows: Deployment[];
}) {
  const router = useRouter();
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const pageRows = rows.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);
  const columns = COLUMNS[variant];

  return (
    <section className="space-y-3">
      <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[#9fb0c9]">
        <span className="h-3 w-0.5 rounded" style={{ background: accent }} />
        {title} <span className="font-normal text-[var(--muted)]">— {rows.length}</span>
      </h3>
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              {columns.map((c) => (
                <th key={c} className={`p-3 ${c === "Trace" ? "text-right" : "text-left"}`}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center text-xs text-[var(--muted)]">
                  No entries yet.
                </td>
              </tr>
            ) : (
              pageRows.map((dep) => (
                <tr
                  key={dep.id}
                  onClick={() => router.push(`/deployments/${dep.id}`)}
                  className="cursor-pointer border-t border-white/6 transition-colors hover:bg-white/[0.025]"
                >
                  <td className="p-3 font-mono text-xs text-[#8ab4f8]">{dep.id}</td>
                  <td className="p-3 font-medium">{dep.service}</td>
                  <td className="p-3"><code className="text-xs">{dep.version}</code></td>
                  {variant === "deploy" && <td className="p-3 text-xs text-[var(--muted)]">{dep.cluster || "—"}</td>}
                  <td className="p-3"><ProviderCell dep={dep} /></td>
                  <td className="p-3 text-[var(--muted)]">{dep.environment}</td>
                  <td className="p-3"><span className={statusStyle[dep.status] ?? "text-[var(--muted)]"}>{dep.status}</span></td>
                </tr>
              ))
            )}
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
    </section>
  );
}
