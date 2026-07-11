// Static mirror of the Python AI Model Router (src/agents/ai/model_router.py).
// The Python router is the source of truth (served via /api/models); this mirror
// only backs the selector when the local router API is not running.

export const ENVIRONMENTS = ["aws", "gcp", "azure", "onprem"] as const;
export type EnvId = (typeof ENVIRONMENTS)[number];

export type Verdict = "recommended" | "allowed" | "discouraged";

export interface ModelOption {
  id: string;
  label: string;
  llm: string;
  framework: string;
  verdict: Verdict;
  reason: string;
}

interface ModelDef {
  id: string;
  label: string;
  llm: string;
  framework: string;
  home: EnvId;
}

const MODELS: ModelDef[] = [
  { id: "local-qwen", label: "Local LLM (Qwen)", llm: "Qwen2.5/3-Coder (MLX)", framework: "pydantic-ai", home: "onprem" },
  { id: "bedrock-claude", label: "Bedrock Claude", llm: "Claude (Bedrock)", framework: "strands", home: "aws" },
  { id: "vertex-gemini", label: "Vertex Gemini", llm: "Gemini 3.5 Flash", framework: "adk", home: "gcp" },
  { id: "azure-gpt", label: "Azure OpenAI GPT", llm: "GPT-5.4", framework: "msft", home: "azure" },
];

const NATIVE: Record<EnvId, string> = {
  aws: "bedrock-claude",
  gcp: "vertex-gemini",
  azure: "azure-gpt",
  onprem: "local-qwen",
};

const ENV_LABEL: Record<EnvId, string> = {
  aws: "AWS",
  gcp: "Google Cloud",
  azure: "Azure",
  onprem: "On-Prem",
};

const VERDICT_RANK: Record<Verdict, number> = { recommended: 0, allowed: 1, discouraged: 2 };

function suitability(model: ModelDef, provider: EnvId): { verdict: Verdict; reason: string } {
  const native = MODELS.find((m) => m.id === NATIVE[provider])!;
  const env = ENV_LABEL[provider];

  if (model.home === provider) {
    return { verdict: "recommended", reason: `Native pairing — ${model.label} is the ${env}-native brain.` };
  }
  if (provider === "onprem") {
    return {
      verdict: "allowed",
      reason: `${model.label} can drive on-prem deploys, but the cloud brain breaks air-gapped operation; ${native.label} is recommended for fully offline on-prem.`,
    };
  }
  if (model.id === "local-qwen") {
    return {
      verdict: "allowed",
      reason: `Local Qwen can drive ${env} deploys (offline brain, cloud hands); ${native.label} is the ${env}-native choice.`,
    };
  }
  return { verdict: "allowed", reason: `Non-native pairing — works, but ${native.label} is recommended for ${env}.` };
}

export function fallbackModelsFor(provider: EnvId): ModelOption[] {
  return MODELS.map((m) => {
    const fit = suitability(m, provider);
    return { id: m.id, label: m.label, llm: m.llm, framework: m.framework, verdict: fit.verdict, reason: fit.reason };
  }).sort((a, b) => VERDICT_RANK[a.verdict] - VERDICT_RANK[b.verdict] || a.label.localeCompare(b.label));
}
