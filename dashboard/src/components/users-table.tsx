"use client";

import { useState } from "react";
import type { UserRecord } from "@/lib/user-data";
import type { Role } from "@/lib/auth";

interface UsersTableProps {
  initialUsers: UserRecord[];
  currentAdminUsername: string;
}

export function UsersTable({ initialUsers, currentAdminUsername }: UsersTableProps) {
  const [users, setUsers] = useState<UserRecord[]>(initialUsers);
  const [search, setSearch] = useState("");
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const filteredUsers = users.filter((u) => {
    const term = search.toLowerCase();
    return (
      u.username.toLowerCase().includes(term) ||
      (u.name || "").toLowerCase().includes(term) ||
      (u.email || "").toLowerCase().includes(term)
    );
  });

  const handleRoleChange = async (username: string, newRole: Role) => {
    if (username === currentAdminUsername) {
      setErrorMsg("You cannot change your own role to prevent lockout.");
      return;
    }

    setLoadingId(username);
    setErrorMsg(null);
    setSuccessMsg(null);

    const userToUpdate = users.find((u) => u.username === username);
    if (!userToUpdate) return;

    try {
      const res = await fetch("/api/dashboard/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          role: newRole,
          name: userToUpdate.name,
          email: userToUpdate.email,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to update user role");

      setSuccessMsg(`Successfully updated role for ${username} to ${newRole}`);
      
      // Update state
      setUsers(
        users.map((u) => (u.username === username ? { ...u, role: newRole } : u))
      );
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred");
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Notifications */}
      {(errorMsg || successMsg) && (
        <div className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm">
          {errorMsg && (
            <div className="flex-1 text-[var(--danger)] border-red-500/25">
              ⚠️ <strong>Error:</strong> {errorMsg}
            </div>
          )}
          {successMsg && (
            <div className="flex-1 text-[var(--success)] border-emerald-500/25">
              ✓ <strong>Success:</strong> {successMsg}
            </div>
          )}
          <button
            onClick={() => {
              setErrorMsg(null);
              setSuccessMsg(null);
            }}
            className="text-xs text-[var(--muted)] hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="relative max-w-md">
        <input
          type="text"
          placeholder="Search users by username, name, or email..."
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

      {/* Users table */}
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.025] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
            <tr>
              <th className="text-left p-3">Username</th>
              <th className="text-left p-3">Full Name</th>
              <th className="text-left p-3">Email Address</th>
              <th className="text-left p-3">Role Type</th>
              <th className="text-right p-3">Actions / Update Role</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-8 text-center text-xs text-[var(--muted)]">
                  No matching users found.
                </td>
              </tr>
            ) : (
              filteredUsers.map((u) => {
                const isPending = loadingId === u.username;
                const isSelf = u.username === currentAdminUsername;

                return (
                  <tr
                    key={u.username}
                    className="border-t border-white/6 transition-colors hover:bg-white/[0.025]"
                  >
                    <td className="p-3 font-semibold text-[#cbd6e9]">
                      @{u.username}
                      {isSelf && (
                        <span className="ml-2 rounded bg-[#8ab4f8]/10 border border-[#8ab4f8]/30 px-1.5 py-0.2 text-[8px] text-[#c4ddff] font-normal uppercase tracking-wider">
                          You
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-[var(--muted)]">{u.name || "-"}</td>
                    <td className="p-3 text-[var(--muted)]">{u.email || "-"}</td>
                    <td className="p-3">
                      <span
                        className={`inline-flex rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                          u.role === "admin"
                            ? "border-red-400/40 text-[#ffb4ae] bg-red-950/20"
                            : u.role === "operator"
                              ? "border-emerald-400/40 text-[var(--success)] bg-emerald-950/20"
                              : "border-white/20 text-[var(--muted)] bg-white/5"
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <select
                        disabled={isPending || isSelf}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.username, e.target.value as Role)}
                        className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-xs text-[#cbd6e9] focus:outline-none focus:border-[#8ab4f8] disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="operator">Operator</option>
                        <option value="admin">Admin</option>
                      </select>
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
