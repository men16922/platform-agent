# STATUS — platform-agent

최종 갱신: 2026-07-09

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- 3-cloud AI Agent 실호출 완료: Bedrock Claude + Vertex AI Gemini 3.5 Flash + Azure OpenAI GPT-5.4.
- Capability-based runbook schema 구현 (cloud-neutral execution steps).
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- 4 provider 코드 완비: AWS / GCP / Azure / On-Prem (kind).

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **352 passed** (2026-07-09, 0.57s)
- `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
- `python -m src.agents.ai.orchestrator` → E2E pipeline 7-step 성공 (dev/staging)
- Strands Agent + Bedrock Claude → 자율 4-tool 호출 → 실배포 ✅
- ADK Agent + Vertex AI Gemini 3.5 Flash → tool calling (gcp_build_image) ✅
- MSFT Agent + Azure OpenAI GPT-5.4 → tool calling (azure_build_image) ✅
- CDK deploy → 97 resources CREATE_COMPLETE (현재 스택 삭제, 재배포 가능)
- GCP: Artifact Registry push + GKE Autopilot 배포 (검증 후 정리)
- Azure: ACR push + AKS 배포 (검증 후 정리)
- 리소스: 전부 정리 완료 (비용 $0)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
3. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
4. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
5. **Runbook registry** — built-in catalog + capability-based schema + CDK seed + scan heuristic.
6. **AI Agents** — Strands(Bedrock) + ADK(Gemini 3.5 Flash) + MSFT(GPT-5.4). 3종 tool calling 검증 완료.
7. **Guardian Agent** — Policy-as-Code (APPROVE/AUTO/REJECT).
8. **MCP + A2A Gateway** — kubectl/docker MCP (9 tools) + FastAPI A2A + Bridge.
9. **On-prem K8s (kind)** — `make local-cluster` → 3노드 + local registry + NGINX ingress.
10. **Deployment Adapters** — 4 provider (local/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
11. **Execution Adapters** — 4 provider: capability → provider-specific action resolution.

## Active Focus

- docs 현행화 + GitHub push 완료
- 다음: Slack interactive buttons (App 생성 + E2E)

## Open Risks / Gaps

1. **CDK 재배포 시 Lambda bundling** — Docker 없이 로컬 pip 번들링 사용 중 (arm64↔amd64 주의).
2. **Slack App 미연결** — APPROVE 승인 버튼은 코드+가이드 완비, 실 Slack App 미생성.
3. **GCP/Azure 실 클러스터** — tool calling 검증 완료, 실 인프라(GKE/AKS) 배포는 비용 때문에 필요 시 수행.
