import { ModelLogoImg } from "./model-logo-img";

// Brand assets are intentionally kept here (rather than duplicated in cards,
// chat, and timelines). Each image has a monogram fallback for offline demos.

interface Mark {
  label: string;
  cls: string;
  title: string;
  src: string;
}

// Brand marks are served locally from /public/models so they render offline and
// aren't subject to remote-favicon CSP/availability failures (the monogram is a
// last-resort fallback if a file is ever missing).
const MODEL_MARKS: Record<string, Mark> = {
  "local-qwen": { label: "Q", cls: "bg-[#6d3bef]/20 text-[#c4b5fd] border-[#7c3aed]/40", title: "Local LLM (Qwen)", src: "/models/qwen.svg" },
  "bedrock-claude": { label: "C", cls: "bg-[#d97757]/20 text-[#f0b49c] border-[#d97757]/45", title: "Bedrock Claude", src: "/models/claude.svg" },
  "vertex-gemini": { label: "G", cls: "bg-[#4285f4]/20 text-[#a9c7ff] border-[#4285f4]/45", title: "Vertex Gemini", src: "/models/gemini.svg" },
  "azure-gpt": { label: "A", cls: "bg-[#22b8cf]/20 text-[#9decf9] border-[#22b8cf]/45", title: "Azure OpenAI GPT", src: "/models/openai.svg" },
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
      {mark.src ? <ModelLogoImg src={mark.src} alt={mark.title} label={mark.label} /> : mark.label}
    </span>
  );
}
