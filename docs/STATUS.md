# STATUS — platform-agent

최종 갱신: 2026-08-08

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- **CI와 로컬이 이제 같은 숫자다 — 그 전엔 아니었다**(2026-08-08) — CI는 **1666/3**,
  로컬은 **1668/1**이었고 넘어간 둘이 하필 `test_terraform_validate_passes` **2종**
  (=이 레포가 배포하는 IaC 검증). `skipif`가 `terraform 미설치 **OR** 모듈 미초기화`인데
  러너가 둘 다 만족했다(`.terraform/`는 gitignore → **설치만 해도 skip**). `gate.yml`에
  terraform 1.15.8 핀 + `init -backend=false` 추가 → CI **1668/1**, 두 테스트 PASSED.
  증거 `docs/evidence/ci-terraform-validate-skipped.log` · PR #3 · → Risk 12②.
- `make check` (pytest) → **1668 passed, 1 skipped** (2026-08-08, +17, **로컬·CI 일치**) — **Phase 5 경계**:
  모든 테넌트 파일 헤더가 Phase 0부터 "이 흐름은 오직 이 파일만 PR한다"고 적어 뒀는데
  **반증할 수단이 0**이었다. `registry_write` = **텍스트로 편집·의미로 검증**(주석이 이 파일들의
  자산이라 YAML 재직렬화 금지 → 재파싱해 **키 하나만** 바뀌었는지 비교). 반증 4종 red.
  ⚠️**안전망을 통째로 지워도 14개가 초록**이었다 — 전부 행복 경로만 태웠기 때문(→ Risk 12③).
- **`main` 브랜치 보호 = 집행 확인**(2026-08-08) — PR 필수 + `check` 통과 필수, 관리자 포함.
  직접 push가 실제로 `[remote rejected]` 되는 것까지 보고, PR #1로 CI→병합 흐름을 완주했다.
  **code-owner 리뷰는 일부러 껐다**(1인 레포=만족 불가) → D43.
- **실 AWS 왕복**(2026-08-08, gate 무관 — 프로브) — 인시던트 속성 6종이 실
  `incident-history`를 왕복해 **타입까지 보존**됨. `confidence`=`Decimal`(DynamoDB N)이라
  대시보드의 `typeof === "number"`가 참이 된다. **모킹으로는 원리상 못 잡는 검증**(목은
  float를 받고, 실제로는 boto3 예외가 `except`에 잡혀 행이 통째로 사라진다).
  `scripts/probe_incident_roundtrip.py` · 증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`.
  **남은 한 칸**: 대시보드 TS 리더 미검증.
- `make check` (pytest) → **1636 passed, 1 skipped** (2026-08-08, +18) — **서명키 회전**:
  결함은 암호가 아니라 **배포 위상**이었다 — 서명자와 검증자가 다른 프로세스인데 키가 하나라
  교체가 원자적일 수 없고, 그 실패가 `failed attestation`(=위조로 읽힘)이라 **회전은 장애
  아니면 오경보**였다. `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`(검증 전용, 절대 서명 안 함) +
  **겹침을 유한하게 만드는 건 D42의 TTL**. 반증 4종 red(특히 retiring 레코드에 TTL 미적용).
  **custody는 미해결이고 거짓 주장도 아니다**(→ Risk 3).
- `make check` (pytest) → **1618 passed, 1 skipped** (2026-08-08, +1) — **테스트가 상했다**:
  `test_incident_time_to_resolve.py`는 **수정된 적이 없는데** red가 됐다. 픽스처가
  `created_at`을 하드코딩(`2026-07-29`)하는데 생산자는 **살아 있는 시계**로 7일 창을 건다 →
  **08-05에 이미 깨져 있었다**. `now` 기준 상대 배치로 교체(형제 `test_report_windows.py`의
  모양) + 가드 1건. **게이트 숫자에는 측정 날짜가 붙어야 한다** → Risk 12①.
- (이전 baseline — gate **1617 이하** / 2026-07-10~08-02 → `docs/archive/progress-2026-08.md` ·
  `docs/archive/status-baseline-2026-07.md` · `COMPLETED_SUMMARY` M13·M14.)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider(AWS/GCP/Azure/On-Prem)
코드 완비. 하네스 = overnight-harness 5 engine. 상세는 `COMPLETED_SUMMARY` M0~M15.

1-6. **Operations 파이프라인**(Detector/Analyzer/Decision/Executor + Approval Bridge, 3-Cloud
   Day2 각 4-step) · **HITL 승인**(Slack→`WaitForTaskToken`+SQS+SFN callback) · **Day1/1.5**
   (provisioning·deployment·reporting) · **Portability**(`NormalizedIncident` + provider registry)
   · **Runbook registry**(catalog + capability 스키마 + CDK seed + scan heuristic).
7-9. **AI Agents** 3종(Strands/ADK/MSFT, tool calling 검증) · **Guardian**(Policy-as-Code
   APPROVE/AUTO/REJECT) · **MCP + A2A Gateway**(kubectl/docker 9도구 + FastAPI A2A).
10-12. **On-prem K8s**(`make local-cluster` = 3노드+registry+ingress) · **Deployment/Execution
   Adapters** 4 provider(Build→Push→Deploy→Validate→Rollback / capability→action).
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지, DynamoDB Live 전용. Auth.js GitHub OAuth +
   Admin/Operator/Viewer 제어판, 복구 승인, 배포 트리거/롤백, 감사 로그. 프로덕션 배포 완료.

## Active Focus

**남은 건 Phase 4(billable, 별 승인)뿐이다.** 무과금·무승인으로 열린 작업은 소진됐다.
Phase 0·1a·1b·2·3 완결(M10~M12) · 잔여 소진(M13) · 결정 7건 닫힘(D36·D38~D43) ·
공급망 0→집행 + Phase 5 경계 + `main` 보호(M15).

**과대 해석 금지(현재 유효한 것만)**
- 스코프·배포 신원 · 이미지 서명 배포 게이트는 전부 **옵트인**(→ Risk 3·6).
- 자격증명이 테넌트-바운드인 건 **온프렘뿐**(→ Risk 10) · 파티션된 읽기 경로는 **둘뿐**.
- `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다(코드 소유자 리뷰 off → D43).
- **어드미션 미도입** · **CODEOWNERS는 라우팅** · Phase 5는 **경계까지**(UI·PR 생성 없음).

