# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-11

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-11 — Supervisor 요청 라우팅 + A2A 위임 경계

- Status: Orchestrator(supervisor)의 최소 수직 슬라이스 구현 — 자연어 요청을 provision/deploy/kagent 역할로 분류하고, 등록된 specialist endpoint로만 A2A `message:send` 위임.
- Changed: `supervisor.py`(결정·trace·표준 HTTP A2A client), Gateway A2A Server의 route trace artifact, `PLATFORM_{PROVISION,DEPLOY,KAGENT}_A2A_URL` 환경변수 registry, 라우팅/위임/안전한 미등록 상태 테스트 추가.
- Verified: `pytest tests/test_supervisor.py tests/test_gateway.py -v` → 37 passed. 전체 `pytest tests/ -q`는 외부 pytest 런타임에서 종료 출력이 확보되지 않아 baseline 갱신 없이 유지.
- Blockers: 실제 kagent A2A endpoint 및 Agent Card discovery/skill 기반 라우팅 미연결; 현재 Agent Card는 Gateway `/.well-known/agent-card.json` 노출·검증만 사용.
- Next: kagent endpoint 등록 → Agent Card discovery/능력 매칭 → 로컬 Qwen ModelConfig 연결.

## 2026-07-11 — 범용 Ops 에이전트 + 관측성 + On-Prem Provision(Terraform/Ansible) + kagent + 아키텍처 정식화

- Status: AI Model Router 배포 채팅을 **범용 On-Prem Ops 에이전트**로 확장(질의→자율 tool 수행), reasoning+tool 트레이스 스트리밍/기록/상세페이지, On-Prem **Provision 역할**(Terraform kind + Ansible k3s) 구현, kagent 설치, ARCHITECTURE 통합·최신화.
- Changed:
  - **범용 Ops**: `ops_tools.py`(read-only kubectl: list_pods/get_logs/describe/rollout_status/list_namespaces) + 시스템프롬프트 일반화. 도구셋 = provision+deploy+investigate(12개).
  - **Provision(① 역할)**: `adapters/provisioning/`(base/onprem/registry) + `provision_tools.py`(provision_cluster/teardown) + `infra/onprem/terraform`(kind IaC, validate/plan ✅) + `infra/onprem/ansible`(k3s 플레이북).
  - **관측성**: `model_router.build_trace`(reasoning+tool ordered trace) + SSE `reasoning` 이벤트, `deploy_recorder` trace 저장, 배포 상세 페이지(`/deployments/[id]`) — instruction/reasoning/tool args·result/summary(markdown)/kubectl output.
  - **대시보드**: 로컬 dev 로그인(GitHub 없이 admin, prod 비활성), Agents 채팅 SSE 스트리밍+인라인 args/result, ModelLogo, Agent 카드 **Tools 팝업**(포털), 배포 상세 진입(Deployments/타임라인), 폭 확대(max-w-[1800px]), 채팅 60vh, 타임라인 10건 페이징.
  - **kagent**: kind에 helm 설치(controller/ui/postgres Running, 에이전트 10개 CRD). LLM(로컬 Qwen) 연결은 호스트 네트워킹 미해결.
  - **Make**: `local-llm-up/down/status`, `mlx-serve/mlx-proxy/router-api`.
  - **Docs**: ARCHITECTURE 통합 스택 표 + Orchestrator+A2A 타깃 + On-Prem "MCP만" 부정확 수정. DECISIONS D9.
- Verified:
  - `make check` → **584 passed, 1 skipped**; dashboard `tsc` 0; `terraform validate/plan` green.
  - **Live E2E (실 MLX Qwen30B → kind)**: NL 배포 build→push→deploy→validate + recorder→DynamoDB→대시보드 aws-live 추적, reasoning/tool SSE, "list pods" 질의는 진단만 수행 확인.
- Blockers: kagent↔로컬 Qwen 연결(kind pod→host MLX 네트워킹, MLX proxy 0.0.0.0 바인딩 필요). 클라우드 Provision/Agent Runtime 호스팅·Orchestrator+A2A 통합 = 로드맵.
- Next: (1) Orchestrator(supervisor)+A2A 통합 착수, or (2) kagent↔Qwen 연결 완성, or (3) push(현재 origin 대비 ahead 18).

## 2026-07-11 — AI Model Router + 자연어 On-Prem 배포 + 대시보드 Agents 채팅

