import { ENVIRONMENTS, fallbackModelsFor, type EnvId } from "@/lib/model-router";

export const dynamic = "force-dynamic";

const LOCAL_API = process.env.LOCAL_DEPLOY_API_URL || "http://127.0.0.1:8077";

// Proxies the AI Model Router's per-environment model options. The Python router
// (src/agents/ai/model_router.py) is the source of truth; when the local API is
// not running we fall back to a static mirror so the selector still renders.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const providerParam = url.searchParams.get("provider") || "onprem";
  const provider = (ENVIRONMENTS.includes(providerParam as EnvId) ? providerParam : "onprem") as EnvId;

  try {
    const res = await fetch(`${LOCAL_API}/api/models?provider=${encodeURIComponent(provider)}`, {
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return Response.json({ ...data, source: "router-api" });
    }
  } catch {
    // fall through to static mirror
  }

  return Response.json({
    provider,
    models: fallbackModelsFor(provider),
    source: "static-fallback",
    notice: `Router API unreachable at ${LOCAL_API}. Showing static options; start it with: uvicorn src.agents.ai.local_deploy_api:app --port 8077`,
  });
}
