# STATUS — platform-agent

최종 갱신: 2026-07-20

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

- `make check` (pytest) → **865 passed, 1 skipped** (2026-07-20, 233.46s, 861→865) — **On-Prem 애드온 스택 Phase 3(GitOps)**(`fafacc6`): `gitops.tf`가 ArgoCD `Application`(로컬 래퍼 차트, argocd depends_on)로 platform-agent 차트를 GitHub origin main에서 auto-sync·selfHeal 관리. `application.resourceTrackingMethod=annotation`으로 instance 라벨 추적 충돌 근본 회피, `releaseName=pa`로 Phase 2 접점 보존. 가드 +4. **라이브($0)**: apply→Synced/Healthy(rev=git HEAD)→6 리소스 무중단 채택→drift(scale 1→3)→selfHeal ~16s 복원. 증거 `docs/evidence/onprem-addons-gitops-e2e.log`.
- `make check` (pytest) → **861 passed, 1 skipped** (2026-07-20, 229.27s, 854→861) — **On-Prem 플랫폼 애드온 스택 Phase 1+2**: 신규 `infra/onprem/addons/` root(argo-cd 10.1.4·kps 87.17.0 핀, 저사양 values, kind·k3s 양기판) apply→전 파드 Ready→UI 3종 200 + Alertmanager receiver→in-cluster webhook 배선 라이브 E2E(crashme 크래시루프→룰 발화→배달→4-step→P2 승인→INC-96D41C2B resolved, $0). 가드 +7. 증거 `docs/evidence/onprem-addons-{phase1,alertmanager-e2e}.log`.
- `make check` (pytest) → **854 passed, 1 skipped** (2026-07-20, 256.62s, 수 무변경) — **리팩토링 후속 2건**(`8792c9c`): operations 그룹핑 cloud축 통일(`aws/`·`runners/` 신설, CDK 핸들러 경로 7종 정합) + approval_bridge 610줄 handler → 4모듈 분리(handler/request_store/slack_interactive/payloads). 순수 구조 개편(동작·테스트 수 무변경).
- `make check` (pytest) → **854 passed, 1 skipped** (2026-07-19, 232.03s, 847→854) — **On-Prem P2 승인 Slack 버튼 연동**(`617839b`): DynamoDB 공유 매체+옵트인 폴러, 라이브 왕복(P2 parking→Slack ONPREM 카드→Approve 클릭→APPROVED→폴러 실행→INC-FA2143AF resolved, 증거 `docs/evidence/onprem-slack-approval-live.log`). **동일자 terraform aws-production 실 apply→검증→destroy 완주**(코드 무변경): EKS 노드 2 Ready·Aurora `platform_state` available·IRSA trust 재배선 확증 후 29개 destroy·잔존 0·≈$0.5 미만(증거 `docs/evidence/terraform-aws-production-apply-live.log`) — #7-b 전 단계 실증 완결.
- `make check` (pytest) → **847 passed, 1 skipped** (2026-07-19, 232.55s, 844→847) — **Slack E2E발 후속 2건 근본수정+라이브 검증**: (a) **Bedrock 무효 모델 ID**(`9a56949`) — 스택이 `.env` 무시·무효 ID 하드코딩으로 매 인시던트 휴리스틱 폴백 강등되던 latent 결함 → `us.anthropic.claude-sonnet-4-6` 프로파일+정확-ARN IAM(프로파일+3리전 하위 모델), 라이브 `analyzer.llm_done`(실 Claude root cause가 Slack 카드에 표시). (b) **유령 SSM 문서**(`55de55e`) — `AWS-SendSlackAlert` 미실존으로 generic-recovery 구조적 `resolved=False` → `_NOTIFICATION_ACTIONS` in-process 1급 처리(+3 test), 라이브 실 LLM **P1/AUTO** 판정→`executor.notify.in_process`→**`resolved=True`**(INC-E15BA62E, DynamoDB 확증). 동일 세션에서 P3/MANUAL·P2/APPROVE 경로도 관측(LLM 심각도 3단 실증).
- `make check` (pytest) → **844 passed, 1 skipped** (2026-07-19, 234.56s) — **Slack App 실 생성 + 인터랙티브 승인 버튼 라이브 E2E 완주**: 알람 ALARM→SFN WaitForApproval→Slack `#platform-test` 버튼 메시지→**Approve 클릭**(브라우저)→서명 검증→DynamoDB claim(APR-8BC7E7E95B9A=APPROVED)→`SendTaskSuccess`→SFN **SUCCEEDED**(INC-2AC4B6C9). 라이브가 표면화한 프로덕션 버그 2건 근본수정(`0f99420`): (a) detector `_SIGNAL_ADAPTER` NameError=AWS 경로 전면 불능→`get_signal_adapter("aws")`+AWS 경로 회귀 가드, (b) approval_bridge confidence float→DynamoDB TypeError=승인 요청 전량 소실→`Decimal`+e2e 페이크에 float 거부 계약. 증거 `docs/evidence/slack-interactive-approval-live.log`.
- `make check` (pytest) → **843 passed, 1 skipped** (2026-07-18, 236.08s) — **OAuth 대시보드 배포 트리거 라이브 E2E + 프로덕션 장애 2건 근본수정**: (a) `.vercelignore` 무앵커 `src/`가 git 트리거 Vercel 배포를 전부 404 빌드로 만들던 결함 수정(canonical 200 복구), (b) CloudTrail로 07-11 **Vercel OIDC provider 삭제** 규명→CDK로 재생성(실 slug `men16922s-projects`)+정확-ARN `StartExecution` grant→대시보드 **DEMO FALLBACK→LIVE·AWS** 복구, (c) 라이브 클릭이 표면화한 `smoke_tester` `base_url` KeyError 수정+가드(+1 test). **E2E**: GitHub OAuth(operator)→Start Release→SFN `deploy-dep-1f054864` **SUCCEEDED**. 증거 `docs/evidence/oauth-deploy-trigger-live.log`.
- `make check` (pytest) → **842 passed, 1 skipped** (2026-07-17, 234.42s) — **차트 stateStore 배선(④↔#7 마무리)**: `stateStore.{dsn,existingSecret}` values(secretKeyRef=프로덕션·plain=dev, secret 우선), persistence off→RollingUpdate·replicas>1 해금, Dockerfile `.[state]`(psycopg2) 재빌드 검증. 차트 가드 +3. JSONL 기본값 무변경. **k3s substrate 스모크(동일자, 코드 무변경)**: 기존 k8s-lab VM에 helm install→`local-path` PVC Bound→P2 승인 루프→원상 복원 — env×substrate 양축(kind/k3s) 실증 완결(`docs/evidence/helm-k3s-substrate-smoke.log`).
- `make check` (pytest) → **839 passed, 1 skipped** (2026-07-17, 238.51s) — **레퍼런스 #7-b Terraform 모듈 → #7 전체 완결(Helm+Terraform)**: 신규 `infra/terraform/aws-production/`(VPC·EKS 1.31·**Aurora Serverless v2 `platform_state`**=④ DSN seam 정합·**IRSA**=차트 SA 전용 trust+DynamoDB activity 테이블 정확-ARN 유일 grant). Redis/Cognito=미소비 의도적 제외. `terraform init+fmt+validate` Success(spend 0, **apply 안 함**=사용자 게이트). 가드 +5(bare `"*"` 금지 등). 이로써 AWSome 레퍼런스 8항목 전부 소화.
- `make check` (pytest) → **834 passed, 1 skipped** (2026-07-17, 242.90s) — **로드맵 ④ SQL State Store(옵트인)+실 Alertmanager 라이브**: 신규 `state_store.py`(`PLATFORM_STATE_DSN` 옵트인, DB-API 주입식, append-only+latest-wins=JSONL 시맨틱 동일, sqlite 오프라인 테스트 +5) + approvals/incidents 양방향 배선. **라이브(docker $0)**: 실 Alertmanager grouping→배달→P2 parking→PostgreSQL, **레플리카 2개 상태 공유**(replica-2 승인→replica-1 즉시 반영=JSONL 불가), 전 프로세스 재기동 생존, psql ground-truth 3 rows. 증거 `docs/evidence/state-store-alertmanager-live.log`. JSONL 기본값 무변경(비오염 테스트 양방향).
- (이전 이력 2026-07-10~17, gate 829 이하 → `docs/archive/status-baseline-2026-07.md`)

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

- **On-Prem 플랫폼 애드온 스택(JOURNEY 범위 로컬 확장)** — `docs/plans/2026-07-20-onprem-platform-addons.md`. Phase 1(addons IaC)·2(Alertmanager→4-step)·**3(ArgoCD GitOps)** 완료(gate 865, 라이브 실증 포함). **다음 = Phase 4**(Argo Rollouts canary 승격/abort + 러너 위치 정리 DECISIONS 1건) → Phase 5 선택.
- 기존 잔여 = 아티클 배포(원고 854 기준 작성 완료, 사용자 "나중에") · push(로컬 ahead — Phase 3 커밋 후 push 예정).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**(provider `oidc.vercel.com/men16922s-projects` 재생성, 실 team slug=Vercel API 확증). 앞으로 diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
3. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
