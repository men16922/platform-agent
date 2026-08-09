# STATUS — platform-agent

최종 갱신: 2026-08-09

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` → **1737 passed, 1 skipped** (2026-08-09, +18, **로컬 ↔ CI 일치**) — 프로브를
  **정기 실행**하려다 **진짜 구속 조건**을 만났다: LaunchAgent는 `~/Desktop` 아래 레포를
  **읽지 못한다**(macOS TCC — 실측 exit 127 + `Operation not permitted`). 뚫으려면 `/bin/zsh`에
  **Full Disk Access** = 모든 zsh 스크립트에 전체 디스크 → **안 했다**. 대신 **이미 허가된**
  대화형 셸에 태웠다(터미널당 하루 한 번). `make spend-watch` = **무엇이 새로 과금되기
  시작했는가**(임계값 없음 — 예산이 "얼마나"를 이미 답한다). 변이 10건 전부 red.
  증거 `spend-watch-launchd-blocked-by-tcc.log`.
- `make check` → **1719, 1 skipped** (2026-08-09) — Azure 크레딧 상계를 닫았다: 7월
  `ActualCost` **=** `AmortizedCost`(소수점 열째 자리까지) · ChargeType `Usage` 한 행 →
  **상계 없음**. ⚠️단 **예약·절약 플랜이 없어서**지 API 성질이 아니다. 덤: **429가 실제
  실패 모드**라 이유를 출력하게 했다(`_why`). 증거 `azure-credit-netting-does-not-apply-yet.log`.
- `make check` → **1718, 1 skipped** (2026-08-09) — **Azure는 잴 수 있었다**:
  `az consumption usage list`가 **28행 전부 `pretaxCost` null**로 exit 0 → 합계 0인데 Cost
  Management는 같은 창에 **₩1,989**(세 번째 같은 계열). 변이 7건 red.
  증거 `azure-consumption-cli-returns-null-cost.log`.
- `make check` → **1709/1708/1699** (2026-08-09, **로컬 ↔ CI 일치**, PR #14·#16·#17) —
  spend-check의 **GCP 누락**(빠진 provider는 잰 0과 구별되지 않는다 · exit 2로는 안 만들었다)
  · **docstring이 코드보다 낡은 모델**을 가리킴. ⚠️두 함정: 가드가 **게이트에서 라이브
  gcloud를 호출**했고(21.97s → 0.02s), 반증 중 **`.pyc`에 속았다**(바이트 수가 같다)
  — **반증 루프는 캐시를 지우고 돌릴 것.**
- (이전 baseline — gate **1697 이하** / 07-10~08-09 및 `main` 보호 확인 →
  `docs/archive/{status-baseline-2026-07,progress-2026-08}.md` · `COMPLETED_SUMMARY` M13·M14.)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider 코드 완비 · 하네스
= overnight-harness 5 engine. 상세는 `COMPLETED_SUMMARY` M0~M15.

1-12. **Operations 파이프라인**(Detector/Analyzer/Decision/Executor + Approval Bridge, 3-Cloud Day2 각 4-step) · **HITL 승인**(Slack→`WaitForTaskToken`+SQS+SFN) · **Day1/1.5** · **Portability** · **Runbook registry** · **AI Agents** 3종(Strands/ADK/MSFT) · **Guardian**(Policy-as-Code) · **MCP + A2A Gateway** · **On-prem K8s** · **Deployment/Execution Adapters** 4 provider.
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지, DynamoDB Live 전용 · Auth.js GitHub OAuth + Admin/Operator/Viewer 제어판, 복구 승인, 배포 트리거/롤백, 감사 로그. 프로덕션 배포 완료.

## Active Focus

**Phase 4는 산정까지 끝났고 남은 건 사용자 결정이다**(→ `docs/plans/2026-08-08-phase4-scope-and-cost.md`):
**4a**(관리형 어댑터, 원격 클러스터 불요) ≈$5/월 · **4b**(원격 클러스터+DR) ≈$185/월. **$0 선행
둘 중 ₩20 예산은 닫혔고**, 남은 **결제 내보내기**는 콘솔 수동이라 사용자 몫 → Risk 4.

**과대 해석 금지(현재 유효한 것만)**
- 스코프·배포 신원 · 이미지 서명 배포 게이트는 전부 **옵트인**(→ Risk 3·6).
- 자격증명이 테넌트-바운드인 건 **온프렘뿐**(→ Risk 10) · 파티션된 읽기 경로는 **둘뿐**.
- `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다(코드 소유자 리뷰 off → D43).
- **어드미션 미도입** · **CODEOWNERS는 라우팅** · Phase 5는 **경계까지**(UI·PR 생성 없음).

**반복 확인**: 기록된 이유가 진짜 구속 조건이 아닐 때가 많다(M13→M15). 단 **늘 그런 건
아니다** — 08-08 재측정 4건 중 3건, **08-09 GCP 3건은 전부 성립**했다. 그래도 돌려 볼 값은
있었다(성립을 확인하다 **프로브의 provider 누락**이 나왔다). **"없다"는 어떻게 봤는지까지.**

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다 — 단 "실 데이터 삭제"는 틀렸다(2026-08-08
   재측정)** — 코드 갭은 유효(Cosmos·Firestore 둘 다 TTL 미설정 → 스토어가 생기면 만료 안 됨).
   하지만 **스토어가 아예 없다**(Firestore API 미활성 · Azure에 DB 없음) → **지울 데이터 0**.
   승인 항목이 아니라 **Phase 4** 선행. 증거 `gcp-azure-retention-nothing-to-delete.log`.
