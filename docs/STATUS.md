# STATUS — platform-agent

최종 갱신: 2026-07-12

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

- `make check` (pytest) → **600 passed, 1 skipped** (2026-07-12) — AI Model Router / Pydantic AI On-Prem 에이전트 / MLX proxy / deploy recorder(+cascade) / ops_tools / provisioning 어댑터 테스트 포함
- **LinkedIn 데모 비디오 편집(2026-07-12)** → `docs/post/local-onprem.mov` 원본 영상을 18.2초(1.0MB)로 구간 및 배속(타임랩스) 편집하고, 각 7개 주요 구간의 자막(Terraform 등 실제 실행 매핑)을 영상 하단에 병합한 `local-onprem-edited.mp4` 제작 완료.
- **배포 추적 IA 정리(2026-07-12)** → activity에 `type`(provision/deploy)·`cluster`(연결키)·`environment`(provider와 분리) 저장; 대시보드 **Provisioning/Deployments/History** 3분리 + **통합 중첩 상세**(provisioning⊃deployments); 롤백 **단일-row 승계**, **cluster teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅; `make dev-up` 한 방 기동. tsc0+next build 성공, `/provisioning`·`/history` 200. **라이브 실증은 미완(사용자 테스트 예정)**.
- **On-Prem 오프라인 완결(2026-07-12)** → Local Qwen **7B**로 NL provision→deploy→validate **~39s** 자율 실증; `deploy_recorder` **로컬 JSONL** 기록 + 대시보드 **hybrid**(AWS DynamoDB + On-Prem JSONL 병합) read; `/api/local-rollback`로 **app 롤백(rollout undo v2→v1)·cluster 롤백(teardown)** 실증. `mlx_qwen_tool_proxy`가 7B의 ```json/Hermes tool-call 파싱, `deploy_service` 복합툴로 LLM 왕복 축소.
- **범용 On-Prem Ops 에이전트** → provision(2)+deploy(5)+investigate(5) 12도구, reasoning+tool SSE 스트리밍, "list pods" 질의는 진단만 수행 확인
- **On-Prem Provision(① 역할)** → Terraform(kind) IaC `validate/plan` green + Ansible(k3s) 실 Multipass VM 적용: k3s v1.31.4 node Ready, 재실행 idempotent(`changed=0`); `provision_cluster`/`teardown` 에이전트 도구
- **관측성** → 배포 상세 페이지 `/deployments/[id]`(reasoning/tool args·result/summary) + DynamoDB trace 기록
- **kagent + local Qwen** → kind Pod→`host.docker.internal:18091/v1` OpenAI-compat ModelConfig 적용, `k8s-agent` A2A JSON-RPC 진단 task가 tool 결과 반환까지 실증.
- **Supervisor + A2A** → 자연어 요청을 provision/deploy/kagent로 분류하고 Agent Card discovery/skill match 후 해당 transport(JSON-RPC 포함)로 위임; Gateway 응답에 route trace 기록.
- **Dashboard Agents UX** → Agent → AI Model → Selected Runtime → Ask Agent 단일 흐름, 실제 model brand asset과 On-Prem router 상태 패널 추가; `next build` 성공.
- AI Model Router → `/api/models`(환경별 선택지) + `/api/local-deploy`(자연어 배포) live 확인; 대시보드 `tsc`+`next build` 통과
- **Live E2E (Pydantic AI + MLX Qwen3-Coder-30B)** → 자연어 "Deploy orders-api ..." → build→push→deploy→validate 자율 실행 → kind `orders-api 1/1 Running`(image v1.5.0) 검증 완료 (2026-07-11)
- **Deployments Live 추적 배선 완성** → 기록 활성 API 배포 → recorder가 DEPLOY/ACTIVITY(DEP-262AC0A3, v1.6.0) DynamoDB 기록 → 대시보드 `/api/dashboard/deployments`(aws-live)가 최신 배포로 노출 확인 (2026-07-11)
- Strands + Bedrock 이전 baseline: `make check` 544 passed (2026-07-11, 237.23s)
- GCP Day2 tests → **28 passed** (Vertex AI mock/heuristic 연동, severity=P2, confidence=0.30)
- Dashboard → lint/build 성공; 11 routes (OG/Twitter image 포함); Vercel production 배포 완료 (2026-07-11)
- CDK → `platform-agent-activity` 테이블 + GSI1 CREATE_COMPLETE; Vercel OIDC read grant UPDATE_COMPLETE (2026-07-11)
- CDK → Vercel team/project-scoped OIDC provider + DynamoDB read-only role AWS 배포 완료 (2026-07-11)
- `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
- `python -m src.agents.ai.orchestrator` → E2E pipeline 7-step 성공 (dev/staging)
- Strands Agent + Bedrock Claude → 자율 4-tool 호출 → 실배포 ✅
- Strands Agent + Qwen3-Coder (via tool proxy) → 로컬 kind 클러스터 자율 4-tool 배포 E2E 성공 ✅
- ADK Agent + Vertex AI Gemini 3.5 Flash → tool calling (gcp_build_image) ✅
- MSFT Agent + Azure OpenAI GPT-5.4 → tool calling (azure_build_image) ✅
- GCP/Azure 실 REST API 연동 및 OIDC 페더레이션 크레덴셜 자격증명 모듈 구현 & 테스트 완료 (2026-07-11) ✅
- AWS/GCP/Azure 다중 리전 및 백업 클러스터 자동 우회 복구(Multi-region Failover) 구현 & 테스트 완료 (2026-07-11) ✅
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
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지. AWS DynamoDB 연동 완료. 모든 데모 목업 데이터를 제거하고 실시간 Live 모드만 활성화. 🔐 Auth.js 기반 GitHub OAuth, Admin/Operator/Viewer 역할 부여 및 사용자 권한 관리 제어판(잠금 방지 보호 포함), 장애 복구 승인(Pending approvals), 신규 배포 트리거/롤백 액션 패널, 보안 감사 로그(Audit Logs) 뷰어 화면 프로덕션 배포 완료.

