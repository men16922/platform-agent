# STATUS — platform-agent

최종 갱신: 2026-07-31

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1596 passed, 1 skipped** (2026-07-31, 1572→1596, +24) —
  **결정 5를 추천안대로 실행**(`b92b54e`+`2a21b86`). **B 배포 신원 축소**: 네 어댑터가 맨
  `kubectl`을 만들어 ambient=**cluster-admin**으로 돌던 걸 seam 하나로 고정(허용은 어댑터가
  부르는 kubectl에서 **파생**, 금지는 **명시**). **A 스코프 생산자**: `attest_decision()`을
  **인가가 성립하는 두 지점**에서 호출 + 테넌트 자격증명 민팅 스크립트(Phase 1a 증거의 그것은
  손으로 만들어 커밋된 적이 없었다). **라이브 kind 양쪽**: 축소 신원으로 `get secrets -A`=no인데
  실 배포·롤백 정상 · 실 인시던트가 **실제로 스코프를 얻고** 이웃 테넌트는 REFUSED.
  **기본값 불변**(미설정=예전 동작 + 경고). 증거
  `docs/evidence/{deploy-identity-reduction,scope-producer-live}.log`.
- `make check` → **1572** (2026-07-30, +7) — **스코프 도달성 실측 + 가드**(결정 5 조사):
  **생산자 없는 메커니즘은 테스트에서 영원히 초록**이다(17개 테스트가 전부 자기가 만든
  레코드로 통과). 증거 `docs/evidence/deploy-path-authorization.log`.
- `make check` → **1565** (2026-07-30, +13) — **배포 네임스페이스 출처**(D37): 행이 착지한 ns를
  안 말해 **네 층이 각자 `"default"`를** 채웠다. **라이브**: 같은 이름이 두 ns에 있으면
  `rollout undo -n default`는 **엉뚱한 쪽을 되돌리며 성공을 보고**한다. **D36이 세 번째·네 번째
  경계에서 살아 있었다**(가드가 **열거**해서).
- `make check` → **1552** (2026-07-29, +8) — **배포 tier 발명 제거**(D36): 한 미상값을 경계는
  `"dev"`로, 매퍼는 `"production"`으로 채웠다. 부재를 끝까지 보존.
- `make check` → **1544** (2026-07-29, +11) — **리포트 창**: `ttl`을 시각처럼 읽어 일일 SLO의
  24h 창이 보관 기간 전체였다(90행 중 90 → 2). ⚠️**라이브 미실행**(실 AWS 필요).
- (이전 이력: gate **1533** 이하 · 2026-07-10~29 → `docs/archive/status-baseline-2026-07.md`
  및 `PROGRESS_LOG`.)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider(AWS/GCP/Azure/On-Prem) 코드 완비. 하네스 = overnight-harness 5 engine.

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge. **3-Cloud Day2**: AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions), 각각 4-step.
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
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지, DynamoDB Live 전용. Auth.js GitHub OAuth + Admin/Operator/Viewer 권한 제어판(잠금 방지), 복구 승인, 배포 트리거/롤백, 감사 로그 — 프로덕션 배포 완료.

## Active Focus

**지금 하는 것**

- **Phase 3(인가 강화) = 완결(M12) + 결정 5 A·B로 실제 집행 가능해짐(2026-07-31, → Risk 3)** —
  다음은 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기 — 열려야 ②를
  GitOps-native로 닫는다). **과대 해석 금지 4건**: 스코프도 배포 신원도 **옵트인**이라 미설정
  환경에선 집행되지 않는다(→ Risk 3) · 자격증명 자체가 테넌트-바운드인 것은 **온프렘뿐**
  (→ Risk 10) · ②는 조용한 되돌림을 거부로 바꿀 뿐(→ D32) · 파티션된 읽기 경로는 **둘뿐**.
- **차단 없는 잔여 = 소진 → M13, 14건**(2026-07-28~30) — **열네 번 다 테스트는 초록**이었다
  (상세 → `COMPLETED_SUMMARY` M13). 아홉은 "선언되고 저장되고 **아무도 읽지 않는다**", ⑩**반대
  방향**("읽는데 아무도 안 씀"), ⑪**한 층 위**(선언 자체를 아무도 안 읽음 — importer 0),
  ⑫리포트 창, ⑬배포 tier 발명(D36), ⑭**배포 네임스페이스 출처**. **교훈**: 부재보다
  **그럴듯한 기본값**이 오래 산다 · **투영/스키마 계층도 소비자**다 · 가드는 **파생**시켜라
  (열거한 D36 가드가 두 경계를 놓쳤다) · **수호 테스트 자신이 안티패턴일 수 있다**(세 번).
  **그 다음 층**: 생산자 자체가 없으면 소비자를 단언해도 초록이다 → Risk 3.
