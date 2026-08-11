# STATUS — platform-agent

최종 갱신: 2026-08-11

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` → **1789 passed, 1 skipped** (2026-08-11, 1737→**+52**, 로컬 macOS·py3.13;
  CI가 #24~#27 **네 지점 전부** 숫자까지 일치, 최종은 #28) — **리포트가 독자에게 갈린 채 도착하고
  있었다**(본문 stdout / 판정 stderr → 파이프에선 절이 빈다), 그리고 **가드가 그걸 원리상
  못 봤다**(→ Risk 12④). 프로브 1건 → `scripts/` CLI **22개 전수** + `src/` 확인까지.
  **훑는 방향을 뒤집은 게 결정적**: `readouterr` 사용처가 아니라 **`sys.stderr`를 쓰는
  프로그램**을 뒤지니 **테스트에 이름조차 없던 2개**가 나왔다. 그리고 **세 번째 문**이 있었다
  — `src/`는 핸들러를 안 붙여 `logger.warning`이 `lastResort`로 **stderr**에 나간다(`print`
  없는 경로). 변이 **30건 red, 생존 0**. 경위·산출은 **M17이 권위**. 증거 `spend-probe-report-split-across-streams.log` ·
  `report-streams-swept-across-all-clis.log`.
- `make check` → **1737 passed, 1 skipped** (2026-08-09, +18, **로컬 ↔ CI 일치**) — 프로브를
  **정기 실행**하려다 **진짜 구속 조건**을 만났다: LaunchAgent는 `~/Desktop` 아래 레포를
  **읽지 못한다**(macOS TCC — 실측 exit 127 + `Operation not permitted`). 뚫으려면 `/bin/zsh`에
  **Full Disk Access** = 모든 zsh 스크립트에 전체 디스크 → **안 했다**. 대신 **이미 허가된**
  대화형 셸에 태웠다(터미널당 하루 한 번). `make spend-watch` = **무엇이 새로 과금되기
  시작했는가**(임계값 없음 — 예산이 "얼마나"를 이미 답한다). 변이 10건 전부 red.
  증거 `spend-watch-launchd-blocked-by-tcc.log`.
- `make check` → **1719 / 1718 / 1709 / 1708 / 1699** (2026-08-09, PR #14·#16·#17) — 비용
  관측을 세 provider로 세운 연쇄. 상세·증거는 `COMPLETED_SUMMARY` **M16**과
  `docs/archive/progress-2026-08.md`가 권위. 여기 남길 것은 **아직 유효한 함정 둘**뿐:
  가드가 **게이트에서 라이브 `gcloud`를 호출**하고 있었고(21.97s → 0.02s), 반증 중
  **`.pyc`에 속았다**(바이트 수가 같다) — **반증 루프는 캐시를 지우고 돌릴 것.**
- (이전 baseline — gate **1697 이하** / 07-10~08-09 및 `main` 보호 확인 →
  `docs/archive/{status-baseline-2026-07,progress-2026-08}.md` · `COMPLETED_SUMMARY` M13·M14.)

## Active Focus

> **"무엇이 도는가"는 여기 적지 말 것** — `AGENT_BRIEF` **Snapshot**과 `COMPLETED_SUMMARY`
> **M0~M17**이 권위다(08-11에 중복 세 문단을 접었다). 이 파일은 **무엇을 믿어도 되는가**만 답한다.

**Phase 4는 산정까지 끝났고 남은 건 사용자 결정이다**(→ `docs/plans/2026-08-08-phase4-scope-and-cost.md`):
**4a**(관리형 어댑터, 원격 클러스터 불요) ≈$5/월 · **4b**(원격 클러스터+DR) ≈$185/월. **$0 선행
둘 중 ₩20 예산은 닫혔고**, 남은 **결제 내보내기**는 콘솔 수동이라 사용자 몫 → Risk 4.

**과대 해석 금지(현재 유효한 것만)**
- 스코프·배포 신원 · 이미지 서명 배포 게이트는 전부 **옵트인**(→ Risk 3·6).
- 자격증명이 테넌트-바운드인 건 **온프렘뿐**(→ Risk 10) · 파티션된 읽기 경로는 **둘뿐**.
- `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다(코드 소유자 리뷰 off → D43).
- **어드미션 미도입** · **CODEOWNERS는 라우팅** · Phase 5는 **경계까지**(UI·PR 생성 없음).

