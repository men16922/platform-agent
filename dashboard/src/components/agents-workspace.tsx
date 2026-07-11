"use client";

import { useEffect, useState } from "react";
import { AgentCard } from "@/components/agent-card";
import { AgentDeployChat } from "@/components/agent-deploy-chat";
import { OnPremRuntimePanel } from "@/components/onprem-runtime-panel";

type ModelOption = { id: string; label: string; llm: string; framework: string; verdict: "recommended" | "allowed" | "discouraged"; reason: string };

const agents = [
  { cloud: "aws" as const, name: "Strands Agent", provider: "AWS", llm: "Bedrock Claude", runtime: "Bedrock AgentCore", path: "Claude → supervisor → AWS deployment tools" },
  { cloud: "gcp" as const, name: "ADK Agent", provider: "Google Cloud", llm: "Gemini 3.5 Flash", runtime: "Vertex AI Agent Engine", path: "Gemini → supervisor → GKE tools" },
  { cloud: "azure" as const, name: "MS Agent", provider: "Microsoft Azure", llm: "GPT-5.4", runtime: "Foundry Agent Service", path: "GPT-5.4 → supervisor → AKS tools" },
  { cloud: "onprem" as const, name: "On-Prem Agent", provider: "On-Premise", llm: "Local Qwen + kagent", runtime: "Local Qwen", path: "Qwen → supervisor → kagent" },
];

export function AgentsWorkspace() {
  const [selected, setSelected] = useState("onprem");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelId, setModelId] = useState("local-qwen");
  const agent = agents.find((item) => item.cloud === selected) ?? agents[3];

  useEffect(() => {
    fetch(`/api/dashboard/agents/models?provider=${agent.cloud}`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        const next = (data.models || []) as ModelOption[];
        setModels(next);
        setModelId((current) => next.some((model) => model.id === current) ? current : (next[0]?.id || ""));
      })
      .catch(() => setModels([]));
  }, [agent.cloud]);
  const model = models.find((item) => item.id === modelId) ?? null;
  return <>
    <section>
      <div className="mb-3 flex items-center justify-between"><h3 className="eyebrow">1. Select execution agent</h3><span className="text-xs text-[var(--muted)]">The selection controls runtime and chat context.</span></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {agents.map((item) => <AgentCard key={item.cloud} {...item} selected={item.cloud === selected} onSelect={() => setSelected(item.cloud)} />)}
      </div>
    </section>
    <OnPremRuntimePanel agent={agent} model={model} models={models} modelId={modelId} onModelChange={setModelId} />
    <AgentDeployChat selectedProvider={agent.cloud} agentName={agent.name} modelId={modelId} model={model} />
  </>;
}
