# platform-agent Helm chart (reference #7 — production packaging)

Packages the **On-Prem control plane** for a real cluster, with the same
safe-by-default posture as the codebase:

| Component | Default | What it is |
|---|---|---|
| `webhook` | **on** | Day-2 plane: Alertmanager → in-process detect→analyze→decide→execute with P1/P2/P3 approval gating (`onprem_webhook_api`) |
| `router` | off | Deploy front door + SSE (`local_deploy_api`); build/push steps need external tooling, so opt-in |
| RBAC | on, **drain off** | Least-privilege verbs for the four reversible actions — never `"*"` |
| `ONPREM_EXECUTOR_LIVE` | `false` | log-only until you arm it (`webhook.executorLive=true`) |

## Layout: env × substrate

- `values.yaml` — safe defaults
- `values-kind.yaml` — kind substrate (host MLX via `host.docker.internal`)
- `values-k3s.yaml` — k3s substrate (`local-path` storage, LAN host IP for the LLM)

```sh
# build the image the chart runs (repo root)
docker build -f infra/onprem/Dockerfile -t platform-agent:0.1.0 .
kind load docker-image platform-agent:0.1.0   # kind substrate

helm install pa infra/helm/platform-agent -f infra/helm/platform-agent/values-kind.yaml
```

## Probes match the resilience pattern (Tier 1 #6)

Liveness hits lenient `/health` (200 while the process lives); readiness hits
strict `/health/ready` (503 while the circuit breaker is OPEN) — so a tripped
breaker drains traffic without the kubelet restarting the pod.

## RBAC model

- Namespaced `Role`: `deployments` get/list/patch, `deployments/scale`
  get/patch, `replicasets` get/list — exactly restart/undo/scale.
- Cluster-scoped drain (`nodes` cordon, `pods/eviction` create) is a **separate
  ClusterRole behind `webhook.rbac.allowDrain`**, default off: a base install
  cannot touch nodes at all.

## Known single-writer constraint

Activity/approvals/incidents persist to JSONL on one RWO volume — `replicas: 1`,
`strategy: Recreate`, and the router (if enabled) is affinity-pinned to the
webhook's node. Multi-replica needs the State Store roadmap item
(PostgreSQL/Redis), not RWX workarounds; the chart deliberately packages what
ships today.
