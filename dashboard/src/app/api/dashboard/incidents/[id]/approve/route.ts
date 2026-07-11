import { auth } from "@/auth";
import { getApprovalRequest, approveApprovalRequest, rejectApprovalRequest } from "@/lib/approval-data";
import { canApprove } from "@/lib/auth";
import { writeAuditLog } from "@/lib/audit-data";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: approvalId } = await params;
  const session = await auth();

  // 1. Authentication check
  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized: Please sign in." }, { status: 401 });
  }

  const username = session.user.username;
  const userEmail = session.user.email || undefined;
  const userRole = (session.user as any).role as Role || "viewer";

  // Parse request body
  let body: { decision?: string; reason?: string } = {};
  try {
    body = await request.json();
  } catch (e) {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { decision, reason = "" } = body;
  if (!decision || (decision !== "approve" && decision !== "reject")) {
    return Response.json({ error: "Decision must be either 'approve' or 'reject'" }, { status: 400 });
  }

  // 2. Lookup the approval request
  const approvalRequest = await getApprovalRequest(approvalId);
  if (!approvalRequest) {
    return Response.json({ error: `Approval request ${approvalId} not found` }, { status: 404 });
  }

  if (approvalRequest.status !== "PENDING") {
    return Response.json(
      { error: `Approval request ${approvalId} is already processed (${approvalRequest.status})` },
      { status: 400 }
    );
  }

  // 3. Authorization check based on severity
  const severity = approvalRequest.severity || "P3";
  if (!canApprove(userRole, severity)) {
    // Audit failed authorization attempt
    await writeAuditLog(
      { username, email: userEmail },
      { action: `${decision}_incident_denied`, target: approvalId },
      "failed",
      `Insufficient role ${userRole} to approve severity ${severity}`,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );
    return Response.json(
      { error: `Forbidden: Role ${userRole} is not authorized to approve ${severity} incidents.` },
      { status: 403 }
    );
  }

  // 4. Perform SFN callback & DB update
  try {
    if (decision === "approve") {
      await approveApprovalRequest(approvalId, username);
    } else {
      await rejectApprovalRequest(approvalId, username, reason);
    }

    // Audit successful action
    await writeAuditLog(
      { username, email: userEmail },
      { action: `${decision}_incident`, target: approvalId },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ ok: true, status: decision === "approve" ? "APPROVED" : "REJECTED" });
  } catch (error: any) {
    console.error(`Failed to handle approval decision for ${approvalId}`, error);

    // Audit failed operation
    await writeAuditLog(
      { username, email: userEmail },
      { action: `${decision}_incident_error`, target: approvalId },
      "failed",
      error.message || "Unknown error",
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ error: error.message || "Internal server error" }, { status: 500 });
  }
}
