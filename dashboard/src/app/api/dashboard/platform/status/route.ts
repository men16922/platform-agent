import { auth } from "@/auth";
import type { Role } from "@/lib/auth";
import type { NormalizedAddonStatus, TenancyPosture } from "@/lib/platform-registry";
import { getUserRecord } from "@/lib/user-data";
import { filterFleet, RESTRICTED, resolveVisibility } from "@/lib/visibility";

export const dynamic = "force-dynamic";

// The hub is the local control plane the spoke agents push to. The dashboard
// READS it — it never talks to a cluster itself, which is what lets the whole
// system hold zero spoke credentials (src/agents/platform/collector.py).
const HUB = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export interface PlatformStatusFeed {
  statuses: NormalizedAddonStatus[];
  freshness: Array<{ identity: string; cluster: string; age_sec: number; stale: boolean }>;
  /** identity ("tenant/env") -> isolation posture. Absent when never pushed. */
  tenancy: Record<string, TenancyPosture>;
  /** Declared tenant/envs the hub has never heard from at all. */
  missing: string[];
  staleAfterSec: number;
  /** False when the hub is unreachable — distinct from "reachable and empty". */
  connected: boolean;
  /**
   * True when rows were withheld by authorization rather than absent (Phase 3③).
   * Kept separate from `connected` and from an empty fleet: "you may not see
   * this" and "there is nothing here" call for opposite reactions.
   */
  restricted: boolean;
}

/**
 * Resolve the caller's tenant grants. Read-side counterpart of the token
 * broker: the grants come from the stored user record, never from anything the
 * caller sends.
 */
async function callerVisibility() {
  const session = await auth();
  const username = session?.user?.username;
  if (!username) return RESTRICTED;

  const role = ((session.user as { role?: Role }).role ?? "viewer") as Role;
  // A missing record is not a reason to widen: fall through with no grants.
  const record = await getUserRecord(username).catch(() => null);
  return resolveVisibility({ role, tenants: record?.tenants ?? null });
}

export async function GET() {
  const empty: PlatformStatusFeed = {
    statuses: [],
    freshness: [],
    tenancy: {},
    missing: [],
    staleAfterSec: 0,
    connected: false,
    restricted: false,
  };

  const visibility = await callerVisibility();
  if (visibility.restricted) {
    // Do not call the hub at all — nothing that comes back would be shown, and
    // an unauthenticated caller should not be able to make us fan out.
    return Response.json({ ...empty, restricted: true } satisfies PlatformStatusFeed);
  }

  try {
    const res = await fetch(`${HUB}/api/platform/status`, { cache: "no-store" });
    if (!res.ok) return Response.json(empty);
    const body = await res.json();
    const feed: PlatformStatusFeed = {
      statuses: body.statuses ?? [],
      freshness: body.freshness ?? [],
      tenancy: body.tenancy ?? {},
      missing: body.missing ?? [],
      staleAfterSec: body.stale_after_sec ?? 0,
      connected: true,
      restricted: false,
    };
    return Response.json(filterFleet(feed, visibility));
  } catch {
    // Hub down, or the dashboard is running on Vercel with no local hub in reach.
    // `connected: false` keeps that separable from "the hub knows of nothing",
    // because the two call for opposite reactions from whoever is looking.
    return Response.json(empty);
  }
}
