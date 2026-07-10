/**
 * Next.js Middleware — Auth.js session protection.
 *
 * Read routes are PUBLIC (no auth required).
 * Write routes (future) require authentication.
 * Auth API routes are always allowed through.
 */

export { auth as middleware } from "@/auth";

export const config = {
  // Only run middleware on write API routes (future) and auth routes.
  // Read routes (/api/dashboard/incidents, /deployments, etc.) are public.
  matcher: [
    "/api/auth/:path*",
    "/api/dashboard/:path*/approve",
    "/api/dashboard/:path*/rollback",
    "/api/dashboard/deployments/trigger",
    "/api/dashboard/settings",
  ],
};
