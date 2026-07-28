# STATUS — platform-agent

최종 갱신: 2026-07-29

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1470 passed, 1 skipped** (2026-07-29, 1454→1470, +16) — **온프렘 런북
  매칭**(`b70c195`): "매칭 설계 결정"으로 남겼던 게 **겹친 결함 3개**였다 — ①`_synthetic_alarm`이
  `reason`을 `metric_name`의 복사본으로 채워 매처가 "availability availability…"를 읽었다
  (alertname·summary는 내내 저장돼 있었고 선택에만 안 닿음) ②`resource_types`가 모든 런북에
  **선언돼 있고 미소비**(없으면 엉뚱한 런북이 걸리고, 해결 실패는 **하드코딩 AWS 액션**으로 조용히
  폴백) ③스테일 시드가 **더 나쁜 매칭으로** 빌트인을 가림(1점이 3점을 이김) → 합집합 휴리스틱(D35).
  **라이브**: 4종 알람 전부 올바른 런북 + ONPREM 액션. 증거 `docs/evidence/onprem-runbook-matching.log`.
- `make check` (pytest) → **1454 passed, 1 skipped** (2026-07-28, 1446→1454, +8) — **executor span**
  (`3939d47`): 기록은 "승인 후 경로 미측정"이었지만 웹훅이 `execute=False` 후 **루트 span이 닫힌
  뒤** 실행해서 **AUTO 경로도 무추적**이었다 — 클러스터를 바꾸는 단계가 실제 알람이 타는 모든
  경로에서 span을 안 냈다. span을 `execute_incident` 안으로 + 웹훅 루트 2개 + 승인은 **링크**
  (사이 간격=사람의 고민 시간). **라이브**(실 OTLP/gRPC): AUTO 6 span 단일 트레이스
  (analyze 5.4s/7.7s) · 승인 트레이스 2개+링크 1개. 증거 `docs/evidence/executor-span-approval-path.log`.
- `make check` (pytest) → **1446 passed, 1 skipped** (2026-07-28, 1411→1446, +35) — **잔여 3건**
  (`63df3c5`·`9beda00`·`278a264`): ①grant는 대조만 없던 게 아니라 **줄 방법 자체가 없었고**
  역할 변경이 whole-item Put으로 grant를 지웠다 → 허브 `GET /api/platform/tenants`(레지스트리
  =SSOT, 못 읽으면 **503**) + 저장 전 대조 + `absent=유지` ②런북 4개가 선택 불가였고, 항목을
  넣어도 **라이브는 넷 다 generic-recovery** — 시드 테이블의 generic 행 때문에 **티어 3이
  배포 환경에서 한 번도 도달된 적 없었다**(`allow_generic=False`로 해소) ③Capsule
  `additionalMetadata`→`additionalMetadataList`(제거 시 **에러 없이 안 읽히는** 실패).
  **라이브**: grant 5케이스 · 실 DynamoDB 스캔 · kind PSS 라벨 유지 + probe 전파.
  증거 `docs/evidence/{phase3-tenant-grant-validation,runbook-selectability,capsule-deprecation-metadata}.log`.
- (이전 이력: gate **1404** 이하 · 2026-07-10~28 → `docs/archive/status-baseline-2026-07.md`
  및 `PROGRESS_LOG`. Phase 3 완결 ②③ = `9e78f81`·`1c13a59`, 증거
  `docs/evidence/phase3-{reconciler-conflict,viewer-visibility}.log`.)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider(AWS/GCP/Azure/On-Prem) 코드 완비. 하네스 = overnight-harness 5 engine.

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

**지금 하는 것**

- **Phase 3(인가 강화) = 완결(M12, 2026-07-28)** — ①자격증명 격리 full · ②reconciler 충돌
  거부 · ③읽기 쪽 테넌트 경계. 다음은 **Phase 4**(managed 어댑터, billable) 또는
  **Phase 5**(레지스트리 쓰기 — 이게 열려야 ②를 GitOps-native로 닫는다).
  **과대 해석 금지 3건**: 자격증명 자체가 테넌트-바운드인 것은 **온프렘뿐**(→ Open Risks 7) ·
  ②는 롤백을 되게 만들지 않고 조용한 되돌림을 거부로 바꿀 뿐(→ D32) ·
  테넌트 파티션이 걸린 읽기 경로는 **둘뿐**이다(플릿·인시던트). deployments/activities는
  여전히 무파티션이고 이유가 다르다 — 배포 기록엔 테넌트 개념이 **아예 없다**(데이터 모델
  결정 선행). 대시보드 전체를 "테넌트 격리됨"이라 부르면 안 된다.
