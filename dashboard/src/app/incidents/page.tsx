import { IncidentRow } from "@/components/incident-row";
import { mockIncidents } from "@/lib/mock-data";

export default function IncidentsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <div>
        <p className="eyebrow mb-3">Autonomous response record</p>
        <h2 className="text-3xl font-semibold tracking-tight">Incidents</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          Incident timeline across all cloud providers — detected, analyzed, and remediated by AI agents
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <IncidentStat label="P1 critical" value={mockIncidents.filter(i => i.severity === "P1").length} tone="text-[var(--danger)]" />
        <IncidentStat label="P2 elevated" value={mockIncidents.filter(i => i.severity === "P2").length} tone="text-[var(--warning)]" />
        <IncidentStat label="P3 advisory" value={mockIncidents.filter(i => i.severity === "P3").length} tone="text-[#a79dff]" />
        <IncidentStat label="Resolved" value={mockIncidents.filter(i => i.resolved).length} tone="text-[var(--success)]" />
        <IncidentStat label="Needs review" value={mockIncidents.filter(i => !i.resolved).length} tone="text-[var(--warning)]" />
      </div>

      <div className="flex items-center justify-between"><p className="eyebrow">Latest events</p><div className="flex gap-2"><span className="rounded-md border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-[10px] font-semibold text-[#cad5e7]">All providers</span><span className="rounded-md border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-[10px] font-semibold text-[var(--muted)]">Last 24h</span></div></div>
      <div className="space-y-3">
        {mockIncidents.map((incident) => (
          <IncidentRow key={incident.id} incident={incident} />
        ))}
      </div>
    </div>
  );
}

function IncidentStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <div className="surface p-4"><p className="eyebrow">{label}</p><p className={`mt-3 text-2xl font-semibold ${tone}`}>{value}</p></div>;
}