- **결정 1 = 닫힘(2026-07-29, D36)** — **배포는 테넌트 소유가 아니다**: 무파티션 + 테넌트별 모델
  rate limit 안 함 확정. 한 개인 줄 알았던 게 **세 개**(귀속·인가·과금)였고 과금은 결정이 아니라
  **구조 대기**였다. **"테넌트 격리됨" 범위는 플릿·인시던트 둘로 고정.** 분리분 중 인가는
  **결정 5**로 살아 있다(→ Risk 3).
- **발행 3종 완료(2026-07-28)** — Notion·YouTube Shorts `2J9WfZV0TPE`·LinkedIn `6979787`. 후속편 보류.

**직전에 선 것들(2026-07-26~27, 상세는 `PROGRESS_LOG`/`COMPLETED_SUMMARY`)**

- **자연어 한 문장이 테넌트를 세운다** — `setup_tenancy → install_tenant_addons`(17.6s). mutating
  범위는 **테넌트 스코프까지**, 공유 스택 9개는 TF 소유·컨텍스트 불일치 시 거부(D30).
- **시연 가능** — `make dev-up` → `make demo-baseline` 4축 ✓ → netpol 1개 삭제 시 network 축만 ✕
  → 복구까지 재현(영상·대본 `docs/post/`) · **레지스트리가 설치까지 표현한다**(`render_addons.py`)
  · **대시보드가 멀티테넌시를 관제한다**(플릿 표, push 전용 D28) · **검증이 훅으로 강제된다**
  (Stop→`make check`, PostToolUse→`tsc`, D29).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다(2026-07-29)** — Cosmos DefaultTimeToLive 미설정,
   Firestore TTL 정책 부재 + 필드가 정수 → **어느 쪽도 만료 안 됨**. "90일"을 믿지 말 것.
   켜는 건 실 데이터 삭제라 승인 → `NEXT_PLAN`.
3. **⚠️ 스코프 격리는 이제 가능하지만 옵트인이다(2026-07-31, 결정 5 A·B 반영)** — 어제 상태는
   "두 경로가 반대 방향으로 고장"이었고 **둘 다 닫혔다**: 인시던트 경로에 생산자가 섰고
   (`attest_decision`), 배포 경로는 축소 신원을 쓸 수 있다. **그러나 기본값은 여전히 미설정**이다
   — `PLATFORM_{CREDENTIAL_DIR,APPROVAL_SIGNING_KEY}`가 없으면 인시던트 경로는 예전처럼 전부
   거부하고, `PLATFORM_DEPLOY_KUBECONFIG`가 없으면 배포는 ambient(=kubeadm에서 cluster-admin)로
   돈다. 즉 **"설정하면 집행되고, 안 하면 조용히 안 된다."** 어느 쪽인지는
   `python scripts/probe_scope_reachability.py`(REFUSED를 찍는다)와 `make deploy-identity-check`가
   답한다. 켜기: `make scope-credentials` · `make deploy-identity`. **남은 것**: 배포 신원은
   테넌트를 구분하지 않는다(무엇을 할 수 있는지만 좁힌다 — 결정 5 C/D는 라우터 인증 선행) ·
   서명키 custody/rotation 미해결 · 클라우드 3종은 여전히 Risk 10.
4. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 시 클러스터 가동 + WIF OIDC 과금 체크.
5. **k3s는 NetworkPolicy를 집행하지만 proven 집합엔 없다(2026-07-29 실측)** — 라이브 3종으로
   **집행은 증명**됐으나 이 집합이 licensing하는 주장은 **우리 정책 shape의 시맨틱**이고,
   `verify_tenant_isolation.py`는 k3s-lab에 **피어 테넌트가 없어 못 돈다**. 집행 증명 ≠ 시맨틱
   증명. → `NEXT_PLAN` 결정 4.
6. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트까지다. API 서버가 미서명
   이미지를 거부하려면 policy controller 새 의존성 필요. **있는 보증을 과대 해석하지 말 것.**
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(구버전 에이전트 페이로드). 롤링 업그레이드 중엔 허브가 두
   버전을 동시에 서빙하므로 **푸시 신규 필드는 항상 optional + 폴백**으로 다룬다.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 파드가 admission에서
   거부되는데 **Argo는 Synced로 보인다**(파드 0개인 채). **새 애드온마다 확인이 필요**하다 — 렌더된
   파드 스펙을 테넌트 ns에 `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 게 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(키 철자가 차트마다 다름).
9. **Capsule deprecation — `additionalMetadata` 이관 완료(2026-07-28), `limitRanges`는 남음.**
   기계적 포팅이 아니다: `GlobalTenantResource`는 **클러스터 스코프**라 **D30 위반**이고
   `TenantResource`는 **SA+RBAC 새 권한 표면**이 필요하다(동작하며 경고만 뜬다, 2→1건). ⚠️ 결정 3.
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 액션이 **어느 네임스페이스를
   건드릴지**만 정하고 토큰을 테넌트에 묶지 않는다. GCP는 프로젝트 전역 신원 하나, **Azure는 ARM에서
   클러스터 admin kubeconfig를 받아온다**. 자격증명 자체가 경계인 것은 **온프렘뿐** → Phase 4.
11. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 없음·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
