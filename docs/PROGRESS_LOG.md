# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-08

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-08 — 커밋을 경로에 한정 + 막힌 근거 재측정 (gate 1668→1676)

- Status: attach UI를 재려다 **그 앞의 구멍**을 먼저 찾았고, 이어서 남은 막힌 항목의
  근거를 돌려 봤다. PR #6·#7 병합.
- Changed(**구멍**): `attach_addon.py`가 조작자에게 `git commit -am`을 시켰다. `-a`는
  **수정된 모든 추적 파일**을 담으므로, 다른 게 더러우면 계획이 이름 댄 적 없는 파일까지 든
  PR이 열린다 — **"한 파일만" 불변식을 세우려고 존재하는 도구가 자기 지시로 그걸 깨는 경로**를
  들고 있었다. `commit_attachment`로 **경로 한정 커밋**(`-- <path>`) + `--commit`.
  브랜치 선점검은 **파일을 쓰기 전에** 돈다(아니면 "거부했는데 편집은 남는다").
  push·API는 그대로 조작자 몫.
- Verified: 반증 — `-- <path>`→`-a`로 **3건 red**, 브랜치 가드 제거로 **2건 red**.
  테스트는 트리를 **일부러 더럽힌 채** 잰다(**깨끗한 트리에선 두 방식이 구별되지 않고, 그래서
  안 보였다**). 라이브(임시 클론, 3파일 더럽힘): 커밋에 담긴 파일 **1개**, push 0 —
  하필 그 더러운 둘이 **이 도구의 소스**였다. `make check` **1676**(CI 일치, 새 git 테스트
  8건 리눅스에서도 PASSED).
- Verified(내 가드가 또 틀렸다): 처음 쓴 브랜치 테스트는 **가드를 지워도 초록**이었다 —
  `switch -c`가 내는 **git 자신의** 메시지에도 `already exists`가 있어 match가 그걸 받았다.
  그리고 "같은 첨부 두 번"은 이 가드의 시나리오가 아니었다(**플래너가 한 층 먼저** 거부).
- Changed(**근거 재측정**): attach UI가 막힌 이유가 "Next+FastAPI 두 층"이 아니다 —
  **FastAPI 층이 아예 없다**(Next→OIDC→DynamoDB). 진짜 구속 조건은 쓰기 대상이 git 파일인데
  UI는 Vercel이라 파일시스템·git·python이 없다는 것 → 같은 줄의 "실제 PR 생성"은 별개 잔여가
  아니라 **이 항목의 구속 조건**이다. MCP 항목도 근거만 틀렸다(생성자 0이 아니라 `bridge.py:35`
  하나, 그걸 만드는 건 테스트뿐). **성립한 근거 3건**(cost_metrics·kind 스냅샷·Cosign/k3s)은
  그대로 뒀다 — **성립하는 것도 결과다.**
- Blockers: 남은 항목은 전부 **승인·비용 / 정책 결정 / 외부 조건 / 선행 인프라 / 보류 지시**.
- 품질 메모: **세는 함정 둘을 실제로 밟았다** — `src/stacks/cdk.out`은 untracked인데 파일
  grep은 무시된 디렉터리까지 훑고(첫 측정 10건이 전부 빌드 사본), **docstring 사용 예시가
  호출로 보인다**. 후자는 **D39가 이미 밟은 함정**이라 이번엔 결론이 아니라 **세는 방법**을
  계획에 적었다.
- Next: Phase 4(billable, 별 승인)와 attach UI(플래너를 어디서 돌릴지) 둘 다 승인 사안.

## 2026-08-08 — 게이트가 검사하지 않는 것과 통과하는 것이 같은 색이었다

- Status: 미커밋 `/tidy-docs` 증분을 PR로 랜딩하다가(**PR #2**) CI 로그에서 문서와
  어긋나는 숫자를 봤다 — 문서 baseline `1668 passed, 1 skipped`인데 CI는 **1666/3**.
- Changed(원인): 수집 총계는 1669로 같고 **2개가 pass→skip**이었다. 하필
  `test_terraform_module`·`test_onprem_addons_module`의 `test_terraform_validate_passes`
  = **이 레포가 배포하는 IaC를 검증하는 둘**. `skipif` 조건이 **`terraform 미설치 OR
  모듈 미초기화`**인데 러너가 **두 절을 다** 만족했다(바이너리 없음 + `.terraform/`는
  gitignore라 새 체크아웃은 초기화된 적 없음 → **설치만 해도 여전히 skip**).
  즉 **D43이 병합 조건으로 삼은 게이트가 자기가 대체한 기계보다 적게 검사했다.**
- Changed(수정, **PR #3**): `gate.yml`에 `setup-terraform` **1.15.8 핀**
  (python 3.13 핀과 같은 이유=로컬에서 검증된 버전) + `terraform_wrapper: false`
  (테스트가 subprocess로 파싱) + `init -backend=false` **두 모듈만**
  (`infra/onprem/terraform`을 주장하는 테스트는 없다). 버전은 **커밋된 lock 파일**이
  고정하므로 자격증명 없이 결정적이다.
- Verified(반증 먼저 선언): *"init을 지우면 1666/3으로 돌아간다"* → 수정 후 CI가
  **1668/1**, 두 테스트 **PASSED**, 남은 skip 1건은 의도된 인-테스트 skip.
  run `31250113860`(전)↔`31250493800`(후). 증거
  `docs/evidence/ci-terraform-validate-skipped.log`. PR #2·#3 병합 완료.
- Changed(정리 중): 아카이브가 **자기 자신**을 "이전 이력"으로 가리키던 순환 포인터 1건 정정.
- Blockers: 없음. 남은 건 Phase 4(billable, 별 승인).
- 품질 메모: **skip은 실패가 아니라서, 검사하지 않는 게이트와 통과한 게이트가 같은
  색이다.** Risk 12②와 같은 계열이되 방향이 반대다 — 12②는 "로컬만 통과"였는데 이건
  **로컬이 통과시키고 CI가 안 도는** 쪽. 그래서 게이트 숫자에는 날짜(12①)뿐 아니라
  **어느 기계에서 쟀는지**도 붙어야 한다.
- Next: Phase 4(billable, 별 승인)만 남았다.

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

