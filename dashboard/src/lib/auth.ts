/**
 * Authentication & Authorization boundary for the platform-agent dashboard.
 *
 * This module defines the role/permission model. Actual enforcement is applied
 * at the middleware and API route level. Read endpoints remain public; write
 * endpoints require authentication once Auth.js is configured.
 *
 * See docs/DASHBOARD_AUTH_DESIGN.md for the full design.
 */

// ─── Roles ──────────────────────────────────────────────────

export type Role = "viewer" | "operator" | "admin";

// ─── Permissions ────────────────────────────────────────────

export type Permission =
  | "incidents:read"
  | "incidents:approve:p3"
  | "incidents:approve:p2"
  | "incidents:approve:p1"
  | "deployments:read"
  | "deployments:trigger"
  | "deployments:rollback"
  | "agents:read"
  | "settings:read"
  | "settings:write";

export const ROLE_PERMISSIONS: Record<Role, readonly Permission[]> = {
  viewer: [
    "incidents:read",
    "deployments:read",
    "agents:read",
    "settings:read",
  ],
  operator: [
    "incidents:read",
    "incidents:approve:p3",
    "incidents:approve:p2",
    "deployments:read",
    "deployments:trigger",
    "deployments:rollback",
    "agents:read",
    "settings:read",
  ],
  admin: [
    "incidents:read",
    "incidents:approve:p3",
    "incidents:approve:p2",
    "incidents:approve:p1",
    "deployments:read",
    "deployments:trigger",
    "deployments:rollback",
    "agents:read",
    "settings:read",
    "settings:write",
  ],
};

// ─── Permission checks ──────────────────────────────────────

/**
 * Check if a role has a specific permission.
 */
export function hasPermission(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}

/**
 * Check if a role can approve an incident of the given severity.
 */
export function canApprove(role: Role, severity: "P1" | "P2" | "P3"): boolean {
  switch (severity) {
    case "P1":
      return hasPermission(role, "incidents:approve:p1");
    case "P2":
      return hasPermission(role, "incidents:approve:p2");
    case "P3":
      return hasPermission(role, "incidents:approve:p3");
  }
}

/**
 * Determine the minimum required permission for an approval action.
 */
export function approvalPermission(severity: "P1" | "P2" | "P3"): Permission {
  return `incidents:approve:${severity.toLowerCase()}` as Permission;
}

// ─── Session types ──────────────────────────────────────────

export interface DashboardSession {
  user_id: string;
  email: string;
  name?: string;
  role: Role;
  org?: string;
  exp: number; // Unix timestamp
}

/**
 * Check if a session is valid (exists and not expired).
 */
export function isSessionValid(session: DashboardSession | null): session is DashboardSession {
  if (!session) return false;
  return session.exp > Math.floor(Date.now() / 1000);
}

// ─── Route protection ───────────────────────────────────────
//
// There is deliberately no route→level table here any more. One existed, was
// exported, and was imported by nothing: it said read routes were "public"
// while `proxy.ts`'s matcher said something else, and neither was what actually
// ran. Two policies that disagree and a third that executes is worse than no
// written policy at all.
//
// Where authorization actually lives now:
//   - write routes  -> `src/proxy.ts` matcher + an `auth()` check inside each
//                      route handler (the proxy is an optimistic check only,
//                      per Next's own guidance)
//   - read routes    -> `src/lib/visibility.ts`, called by the handler next to
//                      the data, because the rule is per-tenant and a matcher
//                      cannot express "this row but not that one"