- Status: 모델(두뇌)과 환경(대상)을 분리하는 **AI Model Router**를 구현하고, On-Prem은 Strands 대신 **Pydantic AI + MLX Qwen** 독립 에이전트로 전환. 대시보드 Agents 페이지에 모델 선택 + 자연어 배포 채팅 추가.
- Changed:
  - `model_router.py` — 모델 레지스트리(local-qwen/bedrock-claude/vertex-gemini/azure-gpt) + (model×environment) 적합도 매트릭스 + 라우팅.
  - `local_deployer.py` — Strands 무의존 Pydantic AI On-Prem 에이전트(완전 오프라인). `local_deploy_api.py` — `/api/models`(셀렉터) + `/api/local-deploy`(실행). `deploy_recorder.py` — DEPLOY+ACTIVITY 기록(executor-writes, env 게이트).
  - `mlx_qwen_tool_proxy.py` — 클라이언트 `stream` 플래그 존중(SSE/JSON 양쪽) 프레임워크 중립화.
  - Dashboard: `agents/deploy`·`agents/models` 라우트, `agent-deploy-chat.tsx`(적합도 배지+step trace), `lib/model-router.ts`(정적 fallback), `agents/page.tsx` 연동.
  - `scripts/slack_live_approval.py` — AWS 배포 없이 Slack 승인 send/simulate/full 하네스.
  - Docs: `ARCHITECTURE.md`(Model Router 섹션+프레임워크 표+On-Prem 갱신), `local-llm-onprem.md`(프레임워크 분리 기록). `pyproject.toml` `[onprem]` extra.
- Verified:
  - `make check` → **569 passed, 1 skipped** (신규 +22 테스트: router/local_deployer/local_deploy_api/deploy_recorder/proxy).
  - Dashboard `tsc --noEmit` 0 + `next build` 성공(신규 라우트 등록 확인).
  - 라우터 API live: `/api/models?provider=onprem` → local-qwen recommended 최상단, aws → bedrock-claude recommended 확인.
  - **Live E2E (신규 Pydantic AI 경로)**: MLX Qwen3-Coder-30B(.venv-mlx, :18090) + proxy(:18091) → `route_deploy("Deploy orders-api ... namespace local-llm-smoke", local-qwen, onprem)` → build→push→deploy→validate 자율 4-tool 실행, `ok=True`. kubectl 확인: `orders-api 1/1 Running`, image=`localhost:5001/orders-api:v1.5.0` 롤링 업데이트.
  - **Live 추적 실증 (Deployments 배선 완성)**: API 배포(`PLATFORM_ACTIVITY_TABLE`=platform-agent-activity, us-east-1) → recorder가 `DEP-262AC0A3`(orders-api v1.6.0)+`ACT-1C981F27` 기록 → 대시보드 `/api/dashboard/deployments`(source: aws-live)가 최신 배포로 노출 확인. kubectl: image v1.6.0. 대시보드↔라우터 API 배선도 dev 서버 live curl(`source: router-api`)로 확인.
  - Slack simulate: approve/reject E2E(실 HMAC 서명 → SFN send_task_success/failure) 통과.
- Blockers:
  - ⚠️ 워킹트리에 **세션 외 미커밋 변경** 다수(ruff autofix류). 특히 `src/agents/models.py` 재수출 제거로 `from src.agents.models import ServiceSpec` ImportError(테스트는 통과). 이번 커밋에서 제외함 — 별도 검토 필요.
  - 실 MLX 서버 기반 채팅→kind 배포 live 스텝은 운영자 수행 필요(로직은 TestModel로 검증).
- Next: 세션 외 미커밋 변경(특히 models.py) 검토/정리 → 대시보드 채팅 live 데모(MLX+kind).

## 2026-07-11 — 로컬 Qwen3-Coder 모델 기반 On-Premises E2E 자율 배포 검증 완료

- Status: MLX Qwen tool proxy의 이중 호환성(Pass-through 및 XML Fallback) 개선을 적용하고, 로컬 kind 클러스터 및 레지스트리 환경에서 strands 자율 배포 E2E 연동 테스트 통과.
- Changed:
  - Tool Proxy: `mlx_qwen_tool_proxy.py`에서 MLX-LM 서버의 네이티브 `tool_calls` JSON 구조를 무손실 중계(Pass-through)하도록 보완하고 XML 마크업 Fallback 로직을 개선.
  - Documentation: `local-llm-onprem.md`에 proxy 구조와 kind 클러스터 E2E 배포/검증 E2E 실행 결과 수록.
