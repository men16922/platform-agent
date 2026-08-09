# PROGRESS_LOG Archive — August 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 8월 이력입니다. 최신이 위.

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


## 2026-08-08 — Cosign은 게이트가 아니었다 → 서명 경로·소비자·CI 키리스까지 (gate 1636→1651)

- Status: 마지막 열린 승인(Cosign 어드미션)을 kind에서 세워 보려다, **기록된 이유가 구속
  조건이 아님**을 또 발견했다. **네 번째 같은 계열.**
- Verified(조사): 기록은 "현재는 CI/사람용 게이트까지. 어드미션엔 policy controller라는 새
  의존성이 필요"였다. 둘째 문장은 참이고 **첫째 문장은 아예 사실이 아니었다** — ①`cosign
  sign`이 레포에 **0건**(워크플로·Makefile·스크립트 어디에도 없다) ②`.github/workflows/`가
  **없다** → "CI 게이트"는 **돌 수 없는 단계**였다 ③`verify_image_signature.py`의 유일한
  호출자는 **자기 테스트**다(나머지 두 언급은 docstring과 values.yaml 주석) — **D39와 같은
  모양** ④차트가 `platform-agent:0.1.0`을 **레지스트리 호스트 없는 맨 태그**로 배포하고
  `digest: ""`다. 서명은 레지스트리의 **다이제스트 옆**에 사는 아티팩트이므로(검증기 자신의
  docstring이 그렇게 적어 뒀다) **놓일 주소조차 없다**.
- Verified(승인의 전제가 뒤집힌다): policy controller를 지금 넣으면 서명을 **강제**하는 게
  아니라 **모든 워크로드를 거부**한다 — 찾을 서명이 없으므로. 그리고 그 실패는 Risk 8의
  모양으로 나타난다(**Argo는 Synced인데 파드 0개**). 즉 승인 사항이 아니라 **작업 선행**이다:
  ①레지스트리에 다이제스트로 push → ②`cosign sign` → ③차트가 다이제스트 핀 → ④그때 어드미션.
- Changed: 거짓 주장 3곳(STATUS Risk 6 · NEXT_PLAN · AGENT_BRIEF)을 측정된 사실로 교체 ·
  가드 `tests/test_signature_gate_claims.py` 4종 — 문서는 **없는 CI 게이트를 주장할 수 없고**,
  검증기에 호출자가 생기면 **일부러 red**(문구를 승격하라는 신호), 어드미션 설정이 서명
  생산자보다 **먼저 들어올 수 없고**, `digest`가 핀되면 red(그때 서명이 가능해진다).
- Verified: `make check` **1640**(+4). 반증: STATUS에 "CI/사람용 게이트" 문구를 되살리자
  정확히 그 가드만 red.
- 품질 메모: **가드를 쓰다가 내가 오탐을 냈다** — 첫 실행이 values.yaml의 **주석 한 줄**을
  프로덕션 호출자로 셌다. 산문을 호출로 세는 건 이 파일이 다루는 결함의 **거울상**이라,
  탐지기도 측정해서 주석을 제외했다(푸시-신원 때 똑같은 실수를 했고 그때도 증거에 남겼다).
  그리고 이번 건의 본질: **검증 도구가 있는 것과 게이트가 도는 것은 다르다.** 도구는
  잘 만들어져 있었다 — "could not check"를 "fine"으로 강등하지 않는 것까지. 다만 **아무도
  부르지 않았다.**
- Changed(같은 날 후속, gate 1640→1641): **서명 경로를 세웠다**. `make sign-image` /
  `scripts/build_and_sign_image.sh` — ①`infra/onprem/Dockerfile` 빌드 ②로컬 레지스트리
  (`localhost:5001`)에 push하고 **push 출력에서 다이제스트를 읽는다**(로컬 id는 레지스트리가
  들고 있는 매니페스트 다이제스트와 다를 수 있고, 틀린 걸 서명하면 **아무 데서도 검증되지 않는
  서명**이 나온다) ③**다이제스트에** `cosign sign`(태그는 움직이는 포인터다) ④검증은
  `cosign verify`를 다시 부르지 않고 **`scripts/verify_image_signature.py`로** 한다 — 그 스크립트가
  이미 "could not check"를 "fine"으로 강등하지 않으므로, 여기서 또 검사하면 **검증의 의미가 두
  군데서 갈릴** 수 있다.
- Verified(라이브): 빌드→push→서명→**VERIFIED**까지 통과
  (`sha256:510619af...`). 반증: **같은 빌드의 image manifest 다이제스트**(서명한 건 manifest
  list다)로 검증하면 `NOT SIGNED` exit 1. 레지스트리에 `tampered`·`unsigned` 태그와 cosign
  서명 아티팩트가 **이미 남아 있었다** — 라이브 검증은 과거에 **수동으로 한 번** 있었고,
  레포에 그걸 재현할 경로가 없었던 것이다.
- Changed(가드 반전): `test_the_verifier_has_no_production_caller`는 **쓴 날 뒤집혔다**.
  참인 명제가 바뀌었으니("호출자가 없다" → "있다") 지키는 명제도 바꿨다 — 이제 **서명 생산자와
  검증 호출자가 사라지면 red**다.
- Blockers(남은 것, 과대 해석 금지): 키는 **로컬 dev 전용**(빈 암호) · **CI 없음**(사람이 `make`를
  쳐야 돈다) · 차트 `digest`는 **비워 둔다**(로컬 다이제스트 커밋 = 아무도 못 가진 이미지에 대한
  주장) · **어드미션 집행은 여전히 미도입**.
- 품질 메모(두 번째): **내 가드에 구멍이 있었다.** `git grep`이 기본적으로 **추적된 파일만**
  본다 — 그래서 새로 쓴 `build_and_sign_image.sh`가 검증기를 부르는데도 가드가 **초록**이었다.
  가드가 말해야 할 바로 그 순간에 눈이 멀어 있던 것이다. `--untracked`로 고쳤다. 오늘만
  **가드 자신이 두 번**(주석을 호출로 셈 · 미추적 파일을 못 봄) 측정 대상이 됐다.
- Changed(세 번째, gate 1641→1651): **소비자를 붙였다.** 서명 경로만 만든 시점에서 나는
  **이 레포가 온종일 사냥한 결함을 새로 만든 상태**였다 — **소비자 없는 생산자**. 서명이
  찍히는데 **쓰는 시점에 아무도 읽지 않으면** 통제가 아니라 빌드 아티팩트다.
  `src/agents/platform/image_trust.py` + `deploy_to_cluster` 배선:
  ①판정은 **검증기의 종료 코드**가 그대로다(0/1/2) — 여기서 다시 판정하면 "검증됨"의 의미가
  두 군데서 갈린다 ②**exit 2("검사 못 함")도 거부**한다. cosign 부재·레지스트리 불통은
  이미지가 괜찮다는 증거가 아니고, fail-open하면 하류 전체가 검사됐다고 믿는다 ③다만 메시지는
  구분한다 — 운영자가 **고장 난 검사기를 위조로 오진하면 안 된다**.
- Verified(라이브, 모킹 없음): 실 레지스트리·실 cosign·실 키로 서명 다이제스트는 통과,
  미서명은 거부. 미서명 표본은 꾸며 낸 값이 아니라 **같은 빌드의 image manifest**다(서명한 건
  manifest **list**). 실 배포 진입점에서 `cluster.deploy called=False` — **거부가 클러스터 호출
  앞에서** 일어난다(뒤에 도는 검사는 게이트가 아니다). `make check` **1651**(+12).
  증거 `docs/evidence/image-signature-deploy-gate.log`.
- Blockers(과대 해석 금지): **옵트인**(`PLATFORM_REQUIRE_SIGNED_IMAGES` 미설정=검사 0) ·
  **온프렘 진입점 하나**만 덮는다(클라우드 3종·ArgoCD가 직접 당기는 이미지는 안 지난다) ·
  **어드미션이 아니다**(API 서버는 여전히 받는다) · 키는 로컬 dev 전용 · CI 없음.
- Changed(네 번째, 같은 날): **CI + 키리스 서명**. 두 결정(CI · 키 custody)은 **사실 하나**였다 —
  **키리스가 키를 없애서 custody를 푼다**(Fulcio 단명 인증서, 보관·회전할 것이 없다).
  `gate.yml`(게이트를 기계가 돌린다) · `sign-image.yml`(빌드→GHCR→키리스 서명→**레포 자신의
  게이트로 검증**, 신원을 이 워크플로의 정확한 ref에 고정 — 아무 신원이나 받으면 Fulcio에 닿을
  수 있는 누구의 서명이든 통과한다). 라이브 첫 실행 **VERIFIED**
  `ghcr.io/men16922/platform-agent@sha256:112dd9b5...`.
- Verified(CI가 세 번 red였고 **세 번 다 진짜 결함**): ①lint 399건 — **내가 게이트를 임의로
  넓혔다**(이 레포의 게이트는 `make check`이고 `make lint`는 포함된 적 없으며 로컬에서도 20건
  실패 중이다. CI는 아무도 합의하지 않은 기준을 들여오기에 나쁜 자리다) ②tracing 17건 —
  **게이트가 선언되지 않은 패키지 위에서 통과하고 있었다**: strands가 OTel api+sdk를 끌고 와
  skipif가 건너뛰지 않는데 **exporter는 미선언**이라 ImportError가 의도적 `except`에 삼켜지고
  트레이싱이 **조용히 no-op**이 된다 → 새 클론에서는 아무도 통과 못 한다(→ `observability`
  extra) ③2건 — **`requires-python = ">=3.11"`은 아무도 확인한 적 없는 주장**(3.11 red /
  3.13 green). floor를 **조용히 올리지 않고** CI를 검증된 버전에 고정했다.
  증거 `docs/evidence/ci-keyless-signing.log` → Risk 13.
- Blockers: **어드미션 하나만 남았다**. Rekor는 **영구 공개·철회 불가**이고, 로컬
  `make sign-image`는 여전히 빈 암호 dev 키다(키리스는 CI 경로만 덮는다).
- 품질 메모: **CI가 잡은 세 건은 로컬에서 원리상 드러나지 않는다.** 특히 ②는 "게이트는
  상한다"(Risk 12)의 공간축 버전이다 — 통과가 코드가 아니라 **말해지지 않은 환경**에 달려
  있었다. 그리고 ①은 내 실수였다: 게이트를 집행하러 가서 **게이트를 넓혔다**.
- Next: **④어드미션만 승인 사항**(kind 선행 권고). Phase 4/5는 그대로.

## 2026-08-08 — 승인 3건을 쟀다: 하나는 통과, 하나는 질문이 틀렸고, 하나는 보류

- Status: 사용자 지시("추천안에 따라 승인할테니 해")로 승인 3건 처리. 먼저 푸시(54커밋,
  `655369f..3908159`) — 그때까지 origin은 **6일 뒤처져** 있었다.
- Verified(①실 DynamoDB 왕복 = **통과**): 생산자 `_record_incident`가 실 `incident-history`에
  행을 남기고(18속성), 여섯 속성이 **타입까지 보존**된다. 핵심은 `confidence`가 `Decimal`로
  돌아온 것 — DynamoDB N 타입이라 대시보드의 `typeof item.confidence === "number"`가 참이 된다.
  **문자열이었다면 파이썬 쪽은 통과하면서 화면엔 영원히 "n/a"**가 떴을 것이다. 그리고 애초에
  float를 넣었으면 boto3 예외가 `except`에 잡혀 **행 전체가 사라졌을** 것이다 — 목은 float를
  군말 없이 받으므로 이건 모킹으로 **원리상** 못 잡는다. 생산 리더의 `started_at`도
  `triggered_at`에서 온다. 프로브는 자기 행을 지운다. `scripts/probe_incident_roundtrip.py`,
  증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`. **남은 한 칸**: 대시보드 TS
  리더로는 안 읽었다(속성명·예약어 별칭 대조까지).
