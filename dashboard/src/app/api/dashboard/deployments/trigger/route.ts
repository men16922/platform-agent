import { auth } from "@/auth";
import { getSFNClient, getDeploymentStateMachineArn } from "@/lib/aws-client";
import { StartExecutionCommand } from "@aws-sdk/client-sfn";
import { writeAuditLog } from "@/lib/audit-data";
import { canApprove } from "@/lib/auth"; // For trigger deployment we can check if they have operator role
import type { Role } from "@/lib/auth";
import { v4 as uuidv4 } from "uuid";

export const dynamic = "force-dynamic";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

export async function POST(request: Request) {
  const session = await auth();

  // 1. Authentication Check
  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized: Please sign in." }, { status: 401 });
  }

  const username = session.user.username;
  const userEmail = session.user.email || undefined;
  const userRole = (session.user as any).role as Role || "viewer";

  // Check permissions: operator or admin can trigger deployments
  if (userRole === "viewer") {
    return Response.json({ error: "Forbidden: Viewer role cannot trigger deployments." }, { status: 403 });
  }

  // Parse body
  let body: {
    service_name?: string;
    version?: string;
    provider?: string;
    environment?: string;
  } = {};

  try {
    body = await request.json();
  } catch (e) {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const {
    service_name,
    version,
    provider = "aws",
    environment = "production",
  } = body;

  if (!service_name || !version) {
    return Response.json({ error: "Missing required fields: service_name and version" }, { status: 400 });
  }

  const deploymentId = `DEP-${uuidv4().replace(/-/g, "").substring(0, 8).toUpperCase()}`;

  // 2. Deployment execution payload for Step Functions
  const payload = {
    pipeline: "deployment_validation",
    deployment_id: deploymentId,
    service_name,
    version,
    provider,
    environment,
    triggered_by: username,
    triggered_at: new Date().toISOString(),
  };

  if (!isLiveMode()) {
    // Audit successful trigger in demo mode
    await writeAuditLog(
      { username, email: userEmail },
      { action: "trigger_deployment_demo", target: deploymentId },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({
      ok: true,
      deployment_id: deploymentId,
      notice: "Demo mode. Simulated triggering deployment pipeline.",
      payload,
    });
  }

  try {
    const stateMachineArn = await getDeploymentStateMachineArn();
    if (!stateMachineArn) {
      throw new Error("Deployment validation state machine ARN could not be resolved.");
    }

    const sfnClient = getSFNClient();
    const result = await sfnClient.send(
      new StartExecutionCommand({
        stateMachineArn,
        name: `deploy-${deploymentId.toLowerCase()}`,
        input: JSON.stringify(payload),
      })
    );

    // Audit successful live trigger
    await writeAuditLog(
      { username, email: userEmail },
      { action: "trigger_deployment", target: deploymentId },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({
      ok: true,
      deployment_id: deploymentId,
      execution_arn: result.executionArn,
    });
  } catch (error: any) {
    console.error("Failed to trigger deployment pipeline", error);

    // Audit failed trigger
    await writeAuditLog(
      { username, email: userEmail },
      { action: "trigger_deployment_failed", target: deploymentId },
      "failed",
      error.message || "Unknown error",
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ error: error.message || "Failed to trigger deployment pipeline" }, { status: 500 });
  }
}
