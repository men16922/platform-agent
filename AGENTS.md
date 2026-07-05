# AGENTS.md — platform-agent

## Project Overview

AWS-native platform agent. Not just alerting — it covers **provision → validate deploys → detect → analyze → decide → execute**.

- Domain agnostic: works with EKS, Kafka, RDS, Lambda, or any CloudWatch-instrumented service
- Built with a **harness** that orchestrates Claude Code (reasoning) + Codex (code generation)
- Directly tied to AWS SAP domains: Reliability, Operational Excellence, Cost Optimization

---

## Agent Architecture

```
Slack / Jira / GitHub / Alarm
              ↓
     Router / Harness
        ↓        ↓        ↓
 Provisioning  Deployment  Operations
```

---

## Directory Structure

```
platform-agent/
├── scripts/overnight/         # Overnight harness state (gate, settings, logs)
├── .claude/harness-config.json # Per-repo harness config
├── .kiro/                     # Kiro CLI agent profile + steering docs
├── .codex/rules/              # Codex permission rules
│
├── src/
│   ├── agents/
│   │   ├── adapters/
│   │   ├── provisioning/
│   │   ├── deployment/
│   │   ├── operations/
│   │   └── models.py
│   ├── stacks/           # CDK (TypeScript)
│   └── step_functions/   # State machine JSON
│
├── docs/
│   ├── engineering/      # Harness engineering bibles
│   ├── architecture.md
│   ├── agents.md
│   ├── models.md
│   └── portability.md
│
└── tests/
```

---

## Tech Stack

| Component     | Technology                  |
|---------------|-----------------------------|
| Orchestrator  | AWS Step Functions          |
| LLM           | Bedrock + harness clients  |
| Alarm ingest  | EventBridge + Lambda        |
| Log analysis  | CloudWatch Logs Insights    |
| Execution     | SSM Automation              |
| IaC           | CDK (TypeScript)            |
| Notifications | Slack Webhook               |

---

## Harness Engineering — Overnight Loop

This project uses the **[claude-overnight-harness](https://github.com/men16922/claude-overnight-harness)** plugin for unattended AI-assisted development.

The harness drives a headless coding agent one iteration at a time:
1. Restore context (`/sync`)
2. Implement ONE `[auto]` task from `docs/NEXT_PLAN.md`
3. Pass the gate (`pytest tests/ -v`)
4. Record progress (`/checkpoint`)
5. Local commit → next iteration

| Engine | Command |
|--------|---------|
| Claude | `MAX_ITER=1 make overnight-claude-once` |
| Codex | `MAX_ITER=1 make overnight-codex-once` |
| opencode | `MAX_ITER=1 make overnight-opencode-once` |
| AGY | `AGY_PRINT_TIMEOUT=30m MAX_ITER=1 make overnight-agy-once` |
| Kiro | `KIRO_AGENT=overnight-harness MAX_ITER=1 make overnight-kiro-once` |

Safety: each iteration verifies the gate externally; consecutive failures trigger auto-stop.

**Fallback:** All engines use the same backlog, gate, and sentinel interface. Swap engines freely.

---

## Key Design Decisions (SAP Alignment)

| Decision | SAP Exam Angle |
|----------|----------------|
| Step Functions over SWF | SWF vs Step Functions comparison |
| EventBridge over SNS for alarm trigger | Event routing patterns |
| Multi-region failure handling in Executor | DR design, RTO/RPO |
| Executor Agent IAM scope | Least Privilege |

When making architecture decisions, default to the SAP-aligned reasoning: explain *why* a service was chosen, not just *what* it does.

---

## Development Guidelines

- **Do not add features beyond what is asked.** Stick to the detect → analyze → decide → execute pipeline.
- **IaC is CDK (TypeScript).** Do not introduce Terraform or CloudFormation raw templates.
- **Agents are Python.** Harness layer is Python; CDK stacks are TypeScript.
- **IAM: least privilege always.** Executor Agent IAM roles must be scoped to minimum required actions.
- **No mocking AWS services in tests.** Use localstack or real AWS test accounts for integration tests.
- **Step Functions state machine** lives in `src/step_functions/` as JSON. Keep it in sync with CDK stack definitions.

---

## Goals

1. Functional end-to-end pipeline (request/alarm → deploy/operate → Slack report)
2. GitHub README ready for public release post-SAP
3. LinkedIn article: "platform-agent — your always-on platform engineer"
4. Medium article: "Harness Engineering: orchestrating Claude Code + Codex to overcome context limits"