## Active Focus

- 범용 Ops 에이전트 + 관측성 + On-Prem Provision(Terraform/Ansible) + kagent 설치 완료. ARCHITECTURE 통합·최신화(단일 스택 표 + Orchestrator+A2A 타깃).
- On-Prem 오프라인 기록/hybrid 대시보드/실 롤백 + Local Qwen 7B 전환 완료(2026-07-12).
- **배포 추적 IA 정리 완료(2026-07-12, 미커밋)**: Provisioning/Deployments/History 분리 + 중첩 상세 + 롤백 단일-row/teardown cascade + 자연어 라우팅 + `make dev-up`. gate 600 passed.
- 다음: 자연어 4스텝(provision+deploy→app rollback→History 상세→teardown cascade) **라이브 실증** → 전체 커밋 → 브랜치 push/머지 결정, 이후 AWS CDK live diff/kagent 정리.
- **미커밋/미푸시**: 이번 IA 정리분은 워킹트리에만 존재(신규 5파일 포함). 기존 기능은 `0b9148c`(브랜치 `feat/onprem-offline-recording-hybrid-rollback`), origin 미푸시.

## Open Risks / Gaps

1. **CDK 재배포 시 Lambda bundling** — Docker 없이 로컬 pip 번들링 사용 중 (arm64↔amd64 주의).
2. **Slack App 미연결** — APPROVE 승인 버튼 코드+가이드+E2E 테스트 완비, 실 Slack App 미생성 (코드 ready). OIDC 연계를 통한 Slack Webhook 송출 정상 작동.
3. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
4. **Dashboard dependency audit** — Next.js 16.2.10 내부 PostCSS 중간등급 취약점 2건; upstream release 대기.
5. **A2A endpoint/card discovery** — supervisor의 환경변수 endpoint 등록은 구현됐지만 실제 kagent endpoint와 Agent Card 기반 discovery/skill 매칭은 아직 연결 전.
6. **추적 IA 라이브 실증 미완** — Provisioning/Deployments/History·중첩 상세·롤백 단일-row·teardown cascade·자연어 라우팅은 빌드/유닛(600 passed)만 통과. 로그인 후 브라우저에서 자연어 4스텝 end-to-end 클릭/실행 실증 필요(코드·라우트 체인은 준비됨). 레거시 activity 행은 `cluster` 없어 롤백 비활성 — 클린슬레이트는 `~/.platform-agent/activity.jsonl` 비우기.
7. **NEXT_PUBLIC 프로덕션 인라인** — `next start`(Turbopack 빌드)에서 `NEXT_PUBLIC_DASHBOARD_DEV_AUTH`가 인라인 안 됨 → 로컬은 `next dev` 사용 중. 프로덕션 로컬로그인 필요 시 조사 요.
