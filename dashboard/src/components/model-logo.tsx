/* eslint-disable @next/next/no-img-element -- model marks are small remote brand assets with a text fallback. */
// Brand assets are intentionally kept here (rather than duplicated in cards,
// chat, and timelines). Each image has a monogram fallback for offline demos.

interface Mark {
  label: string;
  cls: string;
  title: string;
  src: string;
}

const MODEL_MARKS: Record<string, Mark> = {
  "local-qwen": { label: "Q", cls: "bg-[#6d3bef]/20 text-[#c4b5fd] border-[#7c3aed]/40", title: "Local LLM (Qwen)", src: "https://qwen.ai/favicon.ico" },
  "bedrock-claude": { label: "C", cls: "bg-[#d97757]/20 text-[#f0b49c] border-[#d97757]/45", title: "Bedrock Claude", src: "https://www.anthropic.com/favicon.ico" },
  "vertex-gemini": { label: "G", cls: "bg-[#4285f4]/20 text-[#a9c7ff] border-[#4285f4]/45", title: "Vertex Gemini", src: "https://www.gstatic.com/images/branding/product/1x/gemini_32dp.png" },
  "azure-gpt": { label: "A", cls: "bg-[#22b8cf]/20 text-[#9decf9] border-[#22b8cf]/45", title: "Azure OpenAI GPT", src: "https://cdn.simpleicons.org/openai/FFFFFF" },
};

const FALLBACK: Mark = { label: "AI", cls: "bg-white/10 text-[var(--muted)] border-white/15", title: "AI model", src: "" };

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
      {mark.src ? <img src={mark.src} alt={mark.title} className="h-full w-full rounded-[3px] object-contain p-px" onError={(event) => { event.currentTarget.style.display = "none"; event.currentTarget.parentElement?.append(mark.label); }} /> : mark.label}
    </span>
  );
}