**반복 확인**: 기록된 이유가 진짜 구속 조건이 아닐 때가 많다(M13→M15). 단 **늘 그런 건 아니다**
— 재측정이 성립한 쪽이 더 많았고, 그래도 값은 나왔다(성립을 확인하다 **프로브의 provider
누락**이 나왔고, 프로브를 한 번 돌리다 **리포터 자신의 결함**이 나왔다). **"없다"는 어떻게
봤는지까지** — 그리고 **목록을 훑을 땐 목록이 무엇의 그림자인지부터**(Risk 12④ⓐ).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다 — 단 "실 데이터 삭제"는 틀렸다(2026-08-08
   재측정)** — 코드 갭은 유효(Cosmos·Firestore 둘 다 TTL 미설정 → 스토어가 생기면 만료 안 됨).
   하지만 **스토어가 아예 없다**(Firestore API 미활성 · Azure에 DB 없음) → **지울 데이터 0**.
   승인 항목이 아니라 **Phase 4** 선행. 증거 `gcp-azure-retention-nothing-to-delete.log`.
3. **⚠️ 스코프·배포 신원은 집행 가능하지만 옵트인이다(2026-07-31, D38·D39)** — 세 경로가
   닫혔다(인시던트 생산자 · 배포 축소 신원 · MCP 무스코프 읽기 거부). **기본값은 미설정**이라
   `PLATFORM_{CREDENTIAL_DIR,APPROVAL_SIGNING_KEY}` 없으면 인시던트는 전부 거부,
   `PLATFORM_DEPLOY_KUBECONFIG` 없으면 배포는 ambient(=cluster-admin) — **"설정하면 집행되고,
   안 하면 조용히 안 된다."** 묻기 `probe_scope_reachability.py`·`make deploy-identity-check` ·
   켜기 `make scope-credentials`·`make deploy-identity`. **남은 것**: 배포 신원의 테넌트 구분
   (결정 5 C/D=라우터 인증 선행) · **키 custody**(rotation은 닫힘) · 클라우드 3종은 Risk 10.
4. **세 클라우드 다 기본값이 안심시키는 답을 준다 — 셋 다 호출은 성공한다** — 어떻게 셋 다
   틀렸는지는 **M16이 권위**(증거 3건도 거기). **지금 유효한 것만**: 셋 다 `make spend-check`에
   박혔고 **관측 구멍은 GCP 하나**(BQ 내보내기 = 콘솔 수동, 데이터셋은 있고 **테이블 0개** →
   `docs/GCP_BILLING_EXPORT_SETUP.md`) · ₩20 예산 → **₩28,000** · `spend-watch`는 터미널당
   하루 한 번(**launchd는 TCC로 막힌다**) · **측정 자체가 과금된다**(CE 요청당 $0.01 = 월
   ~$0.30) · ⚠️**CE는 당일치를 늦게 보고한다 — 오늘 줄의 0은 잰 0이 아니다** · 8월 Azure
   MTD는 **다른 프로젝트의 ACR 고정 요금**이라 두었다.
5. **k3s는 집행하지만 proven 집합엔 없다 — 결정 4 = D40으로 닫힘(2026-08-01)** — 집행은 라이브
   증명(07-29), 시맨틱은 미증명. 문서들이 반복한 "피어 테넌트 부재"는 **참이지만 구속력이
   없었다**(진짜 이유는 넷 — 네임스페이스 1개 · **순환**(승격하려면 먼저 승격해야 한다) ·
   k3s-lab에 테넌시 실체 0). 열리는 조건: k3s-lab에 워크로드 → D40 · `docs/plans/2026-08-01-k3s-proven-substrate.md`.
6. **공급망: 생산자·소비자·CI 키리스는 섰고, 어드미션은 업스트림 대기(2026-08-08)** —
   0에서 여기까지 온 경위는 **M15가 권위**. 지금은 `make sign-image`(다이제스트 서명→**레포
   자신의 게이트로 검증**) + `image_trust`(배포 직전 거부, **exit 2 "검사 못 함"도 거부**) +
   CI 키리스(Fulcio 단명 인증서 = custody 해소)까지 라이브. **과대 해석 금지**: 배포 게이트는
   **옵트인**(`PLATFORM_REQUIRE_SIGNED_IMAGES`)이고 **온프렘 진입점 하나**만 덮는다 · 로컬
   `make sign-image`는 여전히 **dev 키** · Rekor 기록은 **영구 공개** · **어드미션 미도입**.
   어드미션은 **cosign v3 ↔ policy-controller 서명 저장 위치 불일치**로 막혔다(v0.15.1도 동일,
   v2 서명은 통과 — 양방향 실증). ⚠️**우리 게이트는 같은 이미지에 VERIFIED를 준다** = **"검증됨"이
   도구마다 다르고 우리는 못 본다**. 증거 `docs/evidence/{ci-keyless-signing,
   image-signature-deploy-gate,cosign-admission-kind-attempt}.log` · M15.
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브 페이지가 `posture.namespaces.length`로 죽는 동안 `tsc`는 내내 초록이었다(구버전 페이로드). 롤링 중엔 허브가 두 버전을 동시에 서빙 → **푸시 신규 필드는 항상 optional + 폴백**.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 안 돈다** — 파드는 admission에서 거부되는데 **Argo는 Synced로 보인다**(파드 0개인 채). **새 애드온마다** 렌더된 파드 스펙을 테넌트 ns에 `kubectl apply --dry-run=server`로 던져 API 서버에 직접 물을 것. values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(키 철자가 차트마다 다름).
9. *(해소)* Capsule deprecation(08-02, D41) · GCP 예산 상시 발화 → ₩28,000(08-09) · 리포트 스트림 분리(08-11, M17).
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 액션이 **어느 네임스페이스를
   건드릴지**만 정하고 토큰을 테넌트에 묶지 않는다. GCP는 프로젝트 전역 신원 하나, **Azure는 ARM에서
   클러스터 admin kubeconfig를 받아온다**. 자격증명 자체가 경계인 것은 **온프렘뿐** → Phase 4.
