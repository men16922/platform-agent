export const dynamic = "force-dynamic";

const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export async function GET() {
  let router: "connected" | "unavailable" = "unavailable";
  try {
    const res = await fetch(`${LOCAL_API}/health`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      const body = await res.json();
      if (body?.status === "ok" && body?.service === "model-router-api") router = "connected";
    }
  } catch {
    // The dashboard can run without the local runtime (for example on Vercel).
  }
  // A health response establishes only router reachability, not a live model,
  // supervisor delegation, Kubernetes access, or any particular execution path.
  return Response.json({ router, checked_at: new Date().toISOString() }, { headers: { "Cache-Control": "no-store" } });
}
