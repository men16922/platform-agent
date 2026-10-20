import { auth } from "@/auth";
import { writeAuditLog } from "@/lib/audit-data";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";

const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

// Forwards a natural-language deploy from the Agents chat to the local AI Model
// Router API (executor-writes / dashboard-reads). The dashboard's AWS role is
// read-only; persistence of the deploy into the Deployments/Activity feed is the
// local API's responsibility.
export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized: Please sign in." }, { status: 401 });
  }

  const username = session.user.username;
  const userEmail = session.user.email || undefined;
  const userRole = ((session.user as { role?: Role }).role as Role) || "viewer";
  if (userRole !== "admin" && userRole !== "operator") {
    return Response.json({ error: "Forbidden: Viewer role cannot trigger deployments." }, { status: 403 });
  }

  let body: { instruction?: string; model?: string; provider?: string; read_only?: boolean; snapshot?: unknown } = {};
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const instruction = typeof body?.instruction === "string" ? body.instruction.trim() : "";
  const model = body?.model || "local-qwen";
  const provider = body?.provider || "onprem";
  if (body?.read_only !== undefined && typeof body.read_only !== "boolean") {
    return Response.json({ error: "read_only must be a boolean." }, { status: 400 });
  }
  const readOnly = body?.read_only ?? false;
  if (readOnly && (model !== "local-qwen" || provider !== "onprem")) {
    return Response.json({ error: "Read-only inspection is supported only for local-qwen/onprem." }, { status: 400 });
  }
  if (body?.snapshot !== undefined && (body.snapshot === null || typeof body.snapshot !== "object" || Array.isArray(body.snapshot) || !readOnly)) {
    return Response.json({ error: "Snapshot analysis requires a snapshot object and read-only mode." }, { status: 400 });
  }
  if (!instruction) {
    return Response.json({ error: "Missing 'instruction'." }, { status: 400 });
  }

  const auditContext = {
    ip: request.headers.get("x-forwarded-for") || undefined,
    userAgent: request.headers.get("user-agent") || undefined,
  };

  try {
    const res = await fetch(`${LOCAL_API}/api/local-deploy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, model, provider, read_only: readOnly, ...(body.snapshot !== undefined ? { snapshot: body.snapshot } : {}) }),
      cache: "no-store",
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || `Router API returned ${res.status}`);
    }

    await writeAuditLog(
      { username, email: userEmail },
      { action: "agent_nl_deploy", target: `${provider}:${model}` },
      data.ok ? "success" : "failed",
      data.ok ? undefined : "Deploy reported not ok",
      auditContext,
    );

    return Response.json(data);
  } catch (error: any) {
    await writeAuditLog(
      { username, email: userEmail },
      { action: "agent_nl_deploy_failed", target: `${provider}:${model}` },
      "failed",
      error.message || "Unknown error",
      auditContext,
    );

    return Response.json(
      {
        error: error.message || "Failed to reach the local deploy API",
        hint: `Start the router API next to your MLX-LM / kind cluster: uvicorn src.agents.ai.local_deploy_api:app --port 8077 (LOCAL_DEPLOY_API_URL=${LOCAL_API})`,
      },
      { status: 502 },
    );
  }
}
