# STATUS — platform-agent

최종 갱신: 2026-07-28

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1411 passed, 1 skipped** (2026-07-28, 1404→1411, +7) — **읽기 파티션
  완결 + granted-viewer 실증**(`0512d2b`·`2357583`): 인시던트 파티션이 막혀 있던 원인은 읽기가
  아니라 **쓰기**(`_record_incident`가 Phase 1a부터 있던 tenant를 버렸다) · 기록 없는 행은
  admin 전용 · 캐시 `public, s-maxage` → **`private, no-store`** · granted-viewer가 미실증이던
  진짜 이유는 **local-dev 우회가 `role: admin` 하드코딩**이라 인가 표면이 로컬에서 검증 불가였던
  것. **라이브**: 익명 0/3 · viewer-demo(grant=acme) 1/3 · admin 3/3.
  증거 `docs/evidence/phase3-read-partition-live.log`.
- `make check` (pytest) → **1404 passed, 1 skipped** (2026-07-28, 1377→1404, +27) — **외부 자료
  대조발 결함 4건 근본수정**(`e7ad744`·`1aa86e0`·`67ab309`): Agent Card가 가상 주소와 **집행하지
  않는 인증**을 광고하던 것 · **MCP 게이트웨이가 ambient 자격증명 경로**였던 것(Phase 1a가 앞문에서
  없앤 fail-open이 옆문에 잔존, `kubectl_apply`는 임의 매니페스트를 임의 ns에) · 테넌트별 call
  budget 부재. **라이브(kind)**: 스코프 안 ns인데도 `secrets`는 `Forbidden` — 우리 가드가 아니라
  **API 서버**가 경계를 판정. 넷 다 테스트가 **선언만 단언해** 살아남았다.
  증거 `docs/evidence/mcp-gateway-scope.log`.
- `make check` (pytest) → **1377 passed, 1 skipped** (2026-07-28, 1355→1377, +22) — **Phase 3 완결
  ②③**(`9e78f81`·`1c13a59`): ② `reconciler.py`가 소유 표식을 라이브 객체에서 읽어 reconciler가
  되돌릴 롤백을 거부(되돌리는 액션만; restart·scale은 desired로 수렴) · ③ `visibility.ts` 단일
  seam이 읽기 쪽 테넌트 경계를 세우고 `middleware.ts`→`proxy.ts`(Next 16 deprecation) 이관,
  소비자 0이던 `ROUTE_PROTECTION` 제거. **라이브**: ② out-of-band 변경이 **10초 만에 selfHeal에
  되돌려짐**(전제 반증) → 관리 대상 롤백 거부/같은 워크로드 restart 통과 · ③ 익명 curl →
  `restricted:true`. 테스트는 `visibility.ts`를 **실행**하고 fail-open 주입으로 반증까지 확인.
  `tsc` 클린 · `next build` 성공. 증거 `docs/evidence/phase3-{reconciler-conflict,viewer-visibility}.log`.
- (이전 이력: gate 1355 이하 · 2026-07-10~27 → `docs/archive/status-baseline-2026-07.md`)

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

- **Phase 3(인가 강화) = 완결(2026-07-28)** — ①자격증명 격리 full · ②reconciler 충돌
  거부 · ③읽기 쪽 테넌트 경계. 다음은 **Phase 4**(managed 어댑터, billable) 또는
  **Phase 5**(레지스트리 쓰기 — 이게 열려야 ②를 GitOps-native로 닫는다).
  **과대 해석 금지 3건**: 자격증명 자체가 테넌트-바운드인 것은 **온프렘뿐**(→ Open Risks 7) ·
  ②는 롤백을 되게 만들지 않고 조용한 되돌림을 거부로 바꿀 뿐(→ D32) ·
  테넌트 파티션이 걸린 읽기 경로는 **둘뿐**이다(플릿·인시던트). deployments/activities는
  여전히 무파티션이고 이유가 다르다 — 배포 기록엔 테넌트 개념이 **아예 없다**(데이터 모델
  결정 선행). 대시보드 전체를 "테넌트 격리됨"이라 부르면 안 된다.
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
6. **Capsule deprecation 2건(미조치)** — `render_tenancy.py`가 내는 `limitRanges`·
   `additionalMetadata`는 상위 버전에서 제거 예정이다. 지금은 동작하지만 **values 파일이
   실패하는 방식과 같은 부류**(에러 없이 안 읽힘)라 Capsule 업그레이드 전에 이관 필요.
7. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다(Phase 3① 이후 남은 것)** — 스코프는 액션이
   **어느 네임스페이스를 건드릴지**를 정할 뿐 토큰 자체를 테넌트에 묶지 않는다. GCP는 프로젝트
   전역 신원 하나이고, **Azure는 ARM에서 클러스터 admin kubeconfig를 받아온다**(인시던트가
   어느 테넌트를 지목하든 실제 작업 신원은 cluster-admin). 자격증명 자체가 경계인 것은 **온프렘뿐**.
   → Phase 4(billable). 덧붙여 advisory `allowed_namespaces`가 실제 RBAC보다 넓고, GKE failover의
   `<cluster>-backup` 점프는 네임스페이스 게이트가 제약하지 않는다.
8. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
