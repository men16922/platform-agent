/**
 * Platform registry types + normalized add-on status (dashboard side).
 *
 * Phase 0 of docs/plans/2026-07-21-multi-tenant-env-addons.md. This is the TS
 * half of the shared contract — the Python loader
 * (src/agents/platform/registry.py) owns reading the YAML; the dashboard
 * consumes already-normalized status pushed to the control plane.
 *
 * Deliberately NOT a YAML reader: status collection is a **push** model (each
 * cluster's in-cluster agent pushes its own status) precisely so the hub holds
 * zero spoke read credentials. A dashboard that parsed the registry and polled
 * clusters itself would reintroduce the cross-tenant credential concentration
 * the design exists to avoid.
 */

/**
 * Does the cluster match the declared desired state?
 * `n/a` = managed backend with no git-sync concept (see `applicable`).
 */
export type SyncState = "synced" | "drifted" | "n/a" | "unknown";

/** Is the thing actually working? */
export type HealthState =
  | "healthy"
  | "progressing"
  | "degraded"
  | "missing"
  | "unknown";

/**
 * Two orthogonal axes, never one enum: "drifted from git" and "unhealthy" are
 * different facts needing different responses. `OutOfSync + Healthy` is drift;
 * `Synced + Degraded` is an app problem.
 */
export interface NormalizedAddonStatus {
  tenant: string;
  env: string;
  capability: string;
  backend: string;
  sync_state: SyncState;
  health_state: HealthState;
  desired_version?: string;
  /** False when the sync axis is meaningless for this backend (managed). */
  applicable: boolean;
  /** Raw backend payload, so a UI can explain "why" without modelling every engine. */
  native?: Record<string, unknown>;
}

/**
 * Is the tenant's boundary actually in place, and how full is it?
 *
 * Pushed by the spoke agent alongside add-on status — the dashboard never reads a
 * cluster, which is what keeps the control plane free of spoke credentials.
 *
 * Every axis is tri-state: true / false / **null = could not look**. Rendering
 * "not isolated" when the agent merely lacked permission causes the same panic as
 * a real breach; rendering green in that case is worse.
 */
export interface TenancyPosture {
  adopted_namespaces: number | null;
  declared_namespaces: number;
  quota_hard: Record<string, string>;
  quota_used: Record<string, string>;
  isolation: Record<string, boolean | null>;
  // Everything below arrives from a spoke agent that may be OLDER than this UI —
  // during any rolling upgrade the hub serves reports written by both versions.
  // A TypeScript type is a compile-time claim about data that crossed a network,
  // so these are optional and every read site has a fallback. Learned at runtime:
  // the non-optional version crashed the page the moment a pre-upgrade agent
  // pushed.
  /** soft | vcluster | dedicated */
  tier?: string;
  /** What a scoped credential is issued for: "tenant" or "env". */
  credential_scope?: string;
  namespaces?: string[];
}

/**
 * What each tier actually separates — and what it does not.
 *
 * A green isolation row means something very different on a shared control plane
 * than on a dedicated cluster, and nothing on the screen told the reader which
 * one they were looking at. The non-guarantee is stated next to the guarantee on
 * purpose: a boundary described only by what it protects gets over-trusted.
 */
export const TIER_MEANING: Record<
  string,
  { label: string; separates: string; shares: string; notCovered: string }
> = {
  soft: {
    label: "Soft · namespace-level",
    separates: "namespaces, quota, network policy, RBAC, pod security",
    shares: "control plane, nodes, CRDs, cluster-scoped operators",
    notCovered: "node CPU/disk-IO starvation — API objects are bounded, the kernel is not",
  },
  vcluster: {
    label: "vCluster · virtual control plane",
    separates: "API server, CRDs, RBAC — per tenant",
    shares: "nodes",
    notCovered: "node-level resource contention",
  },
  dedicated: {
    label: "Dedicated · cluster per tenant",
    separates: "everything, including nodes",
    shares: "nothing",
    notCovered: "cost — this is the expensive tier",
  },
};

/** The four things a platform engineer checks before trusting a boundary. */
export const ISOLATION_AXES: Array<{ key: string; label: string; asks: string }> = [
  { key: "quota", label: "Quota", asks: "Can one team starve the others?" },
  { key: "network", label: "Network", asks: "Can another tenant reach these namespaces?" },
  { key: "rbac", label: "RBAC", asks: "Can the agent touch another tenant?" },
  { key: "pod_security", label: "Pod security", asks: "Can a workload here run as root?" },
];

/** Drift is a sync-axis fact — never infer it from health. */
export function isDrifted(status: NormalizedAddonStatus): boolean {
  return status.sync_state === "drifted";
}

/**
 * Whether the sync axis should be rendered at all.
 *
 * A managed backend must show "—" rather than a fabricated "Synced" badge;
 * showing a fake green is worse than showing nothing.
 */
export function showsSyncAxis(status: NormalizedAddonStatus): boolean {
  return status.applicable && status.sync_state !== "n/a";
}

// REMOVED 2026-08-08: `credentialScope` and `namespaceFor`, plus the tenant/env
// types that existed only to type them.
//
// Both were TypeScript re-implementations of rules that live in Python and are
// load-bearing there: `IsolationTier.credential_scope` decides the credential
// boundary unit (registry.py), and `Tenant.namespace_for` names the namespace a
// tenant's add-on is rendered into (delivery.py, and the scope broker mints
// against it). Neither TS copy had a single caller — measured across the whole
// dashboard — and nothing produced a `PlatformTenant` to pass them.
//
// Deleted rather than kept "for later" because the risk is not the dead code, it
// is the second source of truth: a duplicated authorization rule that nothing
// exercises will drift from the live one silently, and whoever wires it up later
// will trust it. The dashboard gets tenancy from pushed status
// (`NormalizedAddonStatus`), not by re-deriving the registry — which is the
// design note at the top of this file.
//
// NEXT_PLAN required "실 레지스트리 대조" before deleting; that is what this was.

/**
 * Group statuses by tenant/env for the switcher, keeping drift visible.
 *
 * `driftCount` counts only the sync axis so a degraded-but-synced add-on does
 * not inflate the drift badge.
 */
export function summarizeByEnv(
  statuses: NormalizedAddonStatus[],
): Array<{
  tenant: string;
  env: string;
  total: number;
  driftCount: number;
  unhealthyCount: number;
  unknownCount: number;
}> {
  const groups = new Map<string, NormalizedAddonStatus[]>();
  for (const status of statuses) {
    const key = `${status.tenant}/${status.env}`;
    const bucket = groups.get(key);
    if (bucket) bucket.push(status);
    else groups.set(key, [status]);
  }
  return [...groups.entries()]
    .map(([key, group]) => {
      const [tenant, env] = key.split("/");
      return {
        tenant,
        env,
        total: group.length,
        driftCount: group.filter(isDrifted).length,
        unhealthyCount: group.filter(
          (s) => s.health_state === "degraded" || s.health_state === "missing",
        ).length,
        // A dead push agent surfaces here rather than silently reading healthy.
        unknownCount: group.filter((s) => s.health_state === "unknown").length,
      };
    })
    .sort((a, b) => a.tenant.localeCompare(b.tenant) || a.env.localeCompare(b.env));
}
