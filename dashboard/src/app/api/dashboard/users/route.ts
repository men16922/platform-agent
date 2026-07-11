import { auth } from "@/auth";
import { listUserRecords, upsertUserRecord } from "@/lib/user-data";
import { writeAuditLog } from "@/lib/audit-data";
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

  let body: { username?: string; role?: Role; name?: string; email?: string } = {};
  try {
    body = await request.json();
  } catch (e) {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { username, role, name, email } = body;
  if (!username || !role) {
    return Response.json({ error: "Missing required fields: username and role" }, { status: 400 });
  }

  if (role !== "admin" && role !== "operator" && role !== "viewer") {
    return Response.json({ error: "Invalid role: must be admin, operator, or viewer" }, { status: 400 });
  }

  try {
    const updatedUser = await upsertUserRecord(username, role, email, name);

    // Log this action to audit log
    await writeAuditLog(
      { username: adminUsername, email: adminEmail },
      { action: "update_user_role", target: `${username}:${role}` },
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
