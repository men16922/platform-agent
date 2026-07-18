# Giving an Autonomous Platform Agent Hands — and the Guardrails to Use Them

*How we built a multi-cloud, on-prem-capable platform operations agent that provisions clusters, ships deployments, and remediates incidents by itself — and the deterministic guardrails that keep an LLM from doing something it can't take back.*

---

## TL;DR

`platform-agent` is an AWS-native (but cloud-neutral) agent that handles both **Day 1** (provision → build → deploy → validate) and **Day 2** (detect → analyze → decide → execute → report) for Kubernetes platforms across **AWS, GCP, Azure, and on-prem**. A single natural-language sentence — *"provision an on-prem cluster, then deploy orders-api and confirm it's healthy"* — becomes a planned, traced, approval-gated sequence of real infrastructure actions.

The interesting part isn't that an LLM can call tools. It's the **guardrails**: a reconciliation gate that refuses to act on facts the model can't ground in tool output, a self-consistency vote on routing, budget gates, circuit breakers, per-tool kill-switches, and graceful cross-account fallback. This post walks through the architecture and the engineering principles behind it, verified by **842 passing tests** and live end-to-end runs on three real clouds.

---

## The problem

Autonomous agents that only summarize text are low-stakes. Agents that run `kubectl scale`, `terraform apply`, or `create_agent_runtime` against a production account are not. The moment you give an agent hands, two questions dominate every design decision:

1. **How do you keep it from acting on a hallucination?** An LLM that decides "this is a P1 incident, auto-restart the deployment" based on a root cause it invented is worse than no automation at all.
2. **How do you make the hard-to-reverse actions safe?** Deleting a cluster, tearing down a runtime, or scaling to zero must never happen on the model's say-so alone.

Everything below is, in one way or another, an answer to those two questions.

---

## Architecture at a glance

The system is organized around one pattern: **`ServiceSpec` (declarative intent) → capability → environment-native adapter**. The agent interprets intent; adapters translate a cloud-neutral capability (e.g. "provision a cluster", "roll back a deployment") into the provider's native mechanism.

| Layer | AWS | GCP | Azure | On-Prem |
|---|---|---|---|---|
| **Provision (IaC)** | CDK / Terraform | gcloud / Terraform | az / Terraform | Terraform + Ansible |
| **Cluster** | EKS | GKE | AKS | kind · k3s · kubeadm |
| **Build → Push** | CodeBuild → ECR | Cloud Build → AR | ACR Tasks → ACR | docker build → registry |
| **Deploy → Validate** | kubectl → EKS + health | kubectl → GKE | kubectl → AKS | kubectl → local |
| **Deploy Agent** | Strands + Bedrock Claude | ADK + Gemini 3.5 Flash | MSFT SDK + Azure GPT‑5.4 | Pydantic AI + Local Qwen (MLX) |
| **Managed Runtime** | Bedrock AgentCore | Vertex AI Agent Engine | Foundry Agent Service | kagent (CNCF) |
| **Day‑2 (Event / Orch)** | EventBridge / Step Functions | Pub/Sub / Cloud Workflows | Event Grid / Durable Functions | Webhook / Temporal |

Two design consequences fall out of this table:

- **The pipeline engine is cloud-independent** — pure Python, no cloud SDK dependency, so it runs identically on a laptop, a CI runner, a Lambda, or a Cloud Function.
- **The hosting layer is swappable** — AWS (EventBridge + Lambda) is one implementation of the event-ingestion contract; GCP, Azure, and on-prem follow the same shape.

### Model ↔ environment separation

The "Deploy Agent" column shows each cloud's *recommended native* pairing, but the brain (model) and the target (environment) are deliberately decoupled by an **AI Model Router**. Any model can drive a deployment to any environment; the router just annotates fit. This is what lets the same natural-language flow run on Bedrock Claude in the cloud and a local MLX-hosted Qwen offline.

### On-prem, fully offline

The on-prem path is a first-class citizen, not a demo stub. A **local Qwen 7B** (served through an MLX tool-call proxy) drives a complete `provision → deploy → validate` cycle in ~39 seconds, records runs to a local JSONL store, and the dashboard merges those with cloud DynamoDB records into one **hybrid** view. Rollback (app `rollout undo` and cluster teardown) works entirely offline. No internet, no cloud account, full lifecycle.

---

## The engineering spine: adapting a reference the honest way