- Verified:
  - `make local-cluster` 기동 및 MLX Qwen proxy (:18081) 연동 테스트 완료.
  - `orders-api` 배포 E2E: 빌드(build_image) -> 푸시(push_image) -> local-llm-smoke 네임스페이스 배포(deploy_to_cluster) -> 검증(validate_deployment, 1/1 Ready) 자율 연동 성공.
  - 전체 단위/통합 테스트 (`make check`) 실행: 544 passed, 1 skipped (성공).
- Next: Slack App 대화형 인터랙티브 컴포넌트 실연동 설정 (Task 12).

## 2026-07-11 — 유저 권한 관리(Users Admin UI) 및 멀티 클라우드 장애 복원력(Failover) 연동 완료

- Status: Admin용 사용자 계정 권한 제어판 구축 및 AWS/GCP/Azure 장애 발생 시 예비 리전/클러스터 우회 복구(Multi-region Failover) 시스템 구현 완료.
- Changed:
  - Users UI: `/users` 계정 권한 설정 페이지를 신설하고 대시보드 내 `UsersTable` 클라이언트 컴포넌트를 연동. Admin 역할 사용자만 진입 가능하며 DynamoDB에 저장된 개별 세션 계정 등급(Viewer/Operator/Admin)을 실시간 편집 가능.
  - Self-lockout Protection: 관리자가 본인 역할을 실수로 강등하여 관리 콘솔에서 잠기는 잠금 방지(Lockout Protection) 기능 적용.
  - Sidebar: 로그인 세션의 역할에 따라 `admin` 권한이 있는 경우에만 "Users" 메뉴가 동적으로 노출되도록 개선.
  - AWS Failover: SSM Automation 실행 실패 시 `AWS_FAILOVER_REGION`(기본 `us-east-1`)으로 자동 스위칭하여 복구 문서를 재시도하도록 보강.
  - GCP Failover: GKE API 호출 및 Cloud Run 조작 실패 시 `GCP_FAILOVER_CLUSTER_NAME` 및 `GCP_FAILOVER_REGION`으로 우회하여 복구 동작을 연속 수행하도록 지원.
  - Azure Failover: AKS 크레덴셜 획득/API 배포 실패 시 `AZURE_FAILOVER_CLUSTER_ID` 및 `AZURE_FAILOVER_RESOURCE_ID`로 Failover하여 실행 보장.
  - MLX-LM Integration: On-Premise 타겟 배포 시 로컬 MLX-LM API 서버를 타겟팅할 수 있는 통합 연동 모듈을 `strands_deployer`에 추가하고 python 환경에 `mlx-lm` 설치 완료.
  - Tests: `test_multicloud_runners.py`에 GKE failover 복구 단위 테스트를 추가하고 전체 543개 백엔드 테스트 및 Next.js 프로덕션 빌드/배포 패스 검증 완료.
- Next: Slack 대화형 연동 가이드 정리.

## 2026-07-11 — 대시보드 감사 로그(Audit Logs) 뷰어 및 역할 기반 필터 연동 완료

- Status: 시스템 변조/승인 이력을 모니터링할 수 있는 감사 로그(Audit Logs) 조회 페이지 및 전용 API 구현 완료.
- Changed:
  - API Route: `/api/dashboard/audit` 엔드포인트를 구현하여 인증 및 역할 검증(Admin/Operator 권한 체크)을 거쳐 감사 로그를 전달하고 미들웨어 수준에서 경로 차단 보호를 적용.
  - Audit Page: `/audit` 화면을 신설하여 비인증/Viewer 등급 사용자에게는 "Access Denied" 오류 화면을 출력하고, 승인된 관리자에게는 SSR 기반의 실시간 DynamoDB 로그 리스트 렌더링.
  - Audit logs table: 클라이언트 컴포넌트(`AuditLogsTable`)를 개발하여 감사 ID, 수행한 운영자, 액션, 대상, 결과 상태(Success/Failed), 발신 IP 및 UserAgent의 대화형 검색 및 필터링 기능 추가.
  - Sidebar: 로그인한 세션 유저의 역할에 맞춰 Admin/Operator인 경우에만 좌측 네비게이션 메뉴에 "Audit Logs" 메뉴 아이템이 동적으로 렌더링되도록 개선.
  - Overview: 메인 Overview 화면의 "Incident feed" 옆 "View all →" 요소를 Next.js `Link` 컴포넌트로 연동하여 실제 Incidents 페이지로 정상 라우팅되도록 수정.
  - Deploy: Next.js 16 빌드 성공 및 최종 프로덕션 웹사이트 배포 완료.
