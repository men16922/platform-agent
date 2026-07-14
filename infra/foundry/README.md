# Azure AI Foundry — agent-runtime hosting setup

The GCP/AWS hosting targets ship a packaged artifact (`infra/agentcore` container,
`infra/agentengine` agent class). Azure AI Foundry prompt agents are **declarative**
(model deployment + instructions), so there is no artifact to build — the runtime
adapter's `host_agent` creates the agent from `spec.extra['model']` + instructions.
This file records the one-time account/project/model setup and the non-obvious
gotchas hit while wiring it live.

## One-time setup (az CLI)

```bash
RG=platform-agent-foundry-rg; ACCT=pa-foundry-908601; REGION=eastus; PROJ=pa-project

# 1. resource group + Foundry (AIServices) account
az group create -n $RG -l $REGION
az cognitiveservices account create -n $ACCT -g $RG -l $REGION \
  --kind AIServices --sku S0 --custom-domain $ACCT --yes

# 2. Foundry project (data-plane endpoint lives under the account)
az cognitiveservices account project create -n $ACCT --project-name $PROJ -g $RG -l $REGION

# 3. model deployment (pick a CURRENT model + its supported SKU; see gotchas)
az cognitiveservices account deployment create -g $RG -n $ACCT \
  --deployment-name gpt-mini --model-name gpt-5.4-mini --model-version 2026-03-17 \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10

# 4. data-plane RBAC — REQUIRED (see gotchas); subscription Owner is control-plane only
az role assignment create \
  --assignee-object-id <your-object-id> --assignee-principal-type User \
  --role "Cognitive Services User" \
  --scope "$(az cognitiveservices account show -n $ACCT -g $RG --query id -o tsv)"
```

Project endpoint for the adapter / `AZURE_AI_PROJECT_ENDPOINT`:
`https://<account>.services.ai.azure.com/api/projects/<project>`

## Gotchas (all hit live)

1. **Data-plane RBAC is separate from Owner.** Subscription Owner grants control-plane
   `actions` but no `dataActions`, so agent calls return `does not have permissions for
   .../agents/read`. Assign **"Cognitive Services User"** (dataAction `Microsoft.CognitiveServices/*`)
   on the account scope. "Azure AI User" does not exist in every tenant.
2. **MSA/personal accounts + role assignment.** `--assignee <guid>` triggers a Graph
   lookup that fails for personal Microsoft accounts. Use `--assignee-object-id <guid>
   --assignee-principal-type User` to skip it.
3. **Model deprecation.** `gpt-4o-mini` / `gpt-4.1-mini` were in a deprecating state and
   rejected for *new* deployments. Use a current model (e.g. `gpt-5.4-mini`) and its
   supported SKU — `gpt-5.4-mini` needs `GlobalStandard`, not `Standard`.
4. **Agent name charset is the OPPOSITE of AgentCore.** Foundry requires
   alphanumeric + hyphens (`platform-agent-deployer`); AgentCore requires underscores
   (`platform_agent_deployer`).
5. **Invocation is the OpenAI Responses API**, not a `.query()`. Use
   `project_client.get_openai_client().responses.create(input=..., extra_body={
   "agent_reference": {"type": "agent_reference", "name": "<agent>"}})`. The older
   `{"agent": ...}` key is deprecated.

## SDK note

The runtime adapter targets `azure-ai-projects` **v2** (2.3.0+): agents are named,
versioned resources — `agents.list()`, `agents.create_version(agent_name,
definition=PromptAgentDefinition(model, instructions))`, `agents.delete(name)`.
The pre-2.0 `create_agent` / `list_agents` API is a different, incompatible surface.
