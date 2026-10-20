import { auth } from "@/auth";
import type { Role } from "@/lib/auth";

export const dynamic = "force-dynamic";
const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.username) {
    return Response.json({ error: "Please sign in." }, { status: 401 });
  }
  const role = (session.user as { role?: Role }).role;
  if (role !== "admin" && role !== "operator") {
    return Response.json({ error: "Operator/Admin role required." }, { status: 403 });
  }
  const { id } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
    return Response.json({ error: "Invalid request ID." }, { status: 400 });
  }
  try {
    const upstream = await fetch(`${LOCAL_API}/api/local-deploy/runs/${id}`, {
      headers: { "X-Platform-Actor": session.user.username },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return Response.json(await upstream.json(), { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Run state is unavailable. The request has not been re-submitted." }, { status: 503 });
  }
}
