/**
 * Tenant visibility — Phase 3③ (viewer visibility limits).
 *
 * Phase 3① made the credential the boundary on the *write* side: a remediation
 * action cannot touch a tenant it was not minted for. This is the same boundary
 * on the *read* side, which had none at all — `/api/dashboard/platform/status`
 * returned every tenant's isolation posture, namespaces and quotas to anyone who
 * asked, unauthenticated. On a single-tenant dashboard that is a demo
 * convenience; on a fleet view it is one tenant reading another's topology.
 *
 * Why this lives in a module the route calls rather than in the proxy:
 * Next.js' own guidance is that proxy (formerly middleware) runs before the app
 * and "should not be your only line of defense" — authorization belongs as close
 * to the data as possible. That happens to match the rule this repo already
 * paid for elsewhere: one implementation that every caller invokes, because a
 * check re-derived per route is a check the fourth route forgets.
 *
 * Fail-closed, and the three answers are kept distinct:
 *
 *   - no session          -> RESTRICTED (sign in), not "no tenants exist"
 *   - session, no grants  -> RESTRICTED, same reason
 *   - admin               -> everything
 *
 * The distinction matters for the same reason `connected: false` is not `[]`
 * elsewhere in this dashboard: an empty fleet and a fleet you may not see call
 * for opposite reactions from whoever is looking at the screen.
 */

import type { Role } from "@/lib/auth";

/** What a caller is allowed to see. `null` tenants = every tenant (admin). */
export interface Visibility {
  /** Tenant names this caller may see, or null for "all of them". */
  tenants: string[] | null;
  /** True when the caller is shown nothing *because of* authorization. */
  restricted: boolean;
  /** Why, in a form the UI can render honestly. */
  reason: "unauthenticated" | "no-grants" | "granted" | "admin";
}

export interface VisibilityInput {
  role: Role | null;
  /** Tenants granted to this user. Absent/empty means none for non-admins. */
  tenants?: string[] | null;
}

export const RESTRICTED: Visibility = {
  tenants: [],
  restricted: true,
  reason: "unauthenticated",
};

/**
 * Resolve what this caller may see.
 *
 * Admins see everything — they are the ones who assign grants, so gating them on
 * grants would make the system unadministrable after the first mistake.
 * Everyone else sees exactly what they were granted, and the default is nothing.
 */
export function resolveVisibility(input: VisibilityInput | null): Visibility {
  if (!input?.role) return RESTRICTED;

  if (input.role === "admin") {
    return { tenants: null, restricted: false, reason: "admin" };
  }

  const granted = (input.tenants ?? []).filter((t) => t.length > 0);
  if (granted.length === 0) {
    return { tenants: [], restricted: true, reason: "no-grants" };
  }
  return { tenants: granted, restricted: false, reason: "granted" };
}

/** Whether `identity` ("tenant/env") or a bare tenant name is visible. */
export function isVisible(visibility: Visibility, identity: string): boolean {
  if (visibility.tenants === null) return true;
  const tenant = identity.split("/")[0];
  return visibility.tenants.includes(tenant);
}

/**
 * Shape of the fleet feed, narrowed to what filtering needs. Kept structural so
 * this module does not have to import the route's own response type and create
 * a cycle.
 */
export interface FleetLike {
  statuses: Array<{ tenant?: string; env?: string }>;
  freshness: Array<{ identity: string }>;
  tenancy: Record<string, unknown>;
  missing: string[];
}

/**
 * Drop everything the caller may not see.
 *
 * Note `missing` is filtered too. It names declared tenant/envs the hub has
 * never heard from — i.e. it leaks the existence of tenants precisely when they
 * have no status to leak, which would otherwise make the one field that reveals
 * the full tenant roster the one field nobody thought to filter.
 */
export function filterFleet<T extends FleetLike>(feed: T, visibility: Visibility): T {
  if (visibility.tenants === null) return feed;

  return {
    ...feed,
    statuses: feed.statuses.filter((s) =>
      isVisible(visibility, `${s.tenant ?? ""}/${s.env ?? ""}`),
    ),
    freshness: feed.freshness.filter((f) => isVisible(visibility, f.identity)),
    tenancy: Object.fromEntries(
      Object.entries(feed.tenancy).filter(([identity]) => isVisible(visibility, identity)),
    ),
    missing: feed.missing.filter((identity) => isVisible(visibility, identity)),
  };
}
