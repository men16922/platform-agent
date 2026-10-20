import { CloudHealth } from "@/lib/mock-data";
import { ProviderLogo } from "@/components/provider-logo";

const providerConfig = {
  aws: { name: "AWS", color: "#FF9900" },
  gcp: { name: "Google Cloud", color: "#8AB4F8" },
  azure: { name: "Microsoft Azure", color: "#00A4EF" },
  onprem: { name: "On-Premise", color: "#69D3A7" },
};

const statusColors = {
  healthy: "text-[var(--success)]",
  degraded: "text-[var(--warning)]",
  down: "text-[var(--danger)]",
};

export function StatusCard({ health }: { health: CloudHealth }) {
  const config = providerConfig[health.provider];
  const statusColor = statusColors[health.status];

  return (
    <div className="surface group relative overflow-hidden p-4 transition-transform duration-200 hover:-translate-y-0.5">
      <div className="absolute inset-x-0 top-0 h-px opacity-80" style={{ backgroundColor: config.color }} />
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-11 shrink-0 items-center justify-center rounded-lg bg-white p-1"><ProviderLogo provider={health.provider} /></span>
          <span className="font-semibold tracking-tight">{config.name}</span>
        </div>
        <span className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] ${statusColor}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />{health.status}
        </span>
      </div>
      <div className="space-y-2 text-xs text-[var(--muted)]">
        <div className="flex justify-between">
          <span>Active Incidents</span>
          <span className={`font-semibold ${health.active_incidents > 0 ? "text-[var(--warning)]" : "text-[var(--foreground)]"}`}>
            {health.active_incidents}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Last Deploy</span>
          <span>{new Date(health.last_deployment).toLocaleTimeString()}</span>
        </div>
      </div>
      <p className="mt-4 text-[10px] text-[var(--muted)]">Last reported: {health.last_check}</p>
    </div>
  );
}
