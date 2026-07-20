"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { getStackLinks } from "@/lib/stack-links";

// Ordered by the platform workflow: drive the agent → provision infra → deploy
// apps → respond to incidents.
const baseNavItems = [
  { href: "/", label: "Overview", icon: "⌘" },
  { href: "/agents", label: "Agents", icon: "✦" },
  { href: "/provisioning", label: "Provisioning", icon: "⬡" },
  { href: "/deployments", label: "Deployments", icon: "↗" },
  { href: "/history", label: "History", icon: "🕑" },
  { href: "/incidents", label: "Incidents", icon: "◈" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  
  const role = (session?.user as any)?.role || "viewer";

  const navItems = [...baseNavItems];
  if (role === "admin" || role === "operator") {
    navItems.push({ href: "/audit", label: "Audit Logs", icon: "🛡" });
  }
  if (role === "admin") {
    navItems.push({ href: "/users", label: "Users", icon: "👥" });
  }

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

        {/* Platform stacks — the add-on cluster tooling (env-driven URLs, open in
            a new tab). These are external UIs, not dashboard routes. */}
        <p className="eyebrow px-3 pb-2 pt-5">Platform stacks</p>
        {getStackLinks().map((link) => (
          <a
            key={link.key}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            title={link.hint}
            className="group mb-1 flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-[var(--muted)] transition-all hover:bg-white/4 hover:text-white"
          >
            <span className="flex h-5 w-5 items-center justify-center text-base">{link.icon}</span>
            <span className="flex-1">{link.label}</span>
            <span className="text-[10px] opacity-40 transition-opacity group-hover:opacity-100">↗</span>
          </a>
        ))}
      </nav>
      <div className="m-3 rounded-xl border border-[var(--card-border)] bg-white/[0.025] p-3 text-xs text-[var(--muted)]">
        <div className="flex items-center gap-2 font-medium text-[#dce5f5]"><span className="pulse-dot" />System operational</div>
        <div className="mt-2">4 providers connected</div>
        <div className="mt-1">490 checks passing</div>
      </div>
    </aside>
  );
}
