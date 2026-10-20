import { auth } from "@/auth";
import { writeAuditLog } from "@/lib/audit-data";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";

const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

// Streams tool-calling progress (SSE) from the AI Model Router API to the Agents
// chat. Same auth gate as the non-streaming deploy route; the upstream SSE body
// is piped straight through.
export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.username) {
    return Response.json({ error: "Unauthorized: Please sign in." }, { status: 401 });
  }
  const userRole = ((session.user as { role?: Role }).role as Role) || "viewer";
  if (userRole !== "admin" && userRole !== "operator") {
    return Response.json({ error: "Forbidden: Viewer role cannot trigger deployments." }, { status: 403 });
  }

  let body: { instruction?: string; model?: string; provider?: string; request_id?: string; read_only?: boolean; snapshot?: unknown } = {};
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
  if (typeof body.request_id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(body.request_id)) {
    return Response.json({ error: "A stable request_id UUID is required." }, { status: 400 });
  }

  // Best-effort audit of the authorized initiation (final status is recorded by
  // the executor into the Deployments/Activity feed).
  await writeAuditLog(
    { username: session.user.username, email: session.user.email || undefined },
    { action: "agent_nl_deploy_stream", target: `${provider}:${model} — ${instruction.slice(0, 100)}` },
    "success",
    undefined,
    {
      ip: request.headers.get("x-forwarded-for") || undefined,
      userAgent: request.headers.get("user-agent") || undefined,
    },
  );

  let upstream: Response;
  try {
    upstream = await fetch(`${LOCAL_API}/api/local-deploy/stream`, {
      method: "POST",
      // Only the authenticated session supplies the actor, never a caller header/body.
      headers: { "Content-Type": "application/json", "X-Platform-Actor": session.user.username },
      body: JSON.stringify({ instruction, model, provider, request_id: body.request_id, read_only: readOnly, ...(body.snapshot !== undefined ? { snapshot: body.snapshot } : {}) }),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      {
        error: "The AI Model Router API is unreachable.",
        hint: `Start it next to your MLX-LM / cluster: make local-llm-up (LOCAL_DEPLOY_API_URL=${LOCAL_API})`,
      },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return Response.json({ error: "Router API error", detail }, { status: upstream.ok ? 502 : upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