**반복해서 확인된 것**: 조사할 때마다 **기록된 이유가 진짜 구속 조건이 아니었다**
(M13→M15에서 열 번 넘게). 새 항목을 집기 전에 **그 이유를 한 번 돌려 보고 시작할 것.**

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다 — 단 "실 데이터 삭제"는 틀렸다(2026-08-08
   재측정)** — 코드 갭은 유효: Cosmos DefaultTimeToLive 미설정, Firestore TTL 정책 부재 →
   스토어가 생기면 **어느 쪽도 만료 안 됨**. 하지만 **스토어가 아예 없다**: GCP는 platform-agent
   프로젝트에 **Firestore API가 켜진 적조차 없고**, Azure엔 `platform-agent` DB가 없다 →
   **지울 데이터 0**. 승인 항목이 아니라 **Phase 4(프로비저닝, billable)** 선행 항목이다.
   증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log`.
3. **⚠️ 스코프·배포 신원은 집행 가능하지만 옵트인이다(2026-07-31, D38·D39)** — 세 경로가
   닫혔다(인시던트 생산자 · 배포 축소 신원 · MCP 무스코프 읽기 거부). **기본값은 미설정**이라
   `PLATFORM_{CREDENTIAL_DIR,APPROVAL_SIGNING_KEY}` 없으면 인시던트는 전부 거부,
   `PLATFORM_DEPLOY_KUBECONFIG` 없으면 배포는 ambient(=cluster-admin). 즉 **"설정하면 집행되고,
   안 하면 조용히 안 된다."** 묻기 `scripts/probe_scope_reachability.py`·`make
   deploy-identity-check` · 켜기 `make scope-credentials`·`make deploy-identity`.
   **남은 것**: 배포 신원은 테넌트를 구분 안 함(결정 5 C/D=라우터 인증 선행) · **키 custody**
   (rotation은 닫힘) · 클라우드 3종은 Risk 10.
4. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 시 가동 + WIF OIDC 과금 체크.
5. **k3s는 집행하지만 proven 집합엔 없다 — 결정 4 = D40으로 닫힘(2026-08-01)** — 집행은 라이브
   증명(07-29), 시맨틱은 미증명. 네 문서가 반복한 "피어 테넌트 부재"는 **참이지만 구속력이
   없었다**: 실제로는 넷 — ①acme/prod는 **네임스페이스 1개**(피어 보기 전에 exit) ③**순환**
   (프로브가 proven 집합을 전제 = **승격하려면 먼저 승격해야 한다**) ④**k3s-lab에 테넌시 실체
   0** → 넣어도 **보호 대상 0**. 열리는 조건: k3s-lab에 워크로드. → D40, `docs/plans/2026-08-01-k3s-proven-substrate.md`.
6. **공급망: 생산자·소비자·CI 키리스는 섰고, 어드미션은 업스트림 대기(2026-08-08)** —
   아침까지 보증은 **0**이었다(`cosign sign` 0건 · CI 없음 · 검증기 호출자가 자기 테스트뿐 ·
   맨 태그라 서명이 놓일 주소도 없음). 지금은 `make sign-image`(다이제스트 서명→**레포 자신의
   게이트로 검증**) + `image_trust`(배포 직전 거부, **exit 2 "검사 못 함"도 거부**) +
   CI 키리스(Fulcio 단명 인증서 = custody 해소)까지 라이브. **과대 해석 금지**: 배포 게이트는
   **옵트인**(`PLATFORM_REQUIRE_SIGNED_IMAGES`)이고 **온프렘 진입점 하나**만 덮는다 · 로컬
   `make sign-image`는 여전히 **dev 키** · Rekor 기록은 **영구 공개** · **어드미션 미도입**.
   어드미션은 **cosign v3 ↔ policy-controller 서명 저장 위치 불일치**로 막혔다(v0.15.1도 동일,
   v2 서명은 통과 — 양방향 실증). ⚠️**우리 게이트는 같은 이미지에 VERIFIED를 준다** = **"검증됨"이
   도구마다 다르고 우리는 못 본다**. 증거 `docs/evidence/{ci-keyless-signing,
   image-signature-deploy-gate,cosign-admission-kind-attempt}.log` · M15.

7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(구버전 에이전트 페이로드). 롤링 업그레이드 중엔 허브가 두
   버전을 동시에 서빙하므로 **푸시 신규 필드는 항상 optional + 폴백**으로 다룬다.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 파드가 admission에서
   거부되는데 **Argo는 Synced로 보인다**(파드 0개인 채). **새 애드온마다 확인이 필요**하다 — 렌더된
   파드 스펙을 테넌트 ns에 `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 게 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(키 철자가 차트마다 다름).
