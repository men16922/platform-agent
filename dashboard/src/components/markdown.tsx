// Minimal dependency-free markdown for LLM output (our own text, escaped via
// React children — no HTML injection). Supports **bold**, `code`, and bullet
// lists. Shared by the agent chat and the deployment detail page.
import type { ReactNode } from "react";

function renderInline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const tok = match[0];
    if (tok.startsWith("**")) {
      nodes.push(<strong key={`${keyBase}-${i}`} className="font-semibold text-[#e6edf7]">{tok.slice(2, -2)}</strong>);
    } else {
      nodes.push(
        <code key={`${keyBase}-${i}`} className="rounded bg-[#8ab4f8]/12 px-1 py-0.5 text-[0.9em] text-[#a9c7ff]">{tok.slice(1, -1)}</code>,
      );
    }
    last = match.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (key: string) => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={key} className="list-disc space-y-0.5 pl-4 marker:text-[#8ab4f8]">
        {bullets.map((li, i) => <li key={i}>{renderInline(li, `${key}-${i}`)}</li>)}
      </ul>,
    );
    bullets = [];
  };
  lines.forEach((line, idx) => {
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }
    flush(`ul-${idx}`);
    if (line.trim() === "") {
      blocks.push(<div key={`sp-${idx}`} className="h-1" />);
      return;
    }
    blocks.push(<p key={`p-${idx}`} className="leading-relaxed">{renderInline(line, `p-${idx}`)}</p>);
  });
  flush("ul-end");
  return <div className="space-y-1">{blocks}</div>;
}
