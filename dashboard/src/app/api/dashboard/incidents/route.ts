import { auth } from "@/auth";
import type { Role } from "@/lib/auth";
import { getIncidentFeed } from "@/lib/incident-data";
import { getUserRecord } from "@/lib/user-data";
import { filterRows, RESTRICTED, resolveVisibility } from "@/lib/visibility";

export const dynamic = "force-dynamic";

/**
 * Incidents, partitioned by tenant (Phase 3③ follow-up).
 *
 * This endpoint returned every tenant's incidents to anyone. The executor was
 * dropping `tenant` at write time even though `NormalizedIncident` has carried
 * it since Phase 1a, so there was nothing to partition on — the read gap and
 * the write gap were the same gap.
 */
async function callerVisibility() {
  const session = await auth();
  const username = session?.user?.username;
  if (!username) return RESTRICTED;
  const role = ((session.user as { role?: Role }).role ?? "viewer") as Role;
  const record = await getUserRecord(username).catch(() => null);
  return resolveVisibility({ role, tenants: record?.tenants ?? null });
}

export async function GET() {
  const feed = await getIncidentFeed();
  const visibility = await callerVisibility();
  const { rows, withheld } = filterRows(feed.incidents, visibility);

  return Response.json(
    {
      ...feed,
      incidents: rows,
      // Withheld-by-authorization is reported, not silently shortened: a list
      // that is empty because you may not see it and one that is empty because
      // nothing happened call for opposite reactions.
      restricted: visibility.restricted,
      withheld,
    },
    {
      headers: {
        // Per-caller now, so a shared cache would serve one tenant's incidents
        // to another. This is the cache header that had to change, not an
        // optimisation that was dropped.
        "Cache-Control": "private, no-store",
      },
    },
  );
}
