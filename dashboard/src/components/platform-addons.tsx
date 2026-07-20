import { getStackLinks } from "@/lib/stack-links";

// Platform add-ons rendered on the Provisioning screen: they are provisioning
// OUTPUT (stood up by infra/onprem/addons Terraform), so we show the IaC
// contract — pinned chart + namespace — next to a link into each UI.
export function PlatformAddons() {
  const stacks = getStackLinks();
  if (stacks.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="eyebrow">Platform add-ons</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Cluster tooling provisioned by <code className="text-[#a9c7ff]">infra/onprem/addons</code> · Terraform ·
            open each console below
          </p>
        </div>
        <span className="rounded-md border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-[10px] font-semibold text-[#cad5e7]">
          {stacks.length} provisioned
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {stacks.map((s) => (
          <a
            key={s.key}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="surface group relative flex flex-col gap-3 overflow-hidden p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_50px_rgba(0,0,0,0.28)]"
          >
            <span className="absolute bottom-0 left-0 top-0 w-0.5" style={{ background: s.accent }} />
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: s.accent }} />
                <span className="font-medium text-[#e6edf7]">{s.label}</span>
              </div>
              <span className="text-[11px] text-[var(--muted)] opacity-40 transition-opacity group-hover:opacity-100">
                Open ↗
              </span>
            </div>
            <span
              className="w-fit rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
              style={{ color: s.accent, borderColor: `${s.accent}55`, background: `${s.accent}12` }}
            >
              {s.category}
            </span>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--muted)]">
              <span className="font-mono text-[#cbd6e9]">{s.chart}</span>
              <span className="font-mono">ns/{s.namespace}</span>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}
