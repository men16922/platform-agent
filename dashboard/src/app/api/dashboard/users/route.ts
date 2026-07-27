import { auth } from "@/auth";
import { listUserRecords, upsertUserRecord } from "@/lib/user-data";
import { writeAuditLog } from "@/lib/audit-data";
import { checkGrants, fetchRoster } from "@/lib/platform-roster";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";

// GET /api/dashboard/users - List users (Admin only)
export async function GET(request: Request) {
  const session = await auth();

  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userRole = (session.user as any).role as Role || "viewer";
  if (userRole !== "admin") {
    return Response.json({ error: "Forbidden: Admin role required." }, { status: 403 });
  }

  try {
    const users = await listUserRecords();
    return Response.json({ users });
  } catch (error: any) {
    return Response.json({ error: error.message || "Failed to list users" }, { status: 500 });
  }
}

// POST /api/dashboard/users - Manage user role overrides (Admin only)
export async function POST(request: Request) {
  const session = await auth();

  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const adminUsername = session.user.username;
  const adminEmail = session.user.email || undefined;
  const userRole = (session.user as any).role as Role || "viewer";

  if (userRole !== "admin") {
    return Response.json({ error: "Forbidden: Admin role required." }, { status: 403 });
  }

  let body: { username?: string; role?: Role; name?: string; email?: string; tenants?: string[] } = {};
  try {
    body = await request.json();
  } catch (e) {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { username, role, name, email, tenants } = body;
  if (!username || !role) {
    return Response.json({ error: "Missing required fields: username and role" }, { status: 400 });
  }

  if (role !== "admin" && role !== "operator" && role !== "viewer") {
    return Response.json({ error: "Invalid role: must be admin, operator, or viewer" }, { status: 400 });
  }

  // Tenant grants, if this request carries any, are checked against the declared
  // roster before they are stored. An unchecked grant is not an inert typo: it
  // renders as access on this page and matches nothing in the fleet view, so the
  // one screen that is supposed to answer "who can see what" answers wrongly in
  // the direction that looks fine.
  let grants: string[] | undefined;
  if (tenants !== undefined) {
    if (!Array.isArray(tenants) || tenants.some((t) => typeof t !== "string")) {
      return Response.json({ error: "Invalid tenants: must be an array of strings" }, { status: 400 });
    }
    const check = checkGrants(tenants, await fetchRoster());
    if (!check.ok) {
      return check.unverifiable
        ? Response.json(
            {
              error:
                "Cannot verify tenant grants: the platform registry is unreachable. " +
                "Grants are not stored unverified.",
            },
            { status: 503 },
          )
        : Response.json(
            {
              error: `Unknown tenant(s): ${check.unknown.join(", ")}. Grants must name a tenant declared in the platform registry.`,
              unknown: check.unknown,
            },
            { status: 400 },
          );
    }
    grants = check.tenants;
  }

  try {
    const updatedUser = await upsertUserRecord(username, role, email, name, grants);

    // Log this action to audit log. Grants are named in the target: a grant
    // change is an authorization change, and an audit trail that records only
    // the role would not show it.
    await writeAuditLog(
      { username: adminUsername, email: adminEmail },
      {
        action: "update_user_role",
        target:
          grants === undefined
            ? `${username}:${role}`
            : `${username}:${role}:tenants=${grants.length > 0 ? grants.join("|") : "(none)"}`,
      },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ ok: true, user: updatedUser });
  } catch (error: any) {
    console.error("Failed to update user role override", error);

    await writeAuditLog(
      { username: adminUsername, email: adminEmail },
      { action: "update_user_role_failed", target: `${username}:${role}` },
      "failed",
      error.message || "Unknown error",
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ error: error.message || "Failed to update user role override" }, { status: 500 });
  }
}
