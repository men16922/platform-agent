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

// ─── Route protection categories ────────────────────────────

export type RouteProtection = "public" | "authenticated" | "operator" | "admin";

/**
 * Dashboard route protection mapping.
 * Read paths are public; write paths require authentication.
 */
export const ROUTE_PROTECTION: Record<string, RouteProtection> = {
  // Read endpoints (public)
  "/api/dashboard/incidents": "public",
  "/api/dashboard/deployments": "public",
  "/api/dashboard/activities": "public",
  "/api/dashboard/health": "public",

  // Write endpoints (auth required — not yet implemented)
  "/api/dashboard/incidents/*/approve": "operator",
  "/api/dashboard/deployments/trigger": "operator",
  "/api/dashboard/deployments/*/rollback": "operator",
  "/api/dashboard/settings": "admin",
};

/**
 * Check if a role satisfies a route's protection level.
 */
export function meetsProtectionLevel(role: Role | null, level: RouteProtection): boolean {
  if (level === "public") return true;
  if (!role) return false;
  if (level === "authenticated") return true;

  const hierarchy: Record<Role, number> = { viewer: 0, operator: 1, admin: 2 };
  const required: Record<RouteProtection, number> = {
    public: -1,
    authenticated: 0,
    operator: 1,
    admin: 2,
  };

  return hierarchy[role] >= required[level];
}
