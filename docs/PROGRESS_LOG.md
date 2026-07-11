# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-11

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-11 — 대시보드 감사 로그(Audit Logs) 뷰어 및 역할 기반 필터 연동 완료

- Status: 시스템 변조/승인 이력을 모니터링할 수 있는 감사 로그(Audit Logs) 조회 페이지 및 전용 API 구현 완료.
- Changed:
  - API Route: `/api/dashboard/audit` 엔드포인트를 구현하여 인증 및 역할 검증(Admin/Operator 권한 체크)을 거쳐 감사 로그를 전달하고 미들웨어 수준에서 경로 차단 보호를 적용.
  - Audit Page: `/audit` 화면을 신설하여 비인증/Viewer 등급 사용자에게는 "Access Denied" 오류 화면을 출력하고, 승인된 관리자에게는 SSR 기반의 실시간 DynamoDB 로그 리스트 렌더링.
  - Audit logs table: 클라이언트 컴포넌트(`AuditLogsTable`)를 개발하여 감사 ID, 수행한 운영자, 액션, 대상, 결과 상태(Success/Failed), 발신 IP 및 UserAgent의 대화형 검색 및 필터링 기능 추가.
  - Sidebar: 로그인한 세션 유저의 역할에 맞춰 Admin/Operator인 경우에만 좌측 네비게이션 메뉴에 "Audit Logs" 메뉴 아이템이 동적으로 렌더링되도록 개선.
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
