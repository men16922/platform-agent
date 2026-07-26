"use client";

import { useEffect, useState } from "react";
import {
  ISOLATION_AXES,
  summarizeByEnv,
  showsSyncAxis,
  type NormalizedAddonStatus,
  type TenancyPosture,
} from "@/lib/platform-registry";

/**
 * Tenant/env switcher over pushed add-on status.
 *
 * The data arrives by push from each cluster's own agent; this component never
 * causes a cluster to be read, which is what keeps the hub free of spoke
 * credentials. The consequence for the UI is that *absence is the interesting
 * case*, and three different absences must not look alike:
 *
 *   hub unreachable      -> we know nothing, and we know that we know nothing
 *   never pushed         -> a declared env nobody is watching
 *   pushed, then silence -> an agent that died; rows read UNKNOWN, not "healthy"
 *
 * A switcher that showed only what it received would be at its emptiest and
 * calmest exactly when a cluster goes dark.
 */

interface StatusFeed {
  statuses: NormalizedAddonStatus[];
  freshness: Array<{ identity: string; cluster: string; age_sec: number; stale: boolean }>;
  tenancy: Record<string, TenancyPosture>;
  missing: string[];
  staleAfterSec: number;
  connected: boolean;
}

const EMPTY: StatusFeed = {
  statuses: [],
  freshness: [],
  tenancy: {},
  missing: [],
  staleAfterSec: 0,
  connected: false,
};

function axisColor(state: string): string {
  switch (state) {
    case "healthy":
    case "synced":
      return "#3fb950";
    case "progressing":
      return "#d29922";
    case "drifted":
    case "degraded":
    case "missing":
      return "#f85149";
    default:
      // unknown / n⁄a — deliberately grey, never green.
      return "#8b949e";
  }
}

/**
 * The two questions the add-on table cannot answer: is this tenant's boundary
 * actually in place, and how much of its quota is gone.
 *
 * Tri-state on purpose. An axis the agent could not read renders grey with a
 * question mark, never red and never green — "we could not look" is a third
 * fact, and collapsing it either way is how a status screen starts lying.
 */
