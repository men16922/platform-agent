export const dynamic = "force-dynamic";

const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

export async function GET() {
  try {
    const res = await fetch(`${LOCAL_API}/health`, { cache: "no-store" });
    if (res.ok) {
      return Response.json({ router: "connected", runtime: "Local Qwen", path: "Qwen → supervisor → kagent" });
    }
  } catch {
    // The dashboard can run without the local runtime (for example on Vercel).
  }
  return Response.json({ router: "offline", runtime: "Local Qwen", path: "Qwen → supervisor → kagent" });
}
