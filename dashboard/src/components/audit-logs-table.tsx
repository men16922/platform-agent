"use client";

import { useState } from "react";
import type { AuditLogEntry } from "@/lib/audit-data";

interface AuditLogsTableProps {
  initialLogs: AuditLogEntry[];
}

export function AuditLogsTable({ initialLogs }: AuditLogsTableProps) {
  const [logs] = useState<AuditLogEntry[]>(initialLogs);
  const [search, setSearch] = useState("");
  const [resultFilter, setResultFilter] = useState<"all" | "success" | "failed">("all");

  const filteredLogs = logs.filter((log) => {
    const whoStr = `${log.who.username} ${log.who.email || ""}`.toLowerCase();
    const whatStr = `${log.what.action} ${log.what.target}`.toLowerCase();
    const idStr = log.audit_id.toLowerCase();
    const ipStr = (log.context?.ip || "").toLowerCase();

    const matchesSearch =
      whoStr.includes(search.toLowerCase()) ||
      whatStr.includes(search.toLowerCase()) ||
      idStr.includes(search.toLowerCase()) ||
      ipStr.includes(search.toLowerCase());

    const matchesResult =
      resultFilter === "all" || log.result === resultFilter;

    return matchesSearch && matchesResult;
  });

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by ID, user, action, target or IP..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs text-[#cbd6e9] placeholder-[var(--muted)] focus:outline-none focus:border-[#8ab4f8] transition-all"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-2.5 text-xs text-[var(--muted)] hover:text-white"
            >
              ✕
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
            Result:
          </span>
          <select
            value={resultFilter}
            onChange={(e) => setResultFilter(e.target.value as any)}
            className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8]"
          >
            <option value="all">All Results</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              <th className="text-left p-3">Audit ID</th>
              <th className="text-left p-3">Time</th>
              <th className="text-left p-3">Operator</th>
              <th className="text-left p-3">Action</th>
              <th className="text-left p-3">Target</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Client IP</th>
              <th className="text-left p-3">Context</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8 text-center text-xs text-[var(--muted)]">
                  No matching audit logs found.
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => {
                const isSuccess = log.result === "success";

                return (
                  <tr
                    key={log.audit_id}
                    className="border-t border-white/6 transition-colors hover:bg-white/[0.025]"
                  >
                    <td className="p-3">
                      <code className="text-xs text-[var(--muted)]">{log.audit_id}</code>
                    </td>
                    <td className="p-3 text-xs text-[var(--muted)]">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <div className="font-medium text-[#cbd6e9]">{log.who.username}</div>
                      {log.who.email && (
                        <div className="text-[10px] text-[var(--muted)]">{log.who.email}</div>
                      )}
                    </td>
                    <td className="p-3">
                      <span className="rounded bg-white/5 border border-white/10 px-2 py-0.5 text-xs font-mono">
                        {log.what.action}
                      </span>
                    </td>
                    <td className="p-3">
                      <code className="text-xs text-[#c4ddff]">{log.what.target}</code>
                    </td>
                    <td className="p-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                          isSuccess
                            ? "bg-emerald-500/10 border border-emerald-500/25 text-[var(--success)]"
                            : "bg-red-500/10 border border-red-500/25 text-[var(--danger)]"
                        }`}
                        title={log.error_message}
                      >
                        {isSuccess ? "Success" : "Failed"}
                      </span>
                      {log.error_message && (
                        <div className="mt-1 text-[10px] text-[var(--danger)] leading-relaxed max-w-[200px] truncate" title={log.error_message}>
                          {log.error_message}
                        </div>
                      )}
                    </td>
                    <td className="p-3 text-xs font-mono text-[var(--muted)]">
                      {log.context?.ip || "-"}
                    </td>
                    <td className="p-3 text-xs text-[var(--muted)] truncate max-w-[150px]" title={log.context?.userAgent}>
                      {log.context?.userAgent || "-"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
