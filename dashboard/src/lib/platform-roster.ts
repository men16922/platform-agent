/**
 * The declared tenant roster — what a grant is checked against.
 *
 * `visibility.ts` decides what a grant *shows*. Nothing decided whether the
 * grant named anything real: an admin could grant `acmee` and the system stored
 * it, displayed it as access, and matched zero rows forever. That failure is
 * silent in the worse direction — the screen says the person has access, and the
 * fleet view says they have nothing, and neither says why.
 *
 * The roster comes from the registry via the hub, not from pushed status. A
 * roster derived from what has reported would make a tenant ungrantable until
 * its agent happened to push, which is backwards: a grant is how someone gets
 * ready to look at a tenant, including one that has gone quiet.
 *
 * Three answers, kept distinct for the same reason `connected: false` is not
 * `[]` elsewhere here:
 *
 *   - roster of names -> validate against it
 *   - `null`          -> could not ask; **reject the write**, do not guess
 *   - `[]`            -> the registry genuinely declares no tenants
 *
 * `null` failing closed is the whole point. Falling back to "accept anything"
 * when the hub is down reintroduces exactly the unchecked grant this module
 * exists to prevent, and it would do it precisely when nobody is watching.
 */

const HUB = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export interface Roster {
  /** Declared tenant names. */
  tenants: string[];
  /** Declared "tenant/env" identities — kept for callers that grant per env. */
  identities: string[];
}

/**
 * Ask the hub for the declared roster.
 *
 * Returns `null` when the roster could not be obtained *for any reason* — hub
 * down, non-2xx, malformed body. A caller cannot tell those apart and should
 * not act differently on them: all three mean "unverified".
 */
export async function fetchRoster(): Promise<Roster | null> {
  try {
    const res = await fetch(`${HUB}/api/platform/tenants`, { cache: "no-store" });
    if (!res.ok) return null;
    const body = await res.json();
    // A body that is not the shape we expect is not an empty roster. Treating a
    // malformed response as "no tenants declared" would reject every grant while
    // reporting a clean, plausible reason.
    if (!Array.isArray(body?.tenants)) return null;
    return {
      tenants: body.tenants.filter((t: unknown): t is string => typeof t === "string"),
      identities: Array.isArray(body?.identities)
        ? body.identities.filter((t: unknown): t is string => typeof t === "string")
        : [],
    };
  } catch {
    return null;
  }
}

export interface GrantCheck {
  /** True when every requested grant names a declared tenant. */
  ok: boolean;
  /** Normalized grants, safe to store. Empty when `ok` is false. */
  tenants: string[];
  /** Requested names that no declared tenant matches. */
  unknown: string[];
  /** Set when the roster itself was unavailable — a distinct failure. */
  unverifiable?: boolean;
}

/**
 * Check requested grants against the roster.
 *
 * Whitespace is trimmed and blanks dropped before checking, because `["acme",
 * ""]` is a typo, not a request for a tenant named "". Duplicates collapse.
 * Matching is exact and case-sensitive: registry tenant names are DNS-label-safe
 * lowercase (`naming_prefix` is validated as such), so a case-insensitive match
 * here would accept a name that no namespace, RBAC rule or push report will ever
 * agree with.
 */
export function checkGrants(requested: readonly string[], roster: Roster | null): GrantCheck {
  const wanted = [...new Set(requested.map((t) => t.trim()).filter((t) => t.length > 0))];

  if (roster === null) {
    // Unverified is not approved. An empty grant list is the exception: asking
    // to revoke everything needs no roster, and refusing it would leave an admin
    // unable to take back access while the hub is down.
    if (wanted.length === 0) return { ok: true, tenants: [], unknown: [] };
    return { ok: false, tenants: [], unknown: [], unverifiable: true };
  }

  const declared = new Set(roster.tenants);
  const unknown = wanted.filter((t) => !declared.has(t));
  if (unknown.length > 0) return { ok: false, tenants: [], unknown };
  return { ok: true, tenants: wanted, unknown: [] };
}