- **차단 없는 잔여 3건 = 소진(2026-07-28)** — grant 대조 · 선택 불가 런북 4개 · Capsule
  metadata 이관. 남은 잔여는 전부 **결정 대기**이지 작업 대기가 아니다(아래 3건).
- **⚠️ 결정 1개가 두 항목을 동시에 막고 있다: "배포는 어느 테넌트 소유인가"** —
  조사 결과 **모델 호출 rate limit**도 여기 묶여 있다. 로컬 모델 호출자는
  `local_deployer`/`strands_deployer` 둘뿐이고 둘 다 배포 경로인데 배포 요청엔 테넌트가
  없고, `setup_tenancy(tenant, ...)`는 **모델이 부르는 도구**다 — 테넌트가 추론의
  **입력이 아니라 출력**이라 신원 전파가 성립하지 않는다. deployments/activities 파티션과
  같은 결정.
- **발행 3종 완료(2026-07-28)** — Notion `3a94c2420ac4801cbe99e36c16ed90fd` · YouTube Shorts
  `2J9WfZV0TPE` · LinkedIn. 레포 원고 정정도 반영(`6979787`). GitAIOps 후속편은 착수 보류.

**직전에 선 것들(2026-07-26~27, 상세는 `PROGRESS_LOG`/`COMPLETED_SUMMARY`)**

- **자연어 한 문장이 테넌트를 세운다** — `setup_tenancy → install_tenant_addons`(17.6s).
  mutating 범위는 **테넌트 스코프까지**, 공유 스택 9개는 TF 소유이고 컨텍스트가 레지스트리와
  다르면 아무것도 쓰지 않고 거부한다(D30).
- **시연 가능** — `make dev-up` → `make demo-baseline`으로 4축 ✓ → netpol 1개 삭제 시
  network 축만 ✕ → 복구까지 재현. 영상·대본 → `docs/post/`.
- **레지스트리가 설치까지 표현한다**(`render_addons.py`) · **대시보드가 멀티테넌시를
  관제한다**(플릿 표, push 전용 D28) · **검증이 훅으로 강제된다**(Stop→`make check`,
  PostToolUse→`tsc`, D29).
- **Phase 2 = 완결(M11)** · **Phase 0·1a·1b = 완결(M10)** — 상세 → `COMPLETED_SUMMARY`.

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**(provider `oidc.vercel.com/men16922s-projects` 재생성, 실 team slug=Vercel API 확증). 앞으로 diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
3. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트(`scripts/verify_image_signature.py`)
   까지다. 미서명 이미지를 API 서버가 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터
   의존성이 필요해 Phase 2 네임스페이스 작업과 함께 다룬다. **지금 있는 보증을 과대 해석하지 말 것.**
4. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(값이 구버전 에이전트 페이로드에서 왔다). 롤링 업그레이드 중엔
   허브가 두 버전 리포트를 동시에 서빙하므로, **푸시로 들어오는 신규 필드는 항상 optional + 폴백**으로
   다룬다. 훅의 `tsc`도 이 부류는 못 잡는다.
5. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 테넌트 네임스페이스에
   `enforce: restricted`가 붙으면 차트 기본값으로는 파드가 admission에서 거부되고, **Argo는
   Synced로 보인다**(파드 0개인 채). loki·tempo는 seccompProfile을 values에 넣어 해소했지만,
   **새 애드온을 추가할 때마다 같은 확인이 필요**하다 — 렌더된 파드 스펙을 테넌트 네임스페이스에
   `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 것이 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(차트마다 키 철자가 다르다).
6. **Capsule deprecation — `additionalMetadata`는 이관 완료(2026-07-28), `limitRanges`는 남음.**
   후자는 기계적 포팅이 아니다: `GlobalTenantResource`는 **클러스터 스코프**라 에이전트
   변경 범위를 테넌트 밖으로 밀어 **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만
   **SA+RBAC라는 새 권한 표면**이 필요하다. 지금은 동작하며 경고만 뜬다(2건→1건).
   ⚠️ 경로 선택은 결정 사항.
7. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다(Phase 3① 이후 남은 것)** — 스코프는 액션이
   **어느 네임스페이스를 건드릴지**를 정할 뿐 토큰 자체를 테넌트에 묶지 않는다. GCP는 프로젝트
   전역 신원 하나이고, **Azure는 ARM에서 클러스터 admin kubeconfig를 받아온다**(인시던트가
   어느 테넌트를 지목하든 실제 작업 신원은 cluster-admin). 자격증명 자체가 경계인 것은 **온프렘뿐**.
   → Phase 4(billable). 덧붙여 advisory `allowed_namespaces`가 실제 RBAC보다 넓고, GKE failover의
   `<cluster>-backup` 점프는 네임스페이스 게이트가 제약하지 않는다.
8. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
