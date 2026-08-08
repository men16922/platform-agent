# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-08

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-08 — 문서 정리: 예산보다 진입점이 문제였다

- Status: 하루치 증분이 쌓여 `PROGRESS_LOG` 329줄(예산 2.7배) 등 3종이 초과 → `/tidy-docs`.
  **삭제 없음**, 전부 아카이브 이동 또는 압축.
- Changed: log 329→**80**(최신 2건 유지 + Cosign 항목 90→18 압축, 6건은
  `archive/progress-2026-08.md`로) · plan 192→**118**(완료 `[x]` 5건 제거 → M15) ·
  status 201→**126**(baseline 12→5건, Active Focus 재작성, 역량 목록 압축) ·
  `COMPLETED_SUMMARY` **M15 신설** · `DECISIONS` **D43**.
- Changed(리스크 병합): Risk **12·13·14**가 전부 *"게이트의 초록에는 조건이 붙는다"*는
  한 계열이라 **Risk 12 ①시간 ②환경 ③하중**으로 합치고 참조를 정정했다.
- Verified: `make check` **1668**. 참조 무결성 확인(아카이브 2종 · M10/M12/M13/M14/M15 전부 존재).
  예산: brief 43/60 · plan 118/120 · log 80/120 ✅, **status 126/120 (+6)**.
- Changed(정리 중 드러난 사실 오류 2건): `AGENT_BRIEF` 가드레일의 **"에이전트=Python 3.11"**은
  오늘 측정과 어긋난다(3.11에서 2건 red) → "게이트는 **3.13에서만 검증됨**"으로 교체 ·
  `NEXT_PLAN` 완료 이력 포인터가 M14까지만 가리켜 M15 추가.
- Blockers: `main`이 보호되어 이 문서 변경은 **PR로만** 들어간다. status +6줄은 더 줄이려면
  현재 판단에 필요한 정보를 깎아야 해서 남겨 뒀다.
- 품질 메모: **줄 수는 예산 안이어도 진입점은 죽어 있을 수 있다.** `AGENT_BRIEF`는 42줄로
  통과였지만 `▶ NEXT SESSION` **한 줄이 6,057자**로 10세션치 이력을 안고 있었다 — `/sync`가
  가장 먼저 읽는 파일인데 1분 문맥 역할을 못 했다. 최장 줄 **6,057→533자**. **예산은 줄 수가
  아니라 읽는 데 드는 시간으로 재야 한다.**
- Next: Phase 4(billable, 별 승인)만 남았다.

## 2026-08-08 — 게이트를 집행으로: 브랜치 보호 + TS의 두 번째 진실 공급원 제거

- Status: 무과금으로 남은 두 항목을 소진. 오늘 세운 CI를 **실제 병합 조건**으로 만들고,
  선행 조건이 갖춰진 TS 스윕 잔여를 닫았다.
- Changed(TS 닫힌 섬): NEXT_PLAN이 요구한 **실 레지스트리 대조**를 하니 기록보다 컸다 —
  타입 5종뿐 아니라 **`namespaceFor`·`credentialScope`도 호출자 0**이었고, 둘은 **살아 있는
  파이썬 규칙의 복제본**이다(`Tenant.namespace_for`=`delivery.py`+스코프 민팅 ·
  `IsolationTier.credential_scope`=`registry.py`). **지운 이유는 죽은 코드라서가 아니라 두 번째
  진실 공급원이라서다** — 아무도 실행하지 않는 인가 규칙은 조용히 어긋나고 나중에 배선하는
  사람은 그걸 믿는다. `Quota`의 "외부 참조" 1건은 **JSX 텍스트**였다. `tsc` clean.
- Changed(브랜치 보호): `main`에 **PR 필수 + `check`(=`make check`) 통과 필수**, 관리자 포함,
  force push·브랜치 삭제 금지. ⚠️**`require code owner review`는 일부러 껐다** — 협업자가
  1명이라 자기 PR을 승인할 수 없어 **만족 불가능한 규칙**이 되고, **우회해야 동작하는 규칙은
  우회를 습관으로 만든다**. 즉 집행하는 건 **게이트(기계)**이고 소유권은 아직 **라우팅**이다.
- Verified: 설정 API의 200은 "저장됐다"이지 "막는다"가 아니라 **일부러 직접 push**를 시도했다 →
  `Changes must be made through a pull request` + `Required status check "check" is expected` →
  `[remote rejected]`. **두 규칙 모두 발화.** 프로브 커밋은 되돌렸다. 이어서 남은 문서를
  **PR #1**로 올려 CI 통과→`MERGEABLE/CLEAN`→squash 병합까지 **새 흐름을 끝까지 돌렸다**.
  `make check` **1668**, 증거 `docs/evidence/branch-protection-enforced.log`.
- Blockers: **`main` 직접 push 불가 — 나를 포함해서.** 이후 변경은 PR로 들어간다.
  되돌리기는 설정 하나(`gh api -X DELETE .../branches/main/protection`).
- 품질 메모: **켰다고 말하기 전에 막는지 물어봐야 한다.** 설정이 저장된 것과 집행되는 것은
  다르고, 그 차이는 오늘만 네 번 나왔다(서명/소비자/어드미션/보호). 그리고 **만족 불가능한
  규칙을 켜지 않은 것**도 같은 규율이다 — 집행하지 않는 것을 광고하지 않는 것과, 광고만 하려고
  집행을 흉내 내지 않는 것은 한 가지다.