11. **Dashboard dependency audit** — Next.js 16.2.10 번들 PostCSS(<8.5.10) moderate 2건. 16.2.x 패치 없음 · `audit fix --force`는 next@9 다운그레이드(07-13 재검증) → **upstream 대기 확정**, 빌드타임 경로라 런타임 위험 낮음.
12. **게이트의 초록에는 조건이 붙는다 — 넷이 같은 계열(2026-08-08~11)** —
   ①**시간**: 픽스처가 절대 시각을 하드코딩하고 생산자가 살아 있는 시계로 창을 걸면 통과는
   **달력이 움직이기 전까지만** 참이다(07-29 픽스처 + 7일 창 → 08-05 만료). **게이트 숫자는
   날짜 없이는 주장이 아니다.** ②**환경**: 게이트가 **선언되지 않은 패키지** 위에서 통과하고
   있었다(OTel exporter 미선언 → 새 클론은 아무도 통과 못 함). CI가 잡았고 로컬에서는 원리상
   안 드러난다(`requires-python = ">=3.11"`도 **아무도 확인한 적 없는 주장**). **역방향도
   실측**: 로컬이 통과시키고 **CI가 안 도는** 경우 — **skip은 실패가 아니라서 검사 안 하는
   게이트와 통과한 게이트가 같은 색**이다 → 숫자엔 날짜와 **잰 기계**를 붙일 것.
   ③**하중**: **행복 경로만 태운 가드는 하중을 받지 않는다**(안전망을 지워도 14개가 초록)
   → **새 가드는 지워 보고 red를 확인할 것.** ④**관측 지점 — 08-11 전수 훑기(상세는 M17)**:
   **가드는 독자가 읽는 그 물건에 대고 물을 것.** 결론 다섯 — ⓐ**결함을 그 그림자로 세지 말
   것**(잘못 문 가드 3건 vs 깨진 프로그램 9건, 둘은 **테스트에 이름조차 없었다**) ·
   ⓑ**"stderr 금지"가 아니다**(독자가 파서면 의무가 거꾸로 → 22개를 REPORT/DOCUMENT/DUAL로
   분류, 미분류는 red) · ⓒ**절반만 묻는 가드**(경고의 **주장**만 묻고 **지시**를 안 물으면
   지시를 지우는 변이가 산다) · ⓓ**문이 넷이다** — `print`·stderr 외에 **로깅**(`src/`엔
   핸들러 0건 → `lastResort`가 WARNING+ 를 stderr로; REPORT 4개가 닿고 **둘은 자격증명 경계
   사건**)과 **잡히지 않은 예외**(트레이스백=stderr·exit 1; `watch_cloud_spend`에선 1이
   "**새로 과금됐다**"라 **못 쟀는데 경보가 된다**) · ⓔ**"클러스터가 필요하다"는 잰 게
   아니었다** — **두 번** 그랬다(둘째는 "자격증명·스택이 필요하다"). 매번 그 문장은 **성공
   경로**를 묘사했고 **실패 경로는 공짜였다**; 시험할 때마다 결함이 나왔다(합 6건). 파이프 뒤
   4→**13 invocation/11 CLI**. **남은 것**: 로깅 문은 REPORT 4개 · `slack_live_approval` 이중 노후화.
   증거 `docs/evidence/{ci-keyless-signing,ci-terraform-validate-skipped,
   spend-probe-report-split-across-streams,report-streams-swept-across-all-clis}.log` · M15·M16.
- (그 밖의 해소 이력 — Slack App 미연결(07-19)·A2A discovery(07-14)·추적 IA 실증(07-13)·NEXT_PUBLIC 인라인(07-13) — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