Here's where it gets opinionated. We took a public AWS reference — the **AWSome AI Gateway** (`aws-samples`, MIT-0), an internal *LLM proxy gateway* with virtual keys, budgets, and multi-account Bedrock routing — and asked: *its product purpose is different from ours, but which of its patterns are worth adopting for a platform ops agent?*

The answer was: not the LLM-proxy parts, but the **governance, resilience, and orchestration** patterns. We mapped each one to a concrete component and shipped it in tiers. Every feature is **opt-in and non-breaking** — the default behavior is unchanged, and each capability engages only when an operator turns it on. That constraint forced clean seams and made everything testable offline.

### Tier 1 — governance & resilience

**1. Reconciliation gate (deterministic-tool-first).** This is the direct answer to question #1. Before an autonomous `decide → execute` runs, a pure-Python gate checks that the analyzer's `severity` and `root_cause` are actually *grounded* in the detector's evidence — firing alarm state, metrics, logs, and token-overlap between the claimed root cause and the observed evidence. If the conclusion is ungrounded, the decision is **downgraded from AUTO to APPROVE** — a human must sign off. An LLM can suggest, but it cannot act on a fact it can't point to in tool output. This is the last line of defense now that the on-prem executor can issue real `kubectl` (gated behind `ONPREM_EXECUTOR_LIVE`).

**2. Three-stage budget gate.** `evaluate_budget()` classifies spend against `PLATFORM_MONTHLY_BUDGET_USD`: `OK` → `SOFT_WARNING` (≥80%) → `THROTTLE` (≥100%, requires approval) → `HARD_BLOCK` (≥150%). Cost is a policy input, not an afterthought.

**3. Circuit breaker + readiness gate.** A `CLOSED / OPEN / HALF_OPEN` breaker with fail-fast and fallback (injectable clock, so the state machine is deterministically testable), plus a strict `/health/ready` (503 when a dependency is down) separated from a lenient `/health` (200 liveness).

**4. Cost sub-metrics.** Every trace is aggregated into per-tool call counts, reasoning steps, and token usage, attached to the activity record — so "what did that autonomous run actually cost" is answerable.

### Tier 2 — orchestration & multi-account

**#2 Agents-as-tools + self-consistency.** The router started as a deterministic keyword classifier: one sentence → one specialist (provision / deploy / diagnostics), delegated over A2A. Tier 2 adds an orchestrator layer *above* it that (a) **votes on the route** — sampling the classifier N times and taking the majority, and (b) **chains specialists as tools** — decomposing a compound request into an ordered plan, delegating each step through the existing delegation path, short-circuiting on the first failure, and threading a shared context across steps.

The subtle part is the **fallback**: when the sampled votes disagree too much to trust (agreement below threshold), the router doesn't guess — it falls back to the deterministic classifier. This is the *same philosophy as the reconciliation gate*: a deterministic backstop always wins over an unsupported model call. And because the default sampler *is* the deterministic classifier, turning the feature on with defaults changes nothing until you inject a real (LLM) sampler.

**#3 MCP-over-HTTP connector + kill-switch.** The gateway exposes kubectl/docker as MCP tools from a single catalog. Tier 2 adds a `remote_mcp_tool()` factory that registers a *remote* MCP server (web search, an external API) as a catalog tool: the handler intercepts the local tool-use, forwards it as a JSON-RPC `tools/call` over HTTP, and reinjects the result — degrading to an error result instead of raising if the remote is down. Every tool, local or remote, is governed by a **per-tool and global kill-switch** (`disable_tool` / `set_kill_switch`, or `MCP_DISABLED_TOOLS` / `MCP_KILL_SWITCH`) checked at dispatch: a blocked tool returns a refusal without ever executing. One environment variable can cut off a single capability — or the whole gateway.

**#4 Cross-account STS AssumeRole + graceful fallback.** For operating across AWS accounts, `assume_role_session()` assumes a role in the target account and builds a boto3 session from the temporary credentials. If the AssumeRole fails — AccessDenied, throttling, a broken trust policy — or if the shared circuit breaker is already open after repeated failures, it **degrades gracefully to in-account credentials** rather than failing the whole operation. It reuses the Tier 1 circuit breaker rather than reinventing resilience; `fallback=False` is available for callers that must never silently run in the wrong account.

---

## The principles underneath

Strip away the feature names and the same handful of principles recur:

- **Deterministic backstop over model output.** The reconciliation gate and the self-consistency fallback both encode the same rule: when the model is unsupported or self-inconsistent, a deterministic path decides. LLMs propose; verified logic disposes.
- **Approval gates for hard-to-reverse actions.** Anything `Delete / Drop / Terminate / teardown` — cluster provisioning, runtime hosting, scale-to-zero — is forced through explicit approval. The autonomous path is deliberately the *reversible* subset (restart, rollback, scale-up, polite drain that respects PodDisruptionBudgets).
- **Opt-in, non-breaking.** Every Tier 1/2 feature ships dark by default. New behavior engages only behind an env flag or an injected dependency, so adoption never risks the existing path — and the regression tests prove the default is unchanged.
- **Injectable seams, offline-testable.** Transports, STS clients, samplers, clocks, and card-fetchers are all injectable. There's no moto, no live-cloud requirement in the unit suite — a fake is monkeypatched into a module-level seam. That's why 842 tests run in minutes.
- **Reuse over reimplement.** The circuit breaker written for Tier 1 resilience is the *same* object that powers Tier 2's cross-account fallback. Patterns compound instead of duplicating.

---

## Verification culture

None of the above is "done" until it's exercised:

- **`make check` → 842 passed, 1 skipped.** Every feature lands with tests, and the gate runs on every multi-file change.
- **Live, on real clouds.** Managed agent-runtime hosting was proven end-to-end on all three clouds — AgentCore, Vertex Agent Engine, and Azure AI Foundry each did a real `create → invoke/query → teardown` with genuine model responses, then immediate deletion (each under \$0.50). Provisioning parity was proven with a real AKS cluster (create → Ready → teardown).
- **A2A against a real peer.** The supervisor discovers and delegates to a real kagent agent (local MLX Qwen) over A2A — Agent Card discovery → skill match → JSON-RPC delegation → a real `k8s_get_resources` diagnostic came back. That live run even surfaced a spec-compliance bug (a missing required `messageId`) that the lenient in-house gateway had masked.

---

## The same thesis, now shipping from the platform vendors

We built these guardrails because they were the only way we'd trust an agent with `kubectl`. It's worth noting that the major agent platforms are converging on the same conclusions.

- **Google's ADK 2.0** introduces "Agentic Workflows" — a directed-graph runtime that reserves the LLM for genuine reasoning and runs routing, conditional branching, and error handling as deterministic code, explicitly to gain reliability and to mitigate prompt injection by decoupling execution control from the model. That is our reconciliation gate and self-consistency fallback restated as a framework primitive: *deterministic control plane, LLM for cognition only.*
- **The A2A protocol's** "zero context pollution" property — specialist peers manage their own state so the primary agent's context window stays clean — is exactly why our delegation sends each specialist only its own instruction and treats the A2A `contextId` as a correlation key, never a growing context blob.
- **Google's `agents-cli`** makes an eval loop (dataset + LLM-as-judge + optimize) first-class alongside the build — a useful reminder that deterministic *tests* (our `make check`) and *decision-quality evaluation* are different layers. We've since shipped the latter too: an offline eval harness with multi-grader scorecards, whose live model sweep replaced a "bigger model for routing" assumption with measured evidence — a 7B beat a 30B on both accuracy and speed.

The point isn't that anyone copied a side project — it's that when independent teams give an LLM real hands, they reach for the same deterministic guardrails. Convergence is a good sign the design is right, not a novelty.

*References: Google Developers Blog — [Why we built ADK 2.0](https://developers.googleblog.com/why-we-built-adk-20/), [How A2A is building a world of collaborative agents](https://developers.googleblog.com/how-a2a-is-building-a-world-of-collaborative-agents/); [`google/agents-cli`](https://github.com/google/agents-cli).*

---

## Closing

The headline feature of an agentic platform tool is autonomy. The *shippable* feature is trust. Most of the engineering in `platform-agent` went not into teaching the model to call more tools, but into the boundaries around those calls: grounding conclusions in evidence, voting on decisions, gating cost, breaking circuits, killing switches, and always keeping a deterministic path that wins when the model is unsure.

Adopting a reference well meant ignoring most of it and adapting the few patterns that transferred — governance, resilience, orchestration — to a product it was never written for. The result is an agent you can actually let touch real infrastructure, because you've decided in advance exactly what it's allowed to do without asking.

---

*Companion demo (≈20s, all natural language): the on-prem agent provisioning a cluster and deploying to it, every tool call visible in real time — see `docs/post/local-onprem-edited.mp4`.*
