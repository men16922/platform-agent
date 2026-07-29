# STATUS — platform-agent

최종 갱신: 2026-07-29

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1544 passed, 1 skipped** (2026-07-29, 1533→1544, +11) —
  **리포트 창**(`5988d6b`): `ttl`은 "쓴 시각+90일"인데 두 fetch가 시각처럼 읽었다. 일일 SLO
  필터 `ttl >= now-24h`는 **만료 안 된 모든 행에 참** — 24시간 창이 보관 기간 전체였다
  (실측 90행 중 90 → 2). 주간 온콜은 `ttl-90일` 역산이라 보관 상수가 바뀌면 조용히 밀리고,
  **`ttl` 없는 행은 90일 과거로 떨어져 모든 리포트에서 누락**됐다. 둘 다 `created_at`으로
  배치, 레거시 폴백 상수는 **writer AST에서 파생 검증**. ⚠️**라이브 미실행**(스케줄 Lambda
  경로 = 실 AWS 필요) — 프로덕션 과대집계는 **추론이지 관측이 아니다**.
  증거 `docs/evidence/report-windows.log`.
- `make check` → **1533** (2026-07-29, 1528→1533, +5) —
  **읽기 모델 문서 드리프트**(`61ee2f4`): `activity-model.ts`를 **아무도 import하지 않아**
  존재 내내 양방향으로 어긋났다 — 아무도 안 쓰는 `duration_ms`를 선언하고, 상세 페이지가
  딛고 선 `trace`·`cost_metrics`·`deployment_id`는 빠뜨렸다. **거짓 주장 둘**: `ttl` "30일
  보관"은 주 writer가 안 써서 **그 행들은 만료 안 됨** · `GSI1`은 절반만 채워지고 아무도
  쿼리하지 않아, 이 문서대로 provider 쿼리를 짰다면 **조용히 짧은 목록**을 받았을 것.
  지키던 테스트가 부분문자열 존재만 봤다 → writer AST 파생 가드로 교체.
  런타임 변화 없음. 증거 `docs/evidence/activity-read-model-drift.log`.
- (이전 이력: gate **1528** 이하 · 2026-07-10~29 → `docs/archive/status-baseline-2026-07.md`
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

- **Phase 3(인가 강화) = 완결(M12, 2026-07-28)** — 상세 → `COMPLETED_SUMMARY` M12.
  다음은 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기 — 열려야 ②를
  GitOps-native로 닫는다). **과대 해석 금지 3건**: 자격증명 자체가 테넌트-바운드인 것은
  **온프렘뿐**(→ Open Risks 8) · ②는 조용한 되돌림을 거부로 바꿀 뿐(→ D32) · 테넌트 파티션이
  걸린 읽기 경로는 **둘뿐**(플릿·인시던트) — deployments/activities는 배포 기록에 테넌트
  개념이 **아예 없어서** 무파티션이다. 대시보드 전체를 "테넌트 격리됨"이라 부르면 안 된다.
- **차단 없는 잔여 = 소진(2026-07-28~29) → M13, 12건** — 같은 결함 축이고 **열두 번 다 테스트는
  초록**이었다(상세 → `COMPLETED_SUMMARY` M13). 아홉은 "선언되고 저장되고 **아무도 읽지 않는다**",
  ⑩**반대 방향**("읽는데 아무도 안 씀"), ⑪**한 층 위**(선언 자체를 아무도 안 읽음 — importer 0),
  ⑫그 실마리를 따라간 **리포트 창**(보관 필드를 시각으로 읽음). 뒤 셋은 전부 **스윕을 새 방향으로
  넓혀서** 나왔다 → `scripts/find_unwritten_keys.py`. **현행 교훈 3종**: 부재보다 **그럴듯한
  기본값**이 오래 산다 · **투영/스키마 계층도 소비자**다 · 가드는 **파생**시켜라 —
  그리고 **수호 테스트 자신이 안티패턴일 수 있다**(내 새 가드가 두 번 그랬다).
  남은 잔여는 전부 **결정 대기**이지 작업 대기가 아니다(아래 3건).