9. *(해소, 2026-08-02)* **Capsule deprecation** — 두 필드 다 이관, 경고 0건 → D41.
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 액션이 **어느 네임스페이스를
   건드릴지**만 정하고 토큰을 테넌트에 묶지 않는다. GCP는 프로젝트 전역 신원 하나, **Azure는 ARM에서
   클러스터 admin kubeconfig를 받아온다**. 자격증명 자체가 경계인 것은 **온프렘뿐** → Phase 4.
11. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 없음·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음.
12. **게이트의 초록에는 조건이 붙는다 — 세 가지가 같은 계열(2026-08-08)** —
   ①**시간**: 픽스처가 절대 시각을 하드코딩하고 생산자가 살아 있는 시계로 창을 걸면 통과는
   **달력이 움직이기 전까지만** 참이다(07-29 픽스처 + 7일 창 → 08-05 만료). **게이트 숫자는
   날짜 없이는 주장이 아니다.** ②**환경**: 게이트가 **선언되지 않은 패키지** 위에서 통과하고
   있었다(OTel exporter 미선언 → 새 클론은 아무도 통과 못 함). CI가 잡았고, 로컬에서는 원리상
   안 드러난다. `requires-python = ">=3.11"`도 **아무도 확인한 적 없는 주장**이었다(CI는 검증된
   3.13 고정). **②의 역방향도 실측됐다**: 로컬이 통과시키고 **CI가 아예 안 도는** 경우 —
   terraform 검증 2건이 CI에서만 조용히 skip됐다(위 baseline). **skip은 실패가 아니라서
   검사 안 하는 게이트와 통과한 게이트가 같은 색**이고, 그래서 게이트 숫자에는 날짜뿐
   아니라 **어느 기계에서 쟀는지**도 붙어야 한다. ③**하중**: **행복 경로만 태운 가드는
   하중을 받지 않는다** — 안전망을 통째로 지워도 14개가 초록이었다. **새 가드를 쓰면
   지워 보고 red가 나는지 확인할 것.** 증거 `docs/evidence/{ci-keyless-signing,
   ci-terraform-validate-skipped}.log` · M15.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
