# LinkedIn Demo Script — On-Prem Agent (Cluster → Deploy, ~30s)

## Post copy

> What if one natural-language request could build your Kubernetes cluster *and* deploy your app — on your own hardware, with every decision and tool call visible in real time?

## ~30-second video script

| Time | Screen | Narration |
|---|---|---|
| 0–3s | **Agents** → select **On-Prem Agent** | “로컬 LLM이, 클러스터부터 배포까지 직접 운영한다면?” |
| 3–6s | Selected Runtime: **Local Qwen → Supervisor → Provision/Deploy** | “모델을 선택하면 실행 경로와 권한 경계가 바로 결정됩니다.” |
| 6–9s | Enter the request below | “요청은 한 문장. 나머지는 에이전트가 스스로 계획합니다.” |
| 9–17s | Live trace — **Provision**: `provision_cluster` (Terraform/Ansible) → node **Ready** | “먼저 k3s 클러스터를 만들고, 노드가 Ready가 될 때까지 확인합니다.” |
| 17–26s | Live trace — **Deploy**: `build_image` → `push_image` → `deploy` → `validate` → Pod `1/1 Running` | “이어서 이미지를 빌드·푸시하고 배포한 뒤, 헬스까지 검증합니다.” |
| 26–30s | On-Prem runtime panel + completed reasoning/tool trace | “클라우드에 보내지 않는, 항상 켜진 플랫폼 엔지니어. platform-agent.” |

## Demo request

```text
Provision an on-prem k8s cluster, then deploy orders-api to it and confirm it is healthy.
```

## Recording notes

- Start on `/agents` with **On-Prem Agent** and **Local Qwen** selected.
- Let the trace show the two phases end-to-end: **provision** (`provision_cluster` → node Ready) then **deploy** (build → push → deploy → validate → `1/1 Running`).
- Zoom/crop to the runtime path and streamed reasoning/tool trace; do not show unrelated dashboard panels.
- If timing runs long, trim the reasoning narration but keep every tool call visible — the point is the autonomous provision→deploy chain.