3. **⚠️ 스코프·배포 신원은 집행 가능하지만 옵트인이다(2026-07-31, D38·D39)** — 세 경로가
   닫혔다(인시던트 생산자 · 배포 축소 신원 · MCP 무스코프 읽기 거부). **기본값은 미설정**이라
   `PLATFORM_{CREDENTIAL_DIR,APPROVAL_SIGNING_KEY}` 없으면 인시던트는 전부 거부,
   `PLATFORM_DEPLOY_KUBECONFIG` 없으면 배포는 ambient(=cluster-admin). 즉 **"설정하면 집행되고,
   안 하면 조용히 안 된다."** 묻기 `scripts/probe_scope_reachability.py`·`make
   deploy-identity-check` · 켜기 `make scope-credentials`·`make deploy-identity`.
   **남은 것**: 배포 신원은 테넌트를 구분 안 함(결정 5 C/D=라우터 인증 선행) · **키 custody**
   (rotation은 닫힘) · 클라우드 3종은 Risk 10.
4. **세 클라우드 다 기본값이 안심시키는 답을 준다 — 셋 다 호출은 성공한다(2026-08-09 실측)**
   ①**AWS**: `aws ce`는 **크레딧 포함** 집계라 "$0"을 두 번 보고했다(실제 **$8.81**) →
   `Not RECORD_TYPE in [Credit,Refund]` + **전 리전 스윕**(원인 `slackops-devops-agent` 18일째,
   **중지함** — **점검이 아니라 경보가 잡았다**). ②**Azure**: `az consumption usage list`가
   **cost 없는 행**을 주고(28행 전부 null → 합계 0) **Cost Management만 실지출을 준다**
   (7월 **₩22,630** · 8월 MTD ₩1,989 = ACR Basic 고정 요금, **다른 프로젝트 것이라 두었다**).
   ③**GCP는 아예 못 잰다** — Cloud Billing v1 **19 메서드에 지출 0** · Budgets에 실지출 readout
   없음 → **BQ 내보내기(콘솔 수동)가 유일**, 데이터셋은 있고 **테이블 0개**
   (`docs/GCP_BILLING_EXPORT_SETUP.md`). ④**아무도 안 돌린다**가 마지막 구멍이었다 →
   `make spend-watch`(무엇이 **새로** 과금되기 시작했는가) + 터미널당 하루 한 번 훅;
   **launchd는 TCC로 막힌다**. 셋 다 `make spend-check`가 박아 뒀고 **관측 구멍은
   이제 GCP 하나**. ₩20 예산 → ₩28,000. 증거 `gcp-budget-always-firing-fixed.log` ·
   `gcp-actual-spend-has-no-api.log` · `azure-consumption-cli-returns-null-cost.log`.
5. **k3s는 집행하지만 proven 집합엔 없다 — 결정 4 = D40으로 닫힘(2026-08-01)** — 집행은 라이브
   증명(07-29), 시맨틱은 미증명. 문서들이 반복한 "피어 테넌트 부재"는 **참이지만 구속력이
   없었다**(실제 이유는 넷: 네임스페이스 1개 · **순환**(승격하려면 먼저 승격해야 한다) ·
   **k3s-lab에 테넌시 실체 0**). 열리는 조건: k3s-lab에 워크로드 → D40, `docs/plans/2026-08-01-k3s-proven-substrate.md`.
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
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로 죽었는데 `tsc`는 내내 초록이었다(구버전 페이로드). 롤링 업그레이드 중엔 허브가 두 버전을 동시에 서빙하므로 **푸시 신규 필드는 항상 optional + 폴백**.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 파드가 admission에서 거부되는데 **Argo는 Synced로 보인다**(파드 0개인 채). **새 애드온마다 확인**할 것 — 렌더된 파드 스펙을 테넌트 ns에 `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 게 가장 싸다. values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(키 철자가 차트마다 다름).
9. *(해소)* Capsule deprecation(08-02, D41) · GCP 예산 상시 발화 → ₩28,000(08-09).
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 액션이 **어느 네임스페이스를
   건드릴지**만 정하고 토큰을 테넌트에 묶지 않는다. GCP는 프로젝트 전역 신원 하나, **Azure는 ARM에서
   클러스터 admin kubeconfig를 받아온다**. 자격증명 자체가 경계인 것은 **온프렘뿐** → Phase 4.
11. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 없음·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음.
12. **게이트의 초록에는 조건이 붙는다 — 세 가지가 같은 계열(2026-08-08)** —
   ①**시간**: 픽스처가 절대 시각을 하드코딩하고 생산자가 살아 있는 시계로 창을 걸면 통과는
   **달력이 움직이기 전까지만** 참이다(07-29 픽스처 + 7일 창 → 08-05 만료). **게이트 숫자는
   날짜 없이는 주장이 아니다.** ②**환경**: 게이트가 **선언되지 않은 패키지** 위에서 통과하고
   있었다(OTel exporter 미선언 → 새 클론은 아무도 통과 못 함). CI가 잡았고 로컬에서는 원리상
   안 드러난다(`requires-python = ">=3.11"`도 **아무도 확인한 적 없는 주장**). **역방향도
   실측**: 로컬이 통과시키고 **CI가 안 도는** 경우 — **skip은 실패가 아니라서 검사 안 하는
   게이트와 통과한 게이트가 같은 색**이다 → 숫자엔 날짜와 **잰 기계**를 붙일 것.
   ③**하중**: **행복 경로만 태운 가드는 하중을 받지 않는다**(안전망을 지워도 14개가 초록)
   → **새 가드는 지워 보고 red를 확인할 것.** 증거
   `docs/evidence/{ci-keyless-signing,ci-terraform-validate-skipped}.log` · M15.
- (그 밖의 해소 이력 — Slack App 미연결(07-19)·A2A discovery(07-14)·추적 IA 실증(07-13)·NEXT_PUBLIC 인라인(07-13) — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
