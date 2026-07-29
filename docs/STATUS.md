# STATUS — platform-agent

최종 갱신: 2026-07-29

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1552 passed, 1 skipped** (2026-07-29, 1544→1552, +8) —
  **배포 tier 발명 제거**(D36): 대시보드 NL 배포는 `environment`를 안 보내는데 HTTP 경계가
  `"dev"`를, 매퍼가 부재를 `"production"`으로 채웠다 — **한 미상값에 두 층이 서로 다른 답을**
  발명했다. 부재를 끝까지 보존(경계 기본값 제거 · writer 조건부 저장 · 문서에서 optional ·
  렌더 5곳 정직화). **내 가드가 잡으려던 홀을 자기가 갖고 있었다**(첨자 대입 미인식) →
  무조건/조건부 분리로 수정. 증거 `docs/evidence/deployment-environment-absence.log`.
- `make check` → **1544** (2026-07-29, 1533→1544, +11) —
  **리포트 창**(`5988d6b`): `ttl`은 "쓴 시각+90일"인데 두 fetch가 시각처럼 읽었다. 일일 SLO
  필터 `ttl >= now-24h`는 **만료 안 된 모든 행에 참** — 24시간 창이 보관 기간 전체였다
  (실측 90행 중 90 → 2). 주간 온콜은 `ttl-90일` 역산이라 보관 상수가 바뀌면 조용히 밀리고,
  **`ttl` 없는 행은 90일 과거로 떨어져 모든 리포트에서 누락**됐다. 둘 다 `created_at`으로
  배치, 레거시 폴백 상수는 **writer AST에서 파생 검증**. ⚠️**라이브 미실행**(스케줄 Lambda
  경로 = 실 AWS 필요) — 프로덕션 과대집계는 **추론이지 관측이 아니다**.
  증거 `docs/evidence/report-windows.log`.
- (이전 이력: gate **1533** 이하 · 2026-07-10~29 → `docs/archive/status-baseline-2026-07.md`
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
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지, DynamoDB 실시간 Live 전용(데모 목업 제거). Auth.js GitHub OAuth + Admin/Operator/Viewer 역할·권한 제어판(잠금 방지), 복구 승인, 배포 트리거/롤백 패널, 감사 로그 뷰어 — 프로덕션 배포 완료.

## Active Focus

**지금 하는 것**

- **Phase 3(인가 강화) = 완결(M12, 2026-07-28)** — 상세 → `COMPLETED_SUMMARY` M12.
  다음은 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기 — 열려야 ②를
  GitOps-native로 닫는다). **과대 해석 금지 3건**: 자격증명 자체가 테넌트-바운드인 것은
  **온프렘뿐**(→ Open Risks 10) · ②는 조용한 되돌림을 거부로 바꿀 뿐(→ D32) · 테넌트 파티션이
  걸린 읽기 경로는 **둘뿐**(플릿·인시던트) — deployments/activities는 배포 기록에 테넌트
  개념이 **아예 없어서** 무파티션이다. 대시보드 전체를 "테넌트 격리됨"이라 부르면 안 된다.
- **차단 없는 잔여 = 소진(2026-07-28~29) → M13, 12건** — 같은 결함 축이고 **열두 번 다 테스트는
  초록**이었다(상세 → `COMPLETED_SUMMARY` M13). 아홉은 "선언되고 저장되고 **아무도 읽지 않는다**",
  ⑩**반대 방향**("읽는데 아무도 안 씀"), ⑪**한 층 위**(선언 자체를 아무도 안 읽음 — importer 0),
  ⑫그 실마리를 따라간 **리포트 창**. 뒤 셋은 **스윕을 새 방향으로 넓혀서** 나왔다
  (`scripts/find_unwritten_keys.py`). **교훈**: 부재보다 **그럴듯한 기본값**이 오래 산다 ·
  **투영/스키마 계층도 소비자**다 · 가드는 **파생**시켜라 · **수호 테스트 자신이 안티패턴일 수
  있다**(내 새 가드가 두 번 그랬다).
- **결정 1 = 닫힘(2026-07-29, D36)** — **배포는 테넌트 소유가 아니다**: 무파티션 + 테넌트별
  모델 rate limit 안 함 확정. 한 개인 줄 알았던 게 **세 개**(귀속·인가·과금)였고 **"둘을 동시에
  막는다"는 전제가 틀렸다** — 과금은 결정이 아니라 **구조 대기**(대상이 추론의 출력 + 라우터
  무인증). **"테넌트 격리됨" 범위는 플릿·인시던트 둘로 고정.** 분리: 배포 경로 무스코프
  (→ Open Risk 3) · 트리거 폼 tier 표기.
- **발행 3종 완료(2026-07-28)** — Notion·YouTube Shorts `2J9WfZV0TPE`·LinkedIn(`6979787`). 후속편 보류.

