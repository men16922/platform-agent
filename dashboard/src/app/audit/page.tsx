import { auth } from "@/auth";
import { listAuditLogs } from "@/lib/audit-data";
import { AuditLogsTable } from "@/components/audit-logs-table";
import { DataSourceBadge } from "@/components/data-source-badge";
import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Audit Logs",
  description: "Tamper-resistant database mutation record",
};

export default async function AuditPage() {
  const session = await auth();

  if (!session?.user) {
    return <AccessDenied reason="authentication_required" />;
  }

  const role = (session.user as any).role || "viewer";
  if (role !== "admin" && role !== "operator") {
    return <AccessDenied reason="insufficient_privileges" role={role} />;
  }

  const logs = await listAuditLogs();
  const source = process.env.DASHBOARD_DATA_SOURCE === "aws" ? ("aws-live" as const) : ("demo" as const);

  return (
    <div className="mx-auto max-w-[1800px] space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="eyebrow mb-3">Compliance & security registry</p>
          <h2 className="text-3xl font-semibold tracking-tight">Audit Logs</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Tamper-resistant record of all system mutations and approvals (90-day retention TTL)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-[var(--success)]">
            🔒 Audit Active
          </span>
          <DataSourceBadge source={source} />
        </div>
      </div>

      <AuditLogsTable initialLogs={logs} />
    </div>
  );
}

function AccessDenied({
  reason,
  role,
}: {
  reason: "authentication_required" | "insufficient_privileges";
  role?: string;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center px-4">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-red-500/35 bg-red-500/10 text-xl text-[#ffb4ae]">
        ⚠️
      </div>
      <h3 className="text-lg font-semibold text-[#cbd6e9]">Access Denied</h3>
      <p className="mt-2 max-w-md text-xs leading-relaxed text-[var(--muted)]">
        {reason === "authentication_required"
          ? "Please sign in to view the secure audit registry records."
          : `Your current role (${role}) does not have permission to view the audit registry. Admin or Operator privileges are required.`}
      </p>
      <div className="mt-6 flex gap-3">
        <Link
          href="/"
          className="rounded-lg border border-white/10 bg-white/[0.025] px-4 py-2 text-xs font-semibold text-[#cbd6e9] hover:bg-white/5 hover:text-white transition-all"
        >
          Return to Overview
        </Link>
      </div>
    </div>
  );
}
