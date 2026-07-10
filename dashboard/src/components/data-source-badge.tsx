import type { IncidentDataSource } from "@/lib/incident-data";

const SOURCE_STYLES: Record<IncidentDataSource, string> = {
  "aws-live": "border-emerald-400/30 bg-emerald-400/10 text-[var(--success)]",
  demo: "border-amber-300/30 bg-amber-300/10 text-[var(--warning)]",
  "demo-fallback": "border-red-300/35 bg-red-300/10 text-[#ffb4ae]",
};

const SOURCE_LABELS: Record<IncidentDataSource, string> = {
  "aws-live": "LIVE · AWS",
  demo: "DEMO DATA",
  "demo-fallback": "DEMO FALLBACK",
};

export function DataSourceBadge({ source }: { source: IncidentDataSource }) {
  return (
    <span className={`rounded-md border px-2 py-1 text-[10px] font-bold tracking-[0.1em] ${SOURCE_STYLES[source]}`}>
      {SOURCE_LABELS[source]}
    </span>
  );
}
