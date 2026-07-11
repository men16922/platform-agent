# LinkedIn Demo + Test Scenario — On-Prem Agent (all natural language)

## Post copy

> What if your whole cluster lifecycle — build it, deploy to it, roll back, tear it down —
> was just a few plain-English sentences to a local agent, on your own hardware, with every
> tool call visible in real time?

## ~30-second video script (hero cut: one sentence → provision + deploy)

| Time | Screen | Narration |
|---|---|---|
| 0–3s | **Agents** → select **On-Prem Agent** | “로컬 LLM이, 클러스터부터 배포까지 직접 운영한다면?” |
| 3–6s | Selected Runtime: **Local Qwen → Supervisor → Provision/Deploy** | “모델을 선택하면 실행 경로와 권한 경계가 바로 결정됩니다.” |
| 6–9s | Enter the composite request below | “요청은 한 문장. 나머지는 에이전트가 스스로 계획합니다.” |
| 9–17s | Live trace — **Provision**: `provision_cluster` → node **Ready** | “먼저 클러스터를 만들고, 노드가 Ready가 될 때까지 확인합니다.” |
| 17–26s | Live trace — **Deploy**: `build_image` → `push_image` → `deploy` → `validate` → `1/1 Running` | “이어서 이미지를 빌드·푸시하고 배포한 뒤, 헬스까지 검증합니다.” |
| 26–30s | **History → click a row** — one page: provisioning on top, the deploy nested below | “모든 실행이 로그로 남고, 한 페이지에서 라이프사이클을 봅니다.” |

---

## Test scenario — everything by natural language

Every step is a plain-English message to the **On-Prem Agent** (no button clicking needed —
the UI just reflects what the agent did). It exercises: the Provisioning / Deployments /
**History** split, the `provider × environment` taxonomy, the single-row rollback lifecycle,
the **teardown cascade** (an app dies with its cluster), and the nested lifecycle detail.

### 0. Preconditions — clean slate + stack up

```bash
kind get clusters                        # (empty)
make dev-up                              # MLX + proxy + router(:8077) + dashboard(:3000)
make dev-status                          # all four "up"
: > ~/.platform-agent/activity.jsonl     # optional: clean the feed
```

> `make dev-up` runs the router from `examples/orders-api` (its Docker build context).
> Starting it from the repo root makes `deploy_service` fail with "Dockerfile missing".

Open `http://localhost:3000`, sign in (Local Dev **admin**), go to **Agents** →
**On-Prem Agent** + **Local Qwen**.

### 1. Provision + deploy — one sentence

```text
Provision an on-prem k8s cluster, then deploy orders-api to it and confirm it is healthy.
```

- **Trace**: `provision_cluster` → node Ready, then `build_image → push_image → deploy → validate` → `1/1 Running`.
- Recorded as **two rows**: **Provisioning** → `platform-agent` (kind, onprem/dev, success);
  **Deployments** → `orders-api` (v1.x, onprem/dev, success).

### 2. Roll back the app — natural language

```text
Roll back orders-api to the previous revision.
```

- The agent runs `rollback_deployment`. Tracking **supersedes the same row** in place:
  on **Deployments**, `orders-api` flips to **rolled-back** — no duplicate row.
- (UI equivalent: the **Rollback** button on the Deployments row — app-only.)

### 3. See the lifecycle — History → row → nested detail

Open **History** (left nav, under Deployments). Two sections: **Provisioning Logs** and
**Deployment Logs**, each paginated. Click any row (the whole row is the link):

- **Top**: the **Provisioning** for `platform-agent`.
- **Below**: **Deployments on this cluster** — `orders-api` expanded, showing
  `build → push → deploy → validate` **and** the appended `rollback_deployment` trace.
  Enter from a Deployment Log row → provisioning stays folded, only that deploy opens.

### 4. Tear down the cluster — natural language (cascade)

```text
Tear down the on-prem cluster.
```

- The agent runs `teardown_cluster` — and **every app on the cluster dies with it**, so the
  tracking cascades:
  - **Provisioning** → `platform-agent` flips to **rolled-back**.
  - **Deployments** → `orders-api` also flips to **rolled-back** automatically (removed with
    its cluster) — and its **Rollback button is disabled** (no cluster to roll back onto).
- Verify the cluster is really gone:

```bash
kind get clusters      # (empty again)
```

- (UI equivalent: the **Rollback** button on the **Provisioning** row — cluster teardown,
  which cascades the same way.)

### Recording tips

- LinkedIn hero cut: steps **1** then **3** — the one-sentence provision→deploy, then the
  nested lifecycle detail. Keep every tool call visible.
- Full walkthrough: **1 → 2 → 4**, cutting to Provisioning / Deployments / History after each
  sentence to show the split, the single-row rollback, and the teardown cascade.
- Zoom/crop to the runtime path and streamed reasoning/tool trace; hide unrelated panels.