- Verified(②GCP/Azure 보관 = **질문이 틀렸다**): "켜는 건 실 데이터 삭제"의 **뒷절반이 한 번도
  측정된 적이 없었다**. GCP는 platform-agent 프로젝트(`project-ec7809f7`)에 **Firestore API가
  켜진 적조차 없고**, Azure엔 `platform-agent` DB가 없다 → **지울 데이터 0**. 없는 컨테이너에
  `DefaultTimeToLive`를 걸 수 없으므로 **구속 조건이 기록과 반대**다: 보관을 켜려면 **먼저
  프로비저닝**해야 하고 그건 billable → Phase 4. ⚠️처음에 **엉뚱한 프로젝트**
  (`claude-study-501117`)를 보고 결론낼 뻔했고 메모리의 결제 매핑이 잡아 줬다 — 그래서 나머지
  3개 프로젝트도 스윕했다. 증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log`.
- Blockers(③Cosign 어드미션 = **보류 권고, 미실행**): policy controller라는 **새 클러스터
  의존성**이고, 잘못 서면 Risk 8의 모양으로 실패한다(**Argo는 Synced인데 파드 0개**).
  승인 3건 중 유일하게 되돌리기 비용이 크다 → kind 선행 + Phase 4와 묶기.
- 품질 메모: **승인 항목도 측정 대상이다.** 셋 중 하나는 통과, 하나는 **질문 자체가 사실이
  아니었고**(9일간 "파괴적 승인"으로 대기), 하나만 진짜 승인이 필요했다. D40·D41과 같은
  계열이다 — 그럴듯한 이유가 문서를 건너 복사되는 동안 **아무도 쿼리를 돌리지 않았다**.
- Next: Phase 4/5. 열린 승인은 Cosign 하나.

## 2026-08-08 — 서명키는 회전할 수 없었다: 같은 키를 요구하던 문장이 곧 제약이었다 (gate 1618→1636)

- Status: 우선순위 2 = 서명키 custody·rotation. **rotation을 닫았고 custody는 안 건드렸다**(아래).
- Verified(조사): 결함은 암호가 아니라 **배포 위상**이었다. 서명자(`attest_decision`, 승인
  경로)와 검증자(`TokenBroker`, 실행기)가 **다른 프로세스**인데 같은
  `PLATFORM_APPROVAL_SIGNING_KEY` 하나를 읽는다 → 교체가 **원자적일 수 없다**. 먼저 롤한 쪽이
  만든 레코드는 상대가 거부하고, 그 거부가 하필 **`failed attestation`** — 즉 **위조로 읽힌다**.
  결과: 회전은 장애 아니면 오경보라서 **실제로는 한 번도 회전하지 않는다**. Makefile의
  "the key must be the same for whoever signs and whoever verifies"는 **설명이 아니라 제약**이었다.
- Changed: `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`(콤마 구분) — **검증 전용, 절대 서명 안 함**.
  `_accepted_keys()`(active + retiring) · `_verifying_key_index()`(어느 키로 통과했는지) ·
  `verify()`는 bool 계약 유지 · **설정이 회전을 흉내 내지 못하게**(active 키를 retiring에
  나열 = 두 반쪽 다 no-op인데 둘 다 한 것처럼 보인다 → 거부 · 중복 → 거부) ·
  `_signed_by_a_pre_ttl_version`도 retiring 키를 본다(롤아웃 스큐와 회전이 겹치면 **또 위조로
  오진**된다) · Makefile에 3단 절차 기록.
- Verified: **겹침 창을 유한하게 만드는 건 D42의 TTL이다** — 새 암호가 아니라. 옛 키는 그 키로
  서명된 레코드가 **만료될 때까지만** 살아 있으면 된다. 가드로 고정: 만료된 레코드는 retiring
  키로도 거부되고, 서명이 `issued_at`을 덮으므로 **백데이트로 TTL을 빠져나갈 수 없다**.
- Verified: `make check` **1636**(+18). 반증 4종 개별 red — retiring 미수용(6 red) · 로그 제거
  (1 red) · 설정 검증 제거(2 red) · **retiring 레코드에 TTL 미적용**(1 red, 겹침이 무한해지는
  바로 그 오구현). ruff clean.
- Blockers: **custody는 안 닫았다 — 그리고 그건 거짓 주장이 아니었다.** `Makefile:256`이
  "Local development only… NOT a secret-management story"라고 정확히 라벨해 뒀다. 닫으려면
  시크릿 매니저를 고르는 **인프라·정책 결정**(+과금)이라 발명하지 않았다.
- 품질 메모: **집행할 수 없는 절차는 관측 가능하게 만든다.** 3단계(옛 키 제거)는 코드가 강제할
  수 없다 — 나열된 키는 나열된 동안 유효하다. 대신 옛 키로 통과한 레코드마다 로그를 남겨
  "회전이 끝났나?"를 **믿음이 아니라 측정**으로 답하게 했다. **침묵이 그 측정이다.**
  그리고 이번 것도 계열이 같다: 문서가 **제약을 설명으로 적어 두면** 아무도 그게 막고 있는
  줄 모른다.
- Next: 승인 3건 → Phase 4/5. custody는 인프라 결정 대기.

## 2026-08-08 — 달력이 움직이자 red가 됐다: 하드코딩 픽스처가 창 밖으로 밀렸다 (gate 1617→1618)

- Status: `/sync` 직후 Stop 훅의 `make check`가 **5 failed**. 미커밋 소스
  (`collector.py`·`scope.py`·`tenancy.py`)가 범인처럼 보였으나 **무관**이었다.
- Verified(진단): 실패한 `tests/test_incident_time_to_resolve.py`는 **수정된 적이 없다**
  (gate 1520에 커밋된 그대로). `_row()`가 `created_at="2026-07-29T00:30:00Z"`를 하드코딩하는데
  생산자 `_fetch_incidents_from_dynamo(days=7)`는 **살아 있는 시계**로 `_in_window`를 건다.
  실측: 그 행은 **9.96일** 되어 창 `[07-31, 08-07]` 밖 → `_fetch`가 `[]` → `IndexError` /
  MTTR `0.0`. 즉 **2026-08-05에 코드 한 줄 안 바뀌고 red가 됐다**. 문서의 1617은 거짓이
  아니라 **유효기간이 지난 것**이었다.
- Changed: 픽스처를 `now` 기준 상대 배치로 — **이미 green이던 형제**
  `test_report_windows.py`(`_row(age_days)`)가 쓰던 그 모양. 측정 대상은 **duration이지
  placement가 아니라서** 오프셋(45.0/20.0/30.0)은 그대로 정확하다 · `_BASE`는 import 시
  1회 고정(픽스처와 단언이 초 경계를 straddle하지 않게) · 가드 1건(창 밖으로 밀리면
  `IndexError` 대신 **이름으로** 먼저 실패 — 빈 리스트발 `IndexError`는 리더 버그처럼
  읽히는데 아니다).
- Verified: `make check` **1618**(+1). 창 필터를 타는 테스트는 이 **둘뿐**이고 둘 다 통과.
  나머지 26개 하드코딩 날짜 파일은 살아 있는 시계를 안 탄다 — **후보이지 결함이 아니다**.
- Changed(정리): 워킹트리에만 있던 gate 1607~1618분을 **커밋 5건**으로 분리
  (D42 · D41+D40 · 푸시 읽기 신원 · 이번 수정 · 체크포인트). 직전 커밋은 `ed36b30`(1605)였다.
- Blockers: 없음. **origin 대비 미푸시**는 남아 있다(푸시는 별도 승인).
- 품질 메모: **이 계열의 시간축 변종이다.** "없는 것은 테스트에서 영원히 초록"이 아니라
  **달력이 움직이기 전까지만 초록**이었다. 그리고 훅이 지목한 파일 목록(미커밋 소스)은
  **상관관계지 인과가 아니었다** — 실패 파일이 unmodified인지 먼저 물었으면 1분이었다.
  게이트 결과에는 **측정 시점이 붙어야 한다**: "1617 passed"는 날짜 없이는 주장이 아니다.
- Next: 우선순위 2 = **서명키 custody·rotation**(D42의 TTL 900초로 선행 해소).

## 2026-08-02 — 계획이 스테일이었다: 막힌 건 푸시 인증이 아니라 스포크의 읽기 (gate 1614→1617)

- Status: `2차 잔여` 첫 항목("agent→hub push 인증")을 잰 결과 **일주일째 스테일**이었고,
  그 자리에 **다른 구멍**이 있었다.
- Verified(라이브, 실 허브 라우트): 쓰기 쪽은 **이미 집행된다** — ①올바른 서명 200
  ②무서명 401 ③틀린 키 401 ④globex 키로 acme 자칭 401 ⑤acme 키에 globex 행 섞기
  → 401 `carries rows for ['globex/dev']`. 2026-07-26(gate 1219→1251)에 이미 끝나 있었다.
  ⚠️**첫 ⑤는 200이 나와 진짜 구멍처럼 보였다** — 내 페이로드가 행을 `addons` 키로 보냈는데
  `StatusReport`는 `statuses`를 읽어 **행이 파싱조차 안 된 빈 보고서**였다. 픽스처를 실제
  생산자 모양(`to_dict()`)으로 바꾸자 정상 거부. **잘못된 픽스처발 오탐은 이 레포가 쫓는
  결함의 거울상**이라 지우지 않고 증거에 남겼다.
- Verified(진짜 구멍): 읽기 쪽은 **자격증명이 경계가 아니다** — `_kubectl`이 맨 kubectl이고
  (`--kubeconfig`/`--context` 없음, D38이 배포에서 닫은 그 모양), 읽는 대상이 **공유 `argocd`
  네임스페이스**라 테넌트 구분이 **파이썬 라벨 필터**다. 게다가 `infra/helm`에 **스포크
  배포 매니페스트가 없다**(router·webhook·orphan-sweeper뿐) — 즉 "각 클러스터가 에이전트를
  돌린다"는 서술은 **의도된 배포지 존재하는 배포가 아니다**.
- Changed: 모듈 docstring의 과장("읽기 경로에서도 blast radius가 1 tenant/env")을 **측정된
  사실로 교체** · `warn_if_ambient_read()`(프로세스당 **한 번**, `--interval 60` 루프가 로그
  노이즈가 되지 않게) · `_kubectl`이 그걸 부르게 해서 **문구가 동작에서 떨어질 수 없게** ·
  가드 3종 · NEXT_PLAN의 스테일 항목 2개를 사실로 교체.
- Verified: `make check` **1617**(+3). 반증 3종 개별 red(경고 우회 · 문구 약화 · 래치 제거).
  증거 `docs/evidence/push-identity-ambient.log`.
- Blockers: 없음. **seam은 일부러 안 만들었다** — D38이 `make deploy-identity`(민팅 경로)와
  함께 나온 이유가 그것이고, 채울 수 없는 env var를 추가하면 **같은 결함에 새 이름**을 붙이는
  것이다. 스코프된 읽기 신원은 **인클러스터 배포가 선행**이라 인프라 결정.
- 품질 메모: **계획 문서도 측정 대상이다.** 닫힌 항목이 열린 채 남아 있으면 다음 사람은 이미
  된 일을 하거나, 더 나쁘게 **그 옆의 진짜 구멍을 못 본다**. 그리고 이번엔 **내가 오탐을
  냈다** — 필드명 하나 틀린 픽스처로. 측정은 도구가 아니라 습관이라 픽스처도 측정해야 한다.
- Next: 승인 3건 + Phase 4/5. 남은 2차 잔여는 스포크 읽기 신원(인프라 선행) · 서명키 rotation.

## 2026-08-02 — 결정 6 = D42: 승인은 1회용이 아니라 상하는 것 (gate 1611→1614)

- Status: 사용자 지시("우선순위 & 추천안에 따라 수행")대로 결정 6을 **추천안 C**로 실행.
- Changed: `AttestedApproval.issued_at`을 **서명 payload에 포함**(시각을 키 없이 앞당길 수
  없다) · 브로커가 TTL 초과·미래 스탬프·`issued_at=0`을 거부 ·
  `PLATFORM_APPROVAL_TTL_SECONDS`(기본 **900초**, `<=0`은 설정 오류로 거부 = **끄는 스위치
  없음**) · 생산자(`attest_decision`)와 소비자(`resolve_incident_scope`) **양쪽 배선**(저장만
  하면 M13을 하나 더 만드는 것) · 가드 6종.
- Verified(라이브, 프로덕션 진입점): ①갓 발행 승인 3회 재사용 → **3회 MINTED**(실행기가 실제로
  두 번 해석하는 패턴이라 이게 정상) ②TTL 초과 → `960s old, past the 900s TTL` ③시각만
  앞당김 → 서명 불일치 ④24시간 미래 스탬프 → 거부 ⑤레포 프로브 `probe_scope_reachability.py`
  → resolve MINTED, 게이트 **PERMITTED**. `make check` **1614**(+6). 반증 3종 개별 red(나이
  검사 제거=3 red · payload에서 `issued_at` 제거=2 red · 스큐 진단을 수락으로=1 red).
- Blockers: 없음. **행동 단위 1회용(옵션 B)**은 실행기 3종 상태 저장이 필요 → Phase 4와 함께.
- 품질 메모: **900초를 발명하지 않았다** — 서명은 인가가 성립하는 순간에 찍히고 실행기가 같은
  흐름에서 소비하므로 **사이에 사람 대기가 없고**, 들어가야 하는 건 기계 시간뿐이라는 경로의
  모양에서 나왔다. 그리고 **첫 구현에 도달 불가능한 분기를 만들 뻔했다**: "구버전 레코드"
  분기를 넣었는데 측정해 보니 `issued_at`이 서명에 들어가 그 레코드는 `verify()`에서 먼저
  죽는다 — 즉 그 주석이 설명하는 상황에 **영원히 닿지 못한다**. 이번 계열에서 배운 걸 내가
  바로 반복할 뻔했다. 거부는 유지하되 **이유를 스큐로 분류**하게 고쳤다(롤링 배포 중 "failed
  attestation"은 위조로 오진된다). **약속이 줄었고 대신 지켜진다** — TTL 안 재사용은
  가능하고, docstring·계획·테스트에 **그렇게 적었다**.
- Next: 승인 3건 + Phase 4/5. 열린 결정 없음.

## 2026-08-02 — Phase 5를 재다가 재사용 가드를 찾았다: 상태가 살아남지 못한다 (gate 1608→1611)

- Status: 다음 우선순위(Phase 4·5)를 집으려 실체를 재는 중 **Phase 5는 완전 그린필드**이고
  설계상 **(선택)**임을 확인, 대신 "선행이 안 끝났는데 이미 출하된" 항목(서명키 custody —
  결정 5-A의 선행)을 재다가 **옆에서 구멍이 나왔다**. **여섯 번째로 전제가 깨졌다.**
- Verified(조사): 서명키 자체는 **거짓 주장이 아니었다** — `Makefile:256`이 "Local development
  only… NOT a secret-management story"라고 정확히 라벨해 두었다. 깨진 건 그 옆
  `AttestedApproval.nonce`의 **"One-time-use marker; the broker rejects a replayed nonce"**다:
  ①`_spent`가 **인스턴스 속성**인데 유일한 프로덕션 호출자 `resolve_incident_scope`가 호출마다
  `TokenBroker.from_env()`를 **새로 만든다** → 프로덕션 경로로 같은 레코드 3회 제출에 **3회
  발급** ②`test_nonce_replay_is_refused`는 broker 픽스처 **하나**를 잡고 두 번 부른다 —
  **수호 테스트가 홀을 놓친 게 아니라 유일한 성립 조건을 제공**했다(이 계열 첫 사례)
  ③그리고 **지금 켜면 정당한 호출자가 깨진다**: `aws/executor.py`가 같은 인시던트로 스코프를
  **두 번** 해석하고(런북·액션 경로) SFN 재시도가 더 겹친다. 즉 "영속화하자"가 아니라
  **"1회의 단위가 무엇인가"** 문제다.
- Verified(영향): **테넌트 경계는 안 깨진다** — 서명이 tenant를 덮어 재사용해도 같은 스코프가
  다시 나올 뿐이다(가드에 단언으로 고정). 깨지는 건 **감사 주장**("이 승인은 정확히 한 번의
  행동을 인가했다")이고, 재사용된 행동은 **옛 `approval_id`로 귀속**된다.
- Changed(모호하지 않은 절반만): 주장 3곳을 사실로 교체(`nonce` 주석 · `_spent` · `mint`) ·
  기존 테스트 이름을 `..._within_one_broker_instance`로(이름 자체가 주장이었다) · 새 가드
  `tests/test_scope_replay_reachability.py`는 **프로덕션 함수로** 단언하고, 재사용이 실제로
  거부되기 시작하면 **일부러 red**가 된다.
- Verified: `make check` **1611**(+3). 반증: 브로커를 모듈 캐시로 바꾸자 두 가드가 정확히 red.
  ruff 변경 파일 clean. 조사 `docs/plans/2026-08-02-nonce-replay-scope.md`.
- Blockers: **결정 6**(소비 단위) — A=인시던트 1회 · **C=TTL로 대체(추천)** · B=행동 1회(영속
  저장, 실행기 3종 새 의존성 → Phase 4와 함께). TTL 길이·소비 단위는 **정책**이라 발명하지 않음.
- 품질 메모: **가드는 자기 상태가 살아남는 수명에서만 집행된다.** 그리고 이번엔 **테스트가 그
  수명을 만들어 줬다** — "수호 테스트 자신이 안티패턴일 수 있다"의 가장 나쁜 형태다. 고칠 때
  **집행을 켜는 쪽으로 먼저 가지 않은 이유**도 측정에서 나왔다: 켰으면 정상 실행이 깨졌다.
- Next: 결정 6 + 승인 3건. Phase 5는 그린필드·선택이라 뒤로.

## 2026-08-02 — 결정 3: 선택지가 둘이 아니라 셋이었다 (gate 1607→1608)

- Status: 마지막 사용자 게이트(결정 3 = Capsule `limitRanges` 이관 경로)를 조사 → 승인 →
  라이브 검증 → 실행. **다섯 번째로 전제가 깨졌다** — 이번엔 **선택지 개수**였다.
- Verified(조사): 네 문서가 두 갈래(`GlobalTenantResource`=D30 위반 / `TenantResource`=새
  SA+RBAC)만 놓고 "둘 다 비싸다"고 적었는데, **같은 증거 로그 26행이 세 번째 답을 이미 적어
  두었다**: *"`networkPolicies`는 우리에게 해당 없음 — 이 레포는 Tenant spec 대신 객체를 직접
  렌더한다."* 같은 릴리스에 폐기된 형제 필드다. `LimitRange`는 **네임스페이스 스코프**라 D30
  무관, **새 권한 표면도 없다** — `TenantResource`가 SA를 요구하는 건 **Capsule이 대신 쓰기
  때문**이고 직접 쓰면 대리인이 없다.
- Verified(라이브 kind, 3단): ①`spec.limitRanges` 제거 → **Capsule이 자기 LimitRange 4개를
  회수**(globex 것은 유지 = 중복 없음) ②없는 상태에서 limits 없는 파드 → `must specify
  limits.cpu for: c` **Forbidden** — 애드온 values 4종 중 limits를 두는 게 **하나도 없어**
  전 워크로드가 여기 의존하고, 그 거부는 **Argo가 Synced로 보이는**(Risk 8) 자리에서 난다
  ③직접 렌더 후 다시 통과하고, Capsule이 `managed-by` 라벨을 찍었음에도 **컨트롤러 재시작
  전체 리싱크를 견딘다**(8회 샘플 120초, 5/5 생존). 부수: apply stderr **0바이트** — 폐기
  경고 2→0.
- Changed: `spec.limitRanges` 제거 + `render_limit_ranges()` 추가(`render_tenancy`가 Capsule
  Tenant를 낼 때만 방출 — `limits.*` 쿼터가 있을 때가 정확히 그때다) · 가드 2종(하나는
  **파생**: 쿼터가 `limits.`를 선언하면 그 렌더의 **모든** 네임스페이스가 기본값을 가져야 한다,
  나중에 추가될 ns까지 잡힌다) · **스테일 픽스처 라벨링**(`CAPSULE_WARNINGS`는 이제 클러스터가
  만들지 않는 stderr다 — 조용히 갱신하지 않고 HISTORICAL로 명시).
- Verified: `make check` **1608**(+1). 반증 2건 개별 red. ruff 변경 파일 clean. 증거
  `docs/evidence/capsule-limitranges-direct.log`, 조사
  `docs/plans/2026-08-02-capsule-limitranges-path.md`, 결정 **D41**.
- Blockers: 없음. 라이브 변경은 로컬 kind에 국한(테넌트 2개 재적용 + 프로브 파드 정리 완료).
- 품질 메모: **질문이 주는 선택지를 세지 말 것.** D40은 "막는 게 하나"라던 게 넷이었고,
  이번엔 "선택지가 둘"이라던 게 셋이었다. 둘 다 **답이 이미 레포 안에** 있었다 — 이번 것은
  같은 파일 40행 위에. 그리고 **폐기됐다고 사문화된 건 아니다**: 이 필드는 쿼터를 admission
  요구로 바꾸는 축이었고, 없으면 조용히가 아니라 **Forbidden**으로 깨지는데 그 소리가 들리는
  곳이 하필 Argo가 Synced를 보여 주는 자리였다.
- Next: **사용자 게이트 전부 닫힘.** 남은 건 승인 3건 + Phase 4/5.

## 2026-08-01 — 결정 4: 승격 도구가 승격을 못 한다 (gate 1605→1607)

- Status: 브리프의 ⓪순위(결정 4 = k3s를 proven 기판에)를 조사 → 사용자 승인(옵션 C) → 실행.
  **네 번째로 전제가 깨졌다** — 이번엔 **막는 것이 하나가 아니었고**, 기록된 하나는 가장 먼저
  걸리지도 않았다.
- Verified(조사): 네 문서가 반복하던 "k3s-lab에 피어 테넌트가 없다"는 **참이지만 구속력이
  없었다**. 실제 프로브 실행 → `acme/prod has 1 namespace(s); the same-tenant leg needs two`
  로 **피어를 보기 전에** 멈춘다(애드온 1개 = 네임스페이스 1개). 임시 레지스트리로 ①②를
  제거해도 ③에서 멈춘다: `network_policies_apply_to(acme,'prod')=False` — 프로브가 proven
  집합을 전제하고 그 집합을 정하는 게 프로브다. **승격하려면 먼저 승격해야 한다**(kind가
  통과한 건 이미 안에 있어서고, 실제로 한 건 승격이 아니라 회귀 테스트). ④ 라이브 k8s-lab
  (20d): 네임스페이스 4개(전부 기본), netpol 0, Capsule·Flux CRD 없음, kube-system 밖 파드 0,
  `acme-prod-*` **한 번도 존재한 적 없음**. 비용도 반대로 적혀 있었다 — **이 클러스터를 보는
  컨트롤러가 없어 레지스트리 편집은 아무것도 프로비저닝하지 않는다**. 즉 오늘 넣으면 **보호
  대상이 0**이다.
- Changed(승인된 옵션 C): 집합은 `{"kind"}` 유지 · **닫는 이유를 사실로 교체**(tenancy.py
  주석 · STATUS Risk 5 · NEXT_PLAN 결정 4/잔여 · 증거 로그 FOLLOW-UP) · **D40** ·
  새 가드 `tests/test_substrate_promotion_reachable.py`(**멤버십 주장은 현재 레지스트리로
  반증 가능해야 한다** + 순환을 코드에 고정) · 조사 문서
  `docs/plans/2026-08-01-k3s-proven-substrate.md`.
- Verified: `make check` **1607**(+2). 반증 2건 개별 red — k3s를 넣으면 `'k3s' is claimed
  PROVEN, but no tenant/env on it can be run ... acme/prod: 1 namespace(s)`, globex를 다른
  클러스터로 옮기면 kind가 red. 반증 1은 **두 번째 가드까지** red(미증명 기판이 사라지면
  가드를 약화하지 말고 폐기하라는 신호). ruff: 변경 파일 clean.
- Blockers: 없음. **클러스터 변경 0건**(읽기만).
- 품질 메모: M13(**소비자 없는 필드**) → D38(**생산자 없는 메커니즘**) → D39(**사용처 없는
  예외**) → D40(**도달 불가능한 검증기**). 네 번째가 가장 은밀했다 — 프로브는 잘 쓰였고 4개
  주장이 전부 반증 가능한데 **자기가 판정해야 할 대상에는 절대 못 닿는다**. 넷 다 테스트는
  초록이었다. 그리고 **부정확한 근거가 네 파일에 복사돼 3일을 살았다** — D39가 "예외의 근거를
  코드로 확인하라"였다면 이건 **"게이트의 근거는 측정으로 확인하라"**다. 한 번만 돌려 봤으면
  첫 줄에서 드러났다.
- Next: 잔여는 **결정 1건(3: Capsule `limitRanges`)** + 승인 3건. 그 뒤 Phase 4/5.
