import { auth } from "@/auth";
import { listAuditLogs } from "@/lib/audit-data";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";

// GET /api/dashboard/audit - List audit logs (Admin and Operator only)
export async function GET(request: Request) {
  const session = await auth();

  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userRole = (session.user as any).role as Role || "viewer";
  if (userRole !== "admin" && userRole !== "operator") {
    return Response.json({ error: "Forbidden: Admin or Operator role required." }, { status: 403 });
  }

  try {
    const logs = await listAuditLogs();
    return Response.json({ logs });
  } catch (error: any) {
    return Response.json({ error: error.message || "Failed to list audit logs" }, { status: 500 });
  }
}
