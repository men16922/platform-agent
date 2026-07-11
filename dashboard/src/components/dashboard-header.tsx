"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signIn, signOut } from "next-auth/react";

const pageLabels: Record<string, string> = {
  "/": "Overview",
  "/incidents": "Incidents",
  "/deployments": "Deployments",
  "/agents": "Agent activity",
};

const mobileNavItems = [
  { href: "/", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  { href: "/deployments", label: "Deployments" },
  { href: "/agents", label: "Agents" },
];

export function DashboardHeader() {
  const pathname = usePathname();
  const label = pageLabels[pathname] ?? "Platform Agent";
  const { data: session, status } = useSession();

  return (
    <header className="mb-7 border-b border-white/6 pb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#8ab4f8]/35 bg-[var(--accent-soft)] text-sm text-[#c4ddff] md:hidden">✦</div>
          <div><p className="text-xs text-[var(--muted)]">Platform Agent / <span className="text-[#c9d4e7]">{label}</span></p><p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--muted)]">Production workspace</p></div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-lg border border-white/7 bg-white/[0.025] px-3 py-2 text-xs text-[var(--muted)] sm:flex"><span className="pulse-dot" />All systems nominal</div>
          <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/8 bg-white/[0.025] text-sm text-[var(--muted)] transition-colors hover:text-white" aria-label="Notifications">⌁</button>
          <UserAvatar session={session} status={status} />
        </div>
      </div>
      <nav aria-label="Primary navigation" className="mt-4 grid grid-cols-4 gap-1 rounded-lg border border-white/8 bg-white/[0.025] p-1 md:hidden">
        {mobileNavItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-md px-2 py-2 text-center text-[11px] font-medium transition-colors ${
                isActive ? "bg-[var(--accent-soft)] text-white" : "text-[var(--muted)] hover:bg-white/5 hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function UserAvatar({ session, status }: { session: any; status: string }) {
  if (status === "loading") {
    return (
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 animate-pulse" />
    );
  }

  if (!session?.user) {
    return (
      <button
        onClick={() => signIn("github")}
        className="flex h-8 items-center gap-2 rounded-lg border border-white/8 bg-white/[0.025] px-3 text-[11px] font-medium text-[var(--muted)] transition-colors hover:text-white"
      >
        Sign in
      </button>
    );
  }

  const user = session.user;
  const role = (user as any).role ?? "viewer";
  const roleBadge: Record<string, string> = {
    admin: "border-red-400/40 text-[#ffb4ae]",
    operator: "border-emerald-400/40 text-[var(--success)]",
    viewer: "border-white/20 text-[var(--muted)]",
  };

  return (
    <div className="flex items-center gap-2">
      <span className={`hidden rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider sm:inline ${roleBadge[role] ?? roleBadge.viewer}`}>
        {role}
      </span>
      {user.image ? (
        <button onClick={() => signOut()} title={`${user.name ?? user.email} (${role}) — Click to sign out`}>
          <img
            src={user.image}
            alt={user.name ?? "User"}
            className="h-8 w-8 rounded-full border border-white/20 transition-opacity hover:opacity-80"
          />
        </button>
      ) : (
        <button
          onClick={() => signOut()}
          title={`${user.name ?? user.email} (${role}) — Click to sign out`}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#8ab4f8] to-[#4285f4] text-[10px] font-bold text-[#202124] transition-opacity hover:opacity-80"
        >
          {(user.name ?? user.email ?? "U").charAt(0).toUpperCase()}
        </button>
      )}
    </div>
  );
}