- Next: **Phase 4(billable)만 남았다** — 별 승인 사항.

## 2026-08-08 — Phase 5의 경계부터: 문장이던 불변식을 반증 가능하게 (gate 1651→1668)

- Status: 무과금으로 갈 수 있는 유일한 항목이 Phase 5라 착수. **UI가 아니라 경계부터** 세웠다.
- Verified(조사): 레지스트리는 레포 안 `platform/tenants/*.yaml`이고, **모든 테넌트 파일 헤더가
  Phase 0부터 이렇게 적어 두고 있었다** — "path-scoped CODEOWNERS가 쓰기를 막고, 대시보드의
  Phase 5 attach 흐름은 **오직 이 파일만** PR할 수 있다". 그런데 **그걸 반증할 수 있는 게
  아무것도 없었다**(CODEOWNERS 0 · PR 코드 0 · UI 0).
- Changed: `src/agents/platform/registry_write.py` — **텍스트로 편집하고 의미로 검증**한다.
  이 파일들은 대부분이 주석이고 그 주석이 이 레포가 재발견에 값을 치른 근거라 YAML
  재직렬화는 **전부 지운다**(유효한 파일을 만들면서). 그래서 삽입은 외과적이고, 그건 그것대로
  깨지기 쉬우므로 **결과를 다시 파싱해 원본과 데이터로 비교**한다 — 허용되는 차이는 **키 하나**뿐.
  테넌트 이름은 **경로가 되기 전에** 슬러그로 검증하고(`../globex` 거부), 만들어진 경로가
  tenants 디렉터리 안인지 **한 번 더** 본다(규칙 하나 + 리팩터링 대비 가드 하나).
  **attach는 upgrade가 아니다** — 이미 선언된 capability는 거부(조용히 버전 올리면 PR이
  적혀 있지 않은 것에 승인된다). `scripts/attach_addon.py`(기본 dry-run) · `.github/CODEOWNERS`.
- Verified: `make check` **1668**(+17). 반증 4종 개별 red — 경로 검증 · 착지 위치 검증 ·
  "한 키만" 비교 · attach/upgrade 구분.
- 품질 메모: **반증 패스가 진짜 구멍을 찾았다.** `_assert_only_change`를 통째로 지워도
  **14개가 전부 초록**이었다 — 전부 **행복 경로**만 태워서 그 안전망이 한 번도 하중을 받지
  않았기 때문이다. "아무 문제 없을 때만 성립하는 가드는 가드가 아니다." 편집을 **일부러
  틀리게** 만드는 테스트 3종을 추가하고 나서야 red가 됐다. 그리고 반증 스크립트 자체도 한 번
  틀렸다(들여쓰기가 안 맞아 치환이 조용히 no-op) — **반증도 측정해야 한다.**
- Blockers: 대시보드 UI와 실제 PR 생성은 안 했다(후자는 외부 동작). ⚠️**CODEOWNERS는
  리뷰어를 지정할 뿐 아무것도 막지 않는다** — 브랜치 보호가 없고, 팀 이름이 틀려도 GitHub는
  **조용히 무시**한다(틀린 규칙이 동작하는 규칙과 똑같이 보인다). 파일에 그대로 적었다.
- Next: Phase 4(billable)만 남았다.

## 2026-08-08 — Cosign은 게이트가 아니었다 → 서명 경로·소비자·CI 키리스 (gate 1636→1651)

- 아침까지 공급망 보증은 **0**이었다: `cosign sign` 레포에 0건 · CI 자체가 없음 ·
  검증기의 유일한 호출자가 **자기 테스트** · 차트가 레지스트리 없는 맨 태그라 **서명이 놓일
  주소조차 없었다**. 즉 어드미션은 승인 사항이 아니라 **작업 선행**이 막고 있었다.
- 네 증분으로 닫았다: ①`make sign-image`(빌드→**다이제스트로** push→서명→**레포 자신의
  게이트로 검증**) ②배포 직전 **소비자**(`image_trust` — exit 2 "검사 못 함"도 거부) ③CI
  (`gate.yml`) ④**키리스**(`sign-image.yml` — Fulcio 단명 인증서라 **보관할 키가 없다** =
  custody의 답). 라이브 VERIFIED, 미서명은 `NOT SIGNED`.
- CI가 첫날 **세 건**을 잡았고 셋 다 진짜 결함이었다: 내가 게이트를 임의로 넓힌 lint ·
  **선언되지 않은 OTel exporter**(새 클론은 아무도 통과 못 했다) · **`>=3.11`은 아무도 확인한
  적 없는 주장**. → Risk 12②.
- 내 가드가 두 번 틀렸다: 주석을 호출로 셈 · `git grep`이 **미추적 파일을 못 봄**(가드가
  말해야 할 순간에 눈이 멀어 있었다).
- 과대 해석 금지: Rekor는 **영구 공개·철회 불가** · 로컬 `make sign-image`는 여전히 dev 키 ·
  배포 게이트는 **옵트인**이고 온프렘 진입점 하나 · **어드미션 미도입**.
- 상세 → `docs/archive/progress-2026-08.md` · 증거 `docs/evidence/{ci-keyless-signing,
  image-signature-deploy-gate}.log`.
