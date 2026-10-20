import { auth } from "@/auth";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";
const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.username) return Response.json({ error: "Please sign in." }, { status: 401 });
  const role = (session.user as { role?: Role }).role;
  if (role !== "operator" && role !== "admin") {
    return Response.json({ error: "Operator/Admin role required." }, { status: 403 });
  }
  let body: unknown;
  try { body = await request.json(); }
  catch { return Response.json({ error: "Invalid JSON body." }, { status: 400 }); }
  try {
    const upstream = await fetch(`${LOCAL_API}/api/local-deploy/prepared`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Platform-Actor": session.user.username },
      body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return Response.json(await upstream.json(), { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Acceptance is unconfirmed. Check the same request ID before submitting again." }, { status: 503 });
  }
}
