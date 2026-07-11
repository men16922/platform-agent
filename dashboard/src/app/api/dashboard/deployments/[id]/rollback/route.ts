import { auth } from "@/auth";
import { getSFNClient, getDeploymentStateMachineArn } from "@/lib/aws-client";
import { StartExecutionCommand } from "@aws-sdk/client-sfn";
import { writeAuditLog } from "@/lib/audit-data";
import type { Role } from "@/lib/auth";
import { v4 as uuidv4 } from "uuid";

export const dynamic = "force-dynamic";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: deploymentId } = await params;
  const session = await auth();

  // 1. Authentication Check
  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized: Please sign in." }, { status: 401 });
  }

  const username = session.user.username;
  const userEmail = session.user.email || undefined;
  const userRole = (session.user as any).role as Role || "viewer";

  // Check permissions: operator or admin can rollback deployments
  if (userRole === "viewer") {
    return Response.json({ error: "Forbidden: Viewer role cannot rollback deployments." }, { status: 403 });
  }

  // Parse body
  let body: {
    service_name?: string;
    rollback_version?: string;
    version?: string;
    provider?: string;
    environment?: string;
    scope?: string;
    namespace?: string;
    cluster_name?: string;
  } = {};

  try {
    body = await request.json();
  } catch (e) {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const {
    service_name,
    rollback_version,
    version,
    provider = "aws",
    environment = "production",
    scope = "app",
    namespace = "default",
    cluster_name = "platform-agent",
  } = body;

  // ── On-prem path: real rollback against the local kind/k3s cluster ──
  // Routes to the local router (next to the cluster); the cloud AWS Step
  // Functions path below cannot reach an on-prem cluster.
  if (provider === "onprem") {
    if (scope !== "cluster" && !service_name) {
      return Response.json({ error: "Missing required field: service_name" }, { status: 400 });
    }
    const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";
    try {
      const res = await fetch(`${LOCAL_API}/api/local-rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: service_name || cluster_name,
          namespace,
          scope,
          cluster_name,
          // Single-row lifecycle: supersede the original deployment's row.
          deployment_id: deploymentId,
          service: service_name,
          version,
          environment,
        }),
      });
      const data = await res.json();
      const ok = res.ok && data.ok;
      await writeAuditLog(
        { username, email: userEmail },
        { action: scope === "cluster" ? "rollback_cluster" : "rollback_deployment", target: deploymentId },
        ok ? "success" : "failed",
        ok ? undefined : data.error || data.summary,
        { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined },
      );
      if (!ok) {
        return Response.json({ error: data.error || data.summary || "On-prem rollback failed" }, { status: 502 });
      }
      return Response.json({
        ok: true,
        rollback_id: `ROL-${uuidv4().replace(/-/g, "").substring(0, 8).toUpperCase()}`,
        scope,
        summary: data.summary,
        result: data.result,
      });
    } catch (error: any) {
      return Response.json(
        { error: `On-prem router unreachable at ${LOCAL_API}: ${error.message}` },
        { status: 502 },
      );
    }
  }

  if (!service_name || !rollback_version) {
    return Response.json(
      { error: "Missing required fields: service_name and rollback_version" },
      { status: 400 }
    );
  }

  const rollbackId = `ROL-${uuidv4().replace(/-/g, "").substring(0, 8).toUpperCase()}`;

  // Deployment execution payload for Step Functions (rollback is a deployment validation pointing to previous version)
  const payload = {
    pipeline: "deployment_validation",
    deployment_id: rollbackId,
    service_name,
    version: rollback_version,
    provider,
    environment,
    rollout_reason: `Rollback of deployment ${deploymentId} requested by ${username}`,
    triggered_by: username,
    triggered_at: new Date().toISOString(),
    is_rollback: true,
    previous_deployment_id: deploymentId,
  };

  if (!isLiveMode()) {
    // Audit successful rollback in demo mode
    await writeAuditLog(
      { username, email: userEmail },
      { action: "rollback_deployment_demo", target: deploymentId },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({
      ok: true,
      rollback_id: rollbackId,
      notice: "Demo mode. Simulated triggering rollback pipeline.",
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
        name: `rollback-${rollbackId.toLowerCase()}`,
        input: JSON.stringify(payload),
      })
    );

    // Audit successful live rollback
    await writeAuditLog(
      { username, email: userEmail },
      { action: "rollback_deployment", target: deploymentId },
      "success",
      undefined,
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({
      ok: true,
      rollback_id: rollbackId,
      execution_arn: result.executionArn,
    });
  } catch (error: any) {
    console.error(`Failed to rollback deployment ${deploymentId}`, error);

    // Audit failed rollback
    await writeAuditLog(
      { username, email: userEmail },
      { action: "rollback_deployment_failed", target: deploymentId },
      "failed",
      error.message || "Unknown error",
      { ip: request.headers.get("x-forwarded-for") || undefined, userAgent: request.headers.get("user-agent") || undefined }
    );

    return Response.json({ error: error.message || "Failed to trigger rollback pipeline" }, { status: 500 });
  }
}
