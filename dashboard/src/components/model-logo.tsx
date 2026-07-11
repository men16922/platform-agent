// Dependency-free per-model marks (monograms, not brand logos) so each AI model
// is visually distinct in the chat, activity timeline and Deployments table.

interface Mark {
  label: string;
  cls: string;
  title: string;
}

const MODEL_MARKS: Record<string, Mark> = {
  "local-qwen": { label: "Q", cls: "bg-[#6d3bef]/20 text-[#c4b5fd] border-[#7c3aed]/40", title: "Local LLM (Qwen)" },
  "bedrock-claude": { label: "C", cls: "bg-[#d97757]/20 text-[#f0b49c] border-[#d97757]/45", title: "Bedrock Claude" },
  "vertex-gemini": { label: "G", cls: "bg-[#4285f4]/20 text-[#a9c7ff] border-[#4285f4]/45", title: "Vertex Gemini" },
  "azure-gpt": { label: "A", cls: "bg-[#22b8cf]/20 text-[#9decf9] border-[#22b8cf]/45", title: "Azure OpenAI GPT" },
};

const FALLBACK: Mark = { label: "AI", cls: "bg-white/10 text-[var(--muted)] border-white/15", title: "AI model" };

/** Best-effort model id from a recorded agent label like "On-Prem Agent (Local LLM (Qwen))". */
export function modelIdFromAgent(agent: string): string | null {
  const a = agent.toLowerCase();
  if (a.includes("qwen")) return "local-qwen";
  if (a.includes("claude") || a.includes("bedrock")) return "bedrock-claude";
  if (a.includes("gemini")) return "vertex-gemini";
  if (a.includes("gpt") || a.includes("azure openai")) return "azure-gpt";
  return null;
}

export function ModelLogo({ model, size = "sm" }: { model: string | null | undefined; size?: "sm" | "md" }) {
  const mark = (model && MODEL_MARKS[model]) || FALLBACK;
  const dim = size === "sm" ? "h-4 w-4 text-[9px]" : "h-5 w-5 text-[10px]";
  return (
    <span
      title={mark.title}
      className={`inline-flex ${dim} shrink-0 items-center justify-center rounded border font-bold leading-none ${mark.cls}`}
    >
      {mark.label}
    </span>
  );
}