- **⚠️ 결정 1개가 두 항목을 동시에 막고 있다: "배포는 어느 테넌트 소유인가"** —
  조사 결과 **모델 호출 rate limit**도 여기 묶여 있다. 로컬 모델 호출자는
  `local_deployer`/`strands_deployer` 둘뿐이고 둘 다 배포 경로인데 배포 요청엔 테넌트가
  없고, `setup_tenancy(tenant, ...)`는 **모델이 부르는 도구**다 — 테넌트가 추론의
  **입력이 아니라 출력**이라 신원 전파가 성립하지 않는다. deployments/activities 파티션과
  같은 결정.
- **발행 3종 완료(2026-07-28)** — Notion `3a94c2420ac4801cbe99e36c16ed90fd` · YouTube Shorts
  `2J9WfZV0TPE` · LinkedIn(`6979787`). GitAIOps 후속편은 착수 보류.

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
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다(2026-07-29 확인)** — 두 기록기가 `ttl`을
   쓰지만 Cosmos는 컨테이너 DefaultTimeToLive 미설정, Firestore는 TTL 정책 부재 + 필드가
   Timestamp가 아닌 정수라 **어느 쪽도 만료되지 않는다**. 문서/주석의 "90일"을 믿지 말 것.
   켜는 것은 실 데이터 삭제라 승인 사항 → `NEXT_PLAN`.
3. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
4. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트(`scripts/verify_image_signature.py`)
   까지다. 미서명 이미지를 API 서버가 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터
   의존성이 필요해 Phase 2 네임스페이스 작업과 함께 다룬다. **지금 있는 보증을 과대 해석하지 말 것.**
5. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(값이 구버전 에이전트 페이로드에서 왔다). 롤링 업그레이드 중엔
   허브가 두 버전 리포트를 동시에 서빙하므로, **푸시로 들어오는 신규 필드는 항상 optional + 폴백**으로
   다룬다. 훅의 `tsc`도 이 부류는 못 잡는다.
6. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 테넌트 네임스페이스에
   `enforce: restricted`가 붙으면 차트 기본값으로는 파드가 admission에서 거부되고, **Argo는
   Synced로 보인다**(파드 0개인 채). loki·tempo는 seccompProfile을 values에 넣어 해소했지만,
   **새 애드온을 추가할 때마다 같은 확인이 필요**하다 — 렌더된 파드 스펙을 테넌트 네임스페이스에
   `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 것이 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(차트마다 키 철자가 다르다).
7. **Capsule deprecation — `additionalMetadata`는 이관 완료(2026-07-28), `limitRanges`는 남음.**
   후자는 기계적 포팅이 아니다: `GlobalTenantResource`는 **클러스터 스코프**라 에이전트
   변경 범위를 테넌트 밖으로 밀어 **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만
   **SA+RBAC라는 새 권한 표면**이 필요하다. 지금은 동작하며 경고만 뜬다(2건→1건).
   ⚠️ 경로 선택은 결정 사항.
8. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다(Phase 3① 이후 남은 것)** — 스코프는 액션이
   **어느 네임스페이스를 건드릴지**를 정할 뿐 토큰 자체를 테넌트에 묶지 않는다. GCP는 프로젝트
   전역 신원 하나이고, **Azure는 ARM에서 클러스터 admin kubeconfig를 받아온다**(인시던트가
   어느 테넌트를 지목하든 실제 작업 신원은 cluster-admin). 자격증명 자체가 경계인 것은 **온프렘뿐**.
   → Phase 4(billable). 덧붙여 advisory `allowed_namespaces`가 실제 RBAC보다 넓고, GKE failover의
   `<cluster>-backup` 점프는 네임스페이스 게이트가 제약하지 않는다.
9. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
