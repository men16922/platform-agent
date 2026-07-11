/**
 * Next.js Middleware — Auth.js session protection.
 *
 * Read routes are PUBLIC (no auth required).
 * Write routes (future) require authentication.
 * Auth routes (/api/auth/*) must NOT be intercepted.
 */

export { auth as middleware } from "@/auth";

export const config = {
  // Only protect future write endpoints.
  // Do NOT include /api/auth/* here — that would block sign-in.
  matcher: [
    "/api/dashboard/:path*/approve",
    "/api/dashboard/:path*/rollback",
    "/api/dashboard/deployments/trigger",
    "/api/dashboard/settings",
    "/api/dashboard/users",
    "/api/dashboard/audit",
  ],
};