**직전에 선 것들(2026-07-26~27, 상세는 `PROGRESS_LOG`/`COMPLETED_SUMMARY`)**

- **자연어 한 문장이 테넌트를 세운다** — `setup_tenancy → install_tenant_addons`(17.6s).
  mutating 범위는 **테넌트 스코프까지**, 공유 스택 9개는 TF 소유이고 컨텍스트 불일치 시 거부(D30).
- **시연 가능** — `make dev-up` → `make demo-baseline` 4축 ✓ → netpol 1개 삭제 시 network 축만
  ✕ → 복구까지 재현. 영상·대본 → `docs/post/`.
- **레지스트리가 설치까지 표현한다**(`render_addons.py`) · **대시보드가 멀티테넌시를 관제한다**
  (플릿 표, push 전용 D28) · **검증이 훅으로 강제된다**(Stop→`make check`, PostToolUse→`tsc`, D29).
- **Phase 2 = 완결(M11)** · **Phase 0·1a·1b = 완결(M10)** — 상세 → `COMPLETED_SUMMARY`.

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**(provider `oidc.vercel.com/men16922s-projects` 재생성, 실 team slug=Vercel API 확증). 앞으로 diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다(2026-07-29)** — Cosmos는 컨테이너
   DefaultTimeToLive 미설정, Firestore는 TTL 정책 부재 + 필드가 Timestamp 아닌 정수 →
   **어느 쪽도 만료 안 됨**. "90일"을 믿지 말 것. 켜는 건 실 데이터 삭제라 승인 → `NEXT_PLAN`.
3. **배포 경로는 스코프 가드를 안 탄다(2026-07-29 발견)** — `guard_scoped_action`은 인시던트
   러너 3종 + MCP 게이트웨이만 부른다. `local_deployer`는 가드 없이 `namespace="default"`로
   ambient 자격증명을 쓴다. **"blast radius = 1 tenant/env"는 인시던트 경로에만 참.** → `NEXT_PLAN`.
4. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
5. **k3s는 NetworkPolicy를 집행하지만 proven 집합엔 없다(2026-07-29 실측)** — 라이브 3종
   (ENFORCED · default-deny 아래 readinessProbe Ready · DNS 정상)으로 **집행은 증명**됐다.
   넣지 않은 이유는 이 집합이 licensing하는 주장이 **우리 정책 shape의 시맨틱**인데
   `verify_tenant_isolation.py`가 k3s-lab에 **피어 테넌트가 없어 못 돌기** 때문이다.
   집행 증명 ≠ 시맨틱 증명. → `NEXT_PLAN` 결정 4.
6. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트(`scripts/verify_image_signature.py`)
   까지다. 미서명 이미지를 API 서버가 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터
   의존성이 필요해 Phase 2 네임스페이스 작업과 함께 다룬다. **지금 있는 보증을 과대 해석하지 말 것.**
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(값이 구버전 에이전트 페이로드에서 왔다). 롤링 업그레이드 중엔
   허브가 두 버전 리포트를 동시에 서빙하므로, **푸시로 들어오는 신규 필드는 항상 optional + 폴백**으로
   다룬다. 훅의 `tsc`도 이 부류는 못 잡는다.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 테넌트 네임스페이스에
   `enforce: restricted`가 붙으면 차트 기본값으로는 파드가 admission에서 거부되고, **Argo는
   Synced로 보인다**(파드 0개인 채). loki·tempo는 seccompProfile을 values에 넣어 해소했지만,
   **새 애드온을 추가할 때마다 같은 확인이 필요**하다 — 렌더된 파드 스펙을 테넌트 네임스페이스에
   `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 것이 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(차트마다 키 철자가 다르다).
9. **Capsule deprecation — `additionalMetadata`는 이관 완료(2026-07-28), `limitRanges`는 남음.**
   후자는 기계적 포팅이 아니다: `GlobalTenantResource`는 **클러스터 스코프**라 에이전트
   변경 범위를 테넌트 밖으로 밀어 **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만
   **SA+RBAC라는 새 권한 표면**이 필요하다. 지금은 동작하며 경고만 뜬다(2건→1건).
   ⚠️ 경로 선택은 결정 사항.
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다(Phase 3① 이후 남은 것)** — 스코프는 액션이
   **어느 네임스페이스를 건드릴지**를 정할 뿐 토큰 자체를 테넌트에 묶지 않는다. GCP는 프로젝트
   전역 신원 하나이고, **Azure는 ARM에서 클러스터 admin kubeconfig를 받아온다**(인시던트가
   어느 테넌트를 지목하든 실제 작업 신원은 cluster-admin). 자격증명 자체가 경계인 것은 **온프렘뿐**.
   → Phase 4(billable). 덧붙여 advisory `allowed_namespaces`가 실제 RBAC보다 넓고, GKE failover의
   `<cluster>-backup` 점프는 네임스페이스 게이트가 제약하지 않는다.
11. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
