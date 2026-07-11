"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";

const baseNavItems = [
  { href: "/", label: "Overview", icon: "⌘" },
  { href: "/incidents", label: "Incidents", icon: "◈" },
  { href: "/deployments", label: "Deployments", icon: "↗" },
  { href: "/agents", label: "Agents", icon: "✦" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  
  const role = (session?.user as any)?.role || "viewer";
  const hasAuditAccess = role === "admin" || role === "operator";

  const navItems = hasAuditAccess
    ? [...baseNavItems, { href: "/audit", label: "Audit Logs", icon: "🛡" }]
    : baseNavItems;

  return (
    <aside className="hidden w-64 shrink-0 border-r border-[var(--card-border)] bg-[#292a2d] md:flex md:flex-col md:min-h-screen">
      <div className="border-b border-[var(--card-border)] px-5 py-6">
        <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl border border-[#8ab4f8]/45 bg-[var(--accent-soft)] text-lg text-[#c4ddff]">✦</div>
        <h1 className="text-base font-semibold tracking-tight">Platform Agent</h1>
        <p className="mt-1 text-xs text-[var(--muted)]">Autonomous cloud operations</p>
      </div>
      <nav className="flex-1 px-3 py-5">
        <p className="eyebrow px-3 pb-2">Workspace</p>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`mb-1 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                isActive
                  ? "bg-[var(--accent-soft)] font-medium text-white shadow-[inset_2px_0_0_var(--accent)]"
                  : "text-[var(--muted)] hover:bg-white/4 hover:text-white"
              }`}
            >
              <span className={`flex h-5 w-5 items-center justify-center text-base ${isActive ? "text-[#c4ddff]" : ""}`}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="m-3 rounded-xl border border-[var(--card-border)] bg-white/[0.025] p-3 text-xs text-[var(--muted)]">
        <div className="flex items-center gap-2 font-medium text-[#dce5f5]"><span className="pulse-dot" />System operational</div>
        <div className="mt-2">4 providers connected</div>
        <div className="mt-1">490 checks passing</div>
      </div>
    </aside>
  );
}