- Next: Slack App 대화형 구성요소의 실 연동 설정 가이드 수립.

## 2026-07-11 — GCP 및 Azure 실 API 연동 및 OIDC 인증 연동 완료

- Status: AWS STS 연계를 활용한 GCP/Azure 실 REST API 연동 및 OIDC 페더레이션 크레덴셜 자격증명 모듈 구현 완료.
- Changed:
  - GCP Auth: AWS STS GetCallerIdentity 서명 정보로 GCP STS 교환 토큰을 가져오는 WIF 페더레이션 자격증명 모듈(`gcp_auth.py`) 구현 (Service Account Key 폴백 지원).
  - GCP/Azure Runners: GKE 롤아웃 재시작/스케일링/롤백 API 호출 및 Cloud Run 스케일링/트래픽 롤백 REST API 호출이 가능한 실 인프라 러너(`gcp_runner.py`, `azure_runner.py`) 개발.
  - Executors: 중앙 AWS Step Functions Executor(`handler.py`) 및 GCP Cloud Workflows Executor(`gcp/executor.py`) 양측에 신규 외부 클라우드 실 실행부 바인딩 완료.
- Verified:
  - `pytest tests/test_multicloud_runners.py` -> 5 passed (성공).
  - 전체 파이썬 테스트 슈트 -> 541 passed, 1 skipped (Mock 모드 기본 지원 확인).
- Next: Slack App 대화형(Interactive) 구성요소의 단일 AWS 연결 설정 연계.

## 2026-07-11 — Auth Phase 2 & 3 UI Control Panels 구현 및 배포 완료

- Status: 대시보드 내 승인/배포/롤백 수행이 가능한 대화형 UI 구성 요소 개발 및 프로덕션 배포 완료.
- Changed:
  - Incidents UI: `PendingApprovals` 카드 컴포포넌트 구현하여 미해결 승인 건 목록 노출 및 즉각적인 승인/거절 기능 제공 (역할 기반 접근 체크 연동).
  - Deployments UI: `DeploymentsControl` 컴포넌트 추가하여 신규 배포 트리거 모달 양식(`service_name`, `version`, `provider`, `environment`) 및 성공한 배포 건에 대한 롤백(Rollback) 실행 버튼 연동.
  - Vercel: 로컬 빌드 및 프로덕션 사이트(`https://platform-agent-red.vercel.app`)에 최종 배포 완료.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: 추가로 요구되는 Slack App 연동 또는 GCP/Azure 클러스터 연동 시 설정 연계.

## 2026-07-11 — Auth Phase 2 (Option 1) & Phase 3 (Option 2) 완료

- Status: Auth Phase 2 및 Phase 3에 명시된 기능 전체 구현 및 빌드 검증 성공.
- Changed:
  - CDK: `platform-agent-users` 및 `platform-agent-audit` DynamoDB 테이블 정의 및 Vercel OIDC role 권한 부여. Step Functions `SendTaskSuccess/Failure/DescribeExecution` 권한 추가.
  - Auth Phase 2: GitHub Organization 멤버십 체크 및 DynamoDB 사용자 역할 연동 (`auth.ts`, `user-data.ts`), 사용자 역할 관리를 위한 관리자 API (`/api/dashboard/users`) 구현.
  - Auth Phase 3: Step Functions 연동 approval 승인/거절 API (`/api/dashboard/incidents/[id]/approve`), deployment trigger API (`/api/dashboard/deployments/trigger`), deployment rollback API (`/api/dashboard/deployments/[id]/rollback`) 구현.
  - Audit logging: 모든 쓰기/변경 엔드포인트에 90일 보관 감사 로그 적재 (`audit-data.ts`, `platform-agent-audit` 테이블 적재).
- Verified:
  - `make check` -> 536 passed, 1 skipped.
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: Vercel에 신규 테이블 권한이 포함된 CDK 스택 재배포 및 배포 환경 연동.

## 2026-07-11 — Dashboard live data pipeline + Auth (Task 11 [auto] 완료)

