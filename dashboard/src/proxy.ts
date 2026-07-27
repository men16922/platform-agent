/**
 * Next.js Proxy — Auth.js session protection.
 *
 * Renamed from `middleware.ts` in Next 16 (the `middleware` file convention is
 * deprecated; see node_modules/next/dist/docs/.../file-conventions/proxy.md).
 *
 * This is an OPTIMISTIC check only. Next's own guidance is that proxy runs in
 * front of the app and "should not be your only line of defense" — so the write
 * routes matched below re-check the session themselves, and read-side tenant
 * partitioning lives in `lib/visibility.ts`, which the route handlers call
 * next to the data (Phase 3③).
 *
 * Read routes are not matched here on purpose: they are not uniformly public
 * any more, but their rule is per-tenant rather than per-route, and a matcher
 * cannot express "this row but not that one".
 */

export { auth as proxy } from "@/auth";

export const config = {
  // Write endpoints. Do NOT include /api/auth/* — that would block sign-in.
  matcher: [
    "/api/dashboard/:path*/approve",
    "/api/dashboard/:path*/rollback",
    "/api/dashboard/deployments/trigger",
    "/api/dashboard/settings",
    "/api/dashboard/users",
    "/api/dashboard/audit",
  ],
};
