# STATUS — platform-agent

최종 갱신: 2026-07-05

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- Slack interactive approval이 Step Functions callback까지 연결됨.
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- Kiro CLI 특화: 3개 에이전트(overnight-harness, aws-ops, cdk-dev) + safety hook + AWS MCP Server.
- AWS portability runtime seam 연결됨. 비-AWS(GCP/Azure/on-prem)는 scaffold+테스트 단계.

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **329 passed** (2026-07-06, 1.24s)
- `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
- `python -m src.agents.provisioning examples/orders-api.yaml` → 유효한 K8s YAML
- `python -m src.agents.ai.orchestrator` → E2E pipeline 7-step 성공 (dev/staging)
- Strands Agent + Bedrock Claude Haiku → 자율 4-tool 호출 → 실배포
- CDK deploy → 97 resources CREATE_COMPLETE (EventBridge+StepFunctions+Lambda+DynamoDB)
- GCP: Artifact Registry push + GKE Autopilot 배포 ✅
- Azure: ACR push + AKS 배포 ✅
- 클라우드 배포: 전부 정리 완료 (비용 $0 복귀)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
3. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
4. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
5. **Runbook registry** — built-in catalog + CDK seed + scan heuristic + schema validation.
6. **Overnight harness** — overnight-harness 플러그인 기반. `make overnight` / `make overnight-kiro-once`.
7. **Kiro CLI 에이전트** — aws-ops(운영 디버깅), cdk-dev(CDK 전용), overnight-harness(자동 루프).
8. **AWS MCP Server** — agent-toolkit-for-aws, mcp-proxy-for-aws@1.6.3, profile: q-user.
9. **On-prem K8s (kind)** — `make local-cluster` → 3노드 + local registry + NGINX ingress.
10. **Deployment Adapters** — 4 provider (local/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
11. **Manifest Generator** — ServiceSpec YAML → K8s Deployment/Service/Ingress.

## Active Focus

- 로드맵 주요 항목 완료 (Task 1~9 + 3-cloud E2E)
- 다음: Slack interactive buttons / ADK·MSFT LLM 실호출 / 아키텍처 다이어그램

## Open Risks / Gaps

1. **CDK 재배포 시 Lambda bundling** — Docker 없이 로컬 pip 번들링 사용 중 (arm64↔amd64 주의).
2. **비-AWS AI Agent LLM 미호출** — ADK(Gemini)/MSFT(GPT-4o) 실제 LLM 호출 미검증 (API key 필요).
3. **Slack App 미연결** — APPROVE 승인 버튼은 코드만 존재, 실 Slack App 미생성.