- Status: Task 11 자동 항목(Activity DB write path, Auth.js Phase 1) 구현 및 검증 완료.
- Changed:
  - Write path: `src/agents/ai/pipeline.py`에 `platform-agent-activity` 테이블 적재 로직 `_record_pipeline_result` 구현.
  - Auth: GitHub OAuth(`dashboard/src/auth.ts`), 세션 프로바이더(`auth-provider.tsx`), 대시보드 헤더 세션 연동 및 미들웨어(`/api/dashboard/:path*/approve` 등) 보호 완료.
  - Test fix: `tests/test_gcp_day2_operations.py`의 휴리스틱 테스트들이 실 Vertex AI 대신 Mock/Heuristic Fallback을 타도록 `vertexai` 모듈 mock 패치 적용.
  - Renaming: 대시보드 UI 상의 `CNCF / On-Prem` 표기를 `On-Premise`로 리네이밍.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - GCP Day2 tests -> 28 passed.
  - Dashboard `npm run build` -> Turbopack 컴파일 및 타입 검사 통과.
- Blockers: 없음.
- Next: Vercel 환경 변수 `DASHBOARD_ACTIVITY_TABLE` 추가 및 대시보드 재배포 (manual).

## 2026-07-11 — Dashboard portfolio release (Task 10 완료)

- Status: 3개 항목 모두 구현·배포·검증 완료.
- Changed:
  - Open Graph: `opengraph-image.tsx` (Edge runtime 1200×630) + `twitter-image.tsx` + `layout.tsx` full OG/Twitter metadata.
  - Durable read model: `activity-model.ts` (DynamoDB 단일 테이블 PK/SK+GSI1) + `activity-data.ts` (3 feed 함수) + API routes 3개 + CDK `platform-agent-activity` 테이블.
  - Auth boundary: `docs/DASHBOARD_AUTH_DESIGN.md` (RBAC 3-role, JWT, 승인 플로우, 3-phase 구현 계획) + `dashboard/src/lib/auth.ts` (타입 모듈).
  - Pages: `page.tsx`/`deployments/page.tsx`/`agents/page.tsx`를 activity-data.ts 사용하도록 전환.
  - CDK: `platform-agent-activity` 테이블 + GSI1 + Vercel OIDC read grant 배포 완료.
- Verified:
  - `make check` → **525 passed, 1 skipped** (244.82s).
  - Dashboard `npm run build` → 11 routes 컴파일 성공 (opengraph-image, twitter-image 포함).
  - Vercel production 배포 → `platform-agent-red.vercel.app` OG image 200 OK (107KB), 전체 meta tags 확인.
  - CDK deploy → `platform-agent-activity` ACTIVE (PK/SK + GSI1), Vercel role에 read 추가.
  - AWS: `aws dynamodb describe-table` → 스키마 정확 확인.
- Blockers: 없음.
- Next: Executor에서 activity table write path 연결 → Auth.js Phase 1.

---

## 2026-07-11 — Vercel OIDC live incident production 활성화

- Status: 완료.
- Changed:
  - AWS: Vercel Team issuer OIDC Provider + `platform-agent-vercel-dashboard-read` Role 배포; `incident-history` read-only 권한.
  - Vercel: Production/Preview에 live source, region, table, role ARN env 설정; CLI root link + `.vercelignore` 추가.
  - Production `https://platform-agent-red.vercel.app` 갱신.
- Verified:
  - CloudFormation `UPDATE_COMPLETE`; OIDC trust는 team/project + production/preview subject로 제한.
  - Protected Preview와 Production API 모두 `source=aws-live`; 현재 records 0건.
  - Production Overview `LIVE · AWS` 표시, Playwright console errors 0건.
- Blockers: 없음.
- Next: Open Graph 메타/이미지 구성과 공유 미리보기 검증.

---

## 2026-07-11 — Dashboard AWS incident live read path + Vercel OIDC

- Status: 구현·로컬 live read 검증 완료.
- Changed:
  - Dashboard `/api/dashboard/incidents` + server data source: `aws-live` / `demo` / `demo-fallback` 계약과 UI 라벨 추가.
  - Executor DynamoDB record에 provider/mode/runbook/timestamp/executed_actions read-model 필드 추가.
  - CDK: Vercel team/project/environment-scoped OIDC trust + `incident-history` read-only IAM role.
- Verified:
  - `make check` → **519 passed, 1 skipped** (230.44s); 신규 persistence test 포함.
  - Dashboard lint/build pass; Playwright demo API·페이지 console error 0건.
  - 로컬 AWS mode → `source=aws-live`, 0 records; CDK TypeScript build + OIDC-context synth pass.
- Blockers: 없음.
- Next: OIDC role을 실배포해 Vercel live feed 활성화.
