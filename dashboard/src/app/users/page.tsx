import { auth } from "@/auth";
import { listUserRecords } from "@/lib/user-data";
import { UsersTable } from "@/components/users-table";
import { DataSourceBadge } from "@/components/data-source-badge";
import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "User Management",
  description: "Manage system operator and admin authorization overrides",
};

export default async function UsersPage() {
  const session = await auth();

  if (!session?.user) {
    return <AccessDenied reason="authentication_required" />;
  }

  const role = (session.user as any).role || "viewer";
  if (role !== "admin") {
    return <AccessDenied reason="insufficient_privileges" role={role} />;
  }

  const users = await listUserRecords();

  return (
    <div className="mx-auto max-w-[1800px] space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="eyebrow mb-3">Identity & access management</p>
          <h2 className="text-3xl font-semibold tracking-tight">User Management</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Manage developer roles and authorization overrides stored in DynamoDB
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg border border-red-400/25 bg-red-400/10 px-3 py-1.5 text-xs font-semibold text-[#ffb4ae]">
            🛡 Admin Mode
          </span>
          <DataSourceBadge source="aws-live" />
        </div>
      </div>

      <UsersTable initialUsers={users} currentAdminUsername={session.user.username ?? ""} />
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
        🔒
      </div>
      <h3 className="text-lg font-semibold text-[#cbd6e9]">Access Denied</h3>
      <p className="mt-2 max-w-md text-xs leading-relaxed text-[var(--muted)]">
        {reason === "authentication_required"
          ? "Please sign in to access identity management console."
          : `Your current role (${role}) does not have administrative privileges to manage user roles. Only Admin role is authorized.`}
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
