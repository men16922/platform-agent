import type { NormalizedAddonStatus } from "@/lib/platform-registry";

export const dynamic = "force-dynamic";

// The hub is the local control plane the spoke agents push to. The dashboard
// READS it — it never talks to a cluster itself, which is what lets the whole
// system hold zero spoke credentials (src/agents/platform/collector.py).
const HUB = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export interface PlatformStatusFeed {
  statuses: NormalizedAddonStatus[];
  freshness: Array<{ identity: string; cluster: string; age_sec: number; stale: boolean }>;
  /** Declared tenant/envs the hub has never heard from at all. */
  missing: string[];
  staleAfterSec: number;
  /** False when the hub is unreachable — distinct from "reachable and empty". */
  connected: boolean;
}

export async function GET() {
  const empty: PlatformStatusFeed = {
    statuses: [],
    freshness: [],
    missing: [],
    staleAfterSec: 0,
    connected: false,
  };

  try {
    const res = await fetch(`${HUB}/api/platform/status`, { cache: "no-store" });
    if (!res.ok) return Response.json(empty);
    const body = await res.json();
    return Response.json({
      statuses: body.statuses ?? [],
      freshness: body.freshness ?? [],
      missing: body.missing ?? [],
      staleAfterSec: body.stale_after_sec ?? 0,
      connected: true,
    } satisfies PlatformStatusFeed);
  } catch {
    // Hub down, or the dashboard is running on Vercel with no local hub in reach.
    // `connected: false` keeps that separable from "the hub knows of nothing",
    // because the two call for opposite reactions from whoever is looking.
    return Response.json(empty);
  }
}