function IsolationPanel({ posture }: { posture: TenancyPosture }) {
  const adoptionGap =
    posture.adopted_namespaces !== null &&
    posture.adopted_namespaces !== posture.declared_namespaces;

  return (
    <div className="surface space-y-4 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11px] font-semibold text-[#cbd6e9]">격리 상태</p>
        <span className="text-[10px] text-[var(--muted)]">
          네임스페이스 {posture.adopted_namespaces ?? "?"} / {posture.declared_namespaces} 적용됨
        </span>
      </div>

      {/* The gap between "labelled with a tenant" and "owned by that tenant" is
          the exact failure this platform hit twice: a quota that binds nothing
          while every view reads correct. It gets its own line, not a colour. */}
      {adoptionGap && (
        <p className="rounded border border-[#d2992233] bg-[#d2992212] px-3 py-2 text-[10px] text-[#d29922]">
          선언된 네임스페이스 중 일부가 아직 테넌트에 편입되지 않았습니다 — 그 네임스페이스에는
          쿼터가 적용되지 않습니다.
        </p>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ISOLATION_AXES.map((axis) => {
          const state = posture.isolation[axis.key] ?? null;
          const color = state === true ? "#3fb950" : state === false ? "#f85149" : "#8b949e";
          const mark = state === true ? "적용" : state === false ? "없음" : "확인 불가";
          return (
            <div
              key={axis.key}
              className="rounded-md border border-white/8 bg-white/[0.02] px-3 py-2"
              title={axis.asks}
            >
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
                <span className="text-[11px] font-medium text-[#e6edf7]">{axis.label}</span>
              </div>
              <p className="mt-1 text-[10px]" style={{ color }}>
                {mark}
              </p>
            </div>
          );
        })}
      </div>

      {Object.keys(posture.quota_hard).length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-[var(--muted)]">쿼터 사용량</p>
          {Object.entries(posture.quota_hard).map(([key, hard]) => {
            const used = posture.quota_used[key];
            return (
              <div key={key} className="flex items-baseline justify-between text-[11px]">
                <span className="font-mono text-[var(--muted)]">{key}</span>
                <span className="font-mono text-[#cbd6e9]">
                  {/* Raw strings, no unit maths: a converted number that is wrong
                      looks exactly as authoritative as one that is right. */}
                  {used ?? "?"} <span className="text-[var(--muted)]">/ {hard}</span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function PlatformTenantSwitcher() {
  const [feed, setFeed] = useState<StatusFeed>(EMPTY);
  const [selected, setSelected] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch("/api/dashboard/platform/status", { cache: "no-store" });
        const body: StatusFeed = await res.json();
        if (!cancelled) setFeed(body);
      } catch {
        if (!cancelled) setFeed(EMPTY);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    };
    load();
    // Polling the HUB (not a cluster) — the hub is the only thing this page is
    // allowed to talk to, and it is cheap and local.
    const timer = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const groups = summarizeByEnv(feed.statuses);
  const staleIdentities = new Set(feed.freshness.filter((f) => f.stale).map((f) => f.identity));
  const active = selected ?? (groups.length > 0 ? `${groups[0].tenant}/${groups[0].env}` : null);
  const rows = feed.statuses.filter((s) => `${s.tenant}/${s.env}` === active);

  if (!loaded) return null;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="eyebrow">Tenants &amp; environments</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Two axes per add-on — <span className="text-[#cbd6e9]">sync</span> (matches git) and{" "}
            <span className="text-[#cbd6e9]">health</span> (actually working) · pushed by each
            cluster&apos;s own agent
          </p>
        </div>
        {feed.connected ? (
          <span className="rounded-md border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-[10px] font-semibold text-[#cad5e7]">
            {groups.length} env{groups.length === 1 ? "" : "s"} reporting
          </span>
        ) : (
          <span className="rounded-md border border-[#f8514933] bg-[#f8514912] px-2.5 py-1.5 text-[10px] font-semibold text-[#f85149]">
            hub unreachable
          </span>
        )}
      </div>

      {!feed.connected && (
        <p className="surface p-4 text-xs text-[var(--muted)]">
          No status hub in reach, so this view knows nothing about any cluster — which is not the
          same as every cluster being fine. Start the local hub
          (<code className="text-[#a9c7ff]">make dev-up</code>) or point{" "}
          <code className="text-[#a9c7ff]">LOCAL_DEPLOY_API_URL</code> at it.
        </p>
      )}

      {feed.connected && groups.length === 0 && (
        <p className="surface p-4 text-xs text-[var(--muted)]">
          The hub is up and has never been pushed to.
        </p>
      )}

      {groups.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {groups.map((group) => {
            const identity = `${group.tenant}/${group.env}`;
            const stale = staleIdentities.has(identity);
            const isActive = identity === active;
            return (
              <button
                key={identity}
                type="button"
                onClick={() => setSelected(identity)}
                className={`surface flex items-center gap-2.5 px-3 py-2 text-left text-xs transition-all duration-200 ${
                  isActive ? "ring-1 ring-[#4493f8]" : "hover:-translate-y-0.5"
                }`}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background: stale
                      ? "#8b949e"
                      : group.driftCount + group.unhealthyCount > 0
                        ? "#f85149"
                        : "#3fb950",
                  }}
                />
                <span className="font-medium text-[#e6edf7]">{group.tenant}</span>
                <span className="text-[var(--muted)]">/ {group.env}</span>
                {stale ? (
                  <span className="text-[10px] font-semibold text-[#8b949e]">no heartbeat</span>
                ) : (
                  <span className="text-[10px] text-[var(--muted)]">
                    {group.driftCount > 0 && `${group.driftCount} drifted`}
                    {group.driftCount > 0 && group.unhealthyCount > 0 && " · "}
                    {group.unhealthyCount > 0 && `${group.unhealthyCount} unhealthy`}
                    {group.driftCount === 0 && group.unhealthyCount === 0 && `${group.total} ok`}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {active && feed.tenancy[active] && (
        <IsolationPanel posture={feed.tenancy[active]} />
      )}

      {rows.length > 0 && (
        <div className="surface overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
              <tr className="border-b border-white/8">
                <th className="px-4 py-3 font-semibold">Capability</th>
                <th className="px-4 py-3 font-semibold">Backend</th>
                <th className="px-4 py-3 font-semibold">Declared</th>
                <th className="px-4 py-3 font-semibold">Sync</th>
                <th className="px-4 py-3 font-semibold">Health</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.capability}`} className="border-b border-white/5 last:border-0">
                  <td className="px-4 py-3 font-medium text-[#e6edf7]">{row.capability}</td>
                  <td className="px-4 py-3 font-mono text-[#cbd6e9]">{row.backend}</td>
                  <td className="px-4 py-3 font-mono text-[var(--muted)]">
                    {row.desired_version ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {showsSyncAxis(row) ? (
                      <span style={{ color: axisColor(row.sync_state) }}>{row.sync_state}</span>
                    ) : (
                      // Two different reasons the sync axis is absent, and they must
                      // not both render as a bare dash: a managed backend has no sync
                      // concept, while a cluster-scoped capability has one that
                      // belongs to the cluster rather than to this tenant.
                      <span
                        className="text-[var(--muted)]"
                        title={
                          row.native?.scope === "cluster"
                            ? "shared cluster install — one per cluster, not synced per tenant"
                            : "no sync axis for this backend"
                        }
                      >
                        {row.native?.scope === "cluster" ? "shared" : "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span style={{ color: axisColor(row.health_state) }}>{row.health_state}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {feed.missing.length > 0 && (
        <p className="text-[11px] text-[var(--muted)]">
          <span className="text-[#d29922]">Never reported:</span> {feed.missing.join(", ")} — declared
          in the registry with no agent pushing. A cluster nobody is watching looks identical to a
          healthy one from here.
        </p>
      )}
    </section>
  );
}
