# STATUS — platform-agent

최종 갱신: 2026-07-11

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- 3-cloud AI Agent 실호출 완료: Bedrock Claude + Vertex AI Gemini 3.5 Flash + Azure OpenAI GPT-5.4.
- Capability-based runbook schema 구현 (cloud-neutral execution steps).
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- 4 provider 코드 완비: AWS / GCP / Azure / On-Prem.

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **536 passed, 1 skipped** (2026-07-11, 229.45s) — GCP Vertex AI mock/heuristic 연동 포함
- GCP Day2 tests → **28 passed** (Vertex AI mock/heuristic 연동, severity=P2, confidence=0.30)
- Dashboard → lint/build 성공; 11 routes (OG/Twitter image 포함); Vercel production 배포 완료 (2026-07-11)
- CDK → `platform-agent-activity` 테이블 + GSI1 CREATE_COMPLETE; Vercel OIDC read grant UPDATE_COMPLETE (2026-07-11)
- CDK → Vercel team/project-scoped OIDC provider + DynamoDB read-only role AWS 배포 완료 (2026-07-11)
- `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
- `python -m src.agents.ai.orchestrator` → E2E pipeline 7-step 성공 (dev/staging)
- Strands Agent + Bedrock Claude → 자율 4-tool 호출 → 실배포 ✅
- ADK Agent + Vertex AI Gemini 3.5 Flash → tool calling (gcp_build_image) ✅
- MSFT Agent + Azure OpenAI GPT-5.4 → tool calling (azure_build_image) ✅
- CDK deploy → 97 resources CREATE_COMPLETE (us-east-1, 2026-07-10)
- GCP: Artifact Registry push + GKE Autopilot 배포 (검증 후 정리)
- Azure: ACR push + AKS 배포 (검증 후 정리)
- 리소스: 전부 정리 완료 (비용 $0)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **3-Cloud Day2 Operations** — AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions). 각각 4-step 파이프라인 구현.
3. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
4. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
5. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
6. **Runbook registry** — built-in catalog + capability-based schema + CDK seed + scan heuristic.
7. **AI Agents** — Strands(Bedrock) + ADK(Gemini 3.5 Flash) + MSFT(GPT-5.4). 3종 tool calling 검증 완료.
8. **Guardian Agent** — Policy-as-Code (APPROVE/AUTO/REJECT).
9. **MCP + A2A Gateway** — kubectl/docker MCP (9 tools) + FastAPI A2A + Bridge.
10. **On-prem K8s** — `make local-cluster` (kind 테스트용) → 3노드 + registry + NGINX ingress.
11. **Deployment Adapters** — 4 provider (onprem/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
12. **Execution Adapters** — 4 provider: capability → provider-specific action resolution.
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지. AWS incident live/demo/fallback + deployment/activity durable read model (DynamoDB `platform-agent-activity` + GSI1) + Vercel OIDC 최소권한 read role. OG/Twitter image 배포 완료. Auth boundary 설계 완료, GitHub OAuth (Auth.js Phase 1) 연동 완료, Auth Phase 2/3 및 사용자 작용 UI 제어판(승인 카드, 배포 트리거 모달, 롤백 실행 버튼) 및 보안 감사 로그(Audit Logs) 조회 화면 전면 구현 및 배포 완료.

## Active Focus

- 대시보드 감사 로그(Audit Logs) 뷰어 화면 개발, 동적 사이드바 렌더링, 전용 보호 API 연동 및 프로덕션 배포 완료.

## Open Risks / Gaps

1. **CDK 재배포 시 Lambda bundling** — Docker 없이 로컬 pip 번들링 사용 중 (arm64↔amd64 주의).
2. **Slack App 미연결** — APPROVE 승인 버튼 코드+가이드+E2E 테스트 완비, 실 Slack App 미생성 (코드 ready). OIDC 연계를 통한 Slack Webhook 송출 정상 작동.
3. **GCP/Azure 실 클러스터** — WIF 자격증명 연동 모듈 및 GKE/Cloud Run/AKS 실 API 호출 러너 구현 완료 (테스트 검증 성공), 실 클러스터 비용 관리에 유의.
4. **Dashboard live dataset** — AWS live 연결 정상; `incident-history` 0건, `platform-agent-activity` 0건 (write path는 연동됨).
5. **Dashboard auth** — Auth.js Phase 1/2/3 구현 및 로컬 Next.js 컴파일/빌드 검증 성공.
6. **Dashboard dependency audit** — Next.js 16.2.10 내부 PostCSS 중간등급 취약점 2건; upstream release 대기.
