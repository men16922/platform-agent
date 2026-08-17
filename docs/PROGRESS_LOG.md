# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-17 — 검증을 세운 그 커밋이 같은 결함을 한 문 옆에 남겼다 (gate 2251)

- Status: 앞 증분(조건 검증)에 **ultrareview**를 돌렸다. 결함 하나(normal)와 죽은
  참조 하나(nit)가 나왔고 **둘 다 성립했다**. 재현해서 확인하고 고쳤다.
- Verified(**리뷰가 맞았다**): `steps: null`은 `_step_problems`가 **0 problems로 통과**
  시키는데, GCP/Azure walk가 `runbook.get("steps", [])`로 읽는다 — **기본값은 키가
  없을 때만** 쓰이므로 저장된 `None`이 그대로 나오고 `for step in None`이 **TypeError**.
  ⚠️**내가 "막겠다"고 주석에 적어 둔 바로 그 500을, 그 주석을 쓴 커밋이 만들었다.**
- Verified(**리뷰보다 넓었다 — 형제를 다시 셌다**): `steps`를 읽는 자리는 넷이고
  **AWS만 `or []`로 None-safe**였다 = **읽는 쪽의 provider 간 비대칭**(이 레포가 정한
  "진짜 결함" 기준). 리뷰가 지적한 둘 외에 **`CapabilityRunbook.from_dict`도 같이
  터진다**(실측). 넷째(`executor.py`)는 생산자가 `default_factory=list`라 도달 불가지만
  **홀수를 남기지 않으려고** 같이 고쳤다.
- Changed: 넷 다 `get("steps") or []` · `schema.py` 계약 도크스트링에 **null 허용**을
  명시(에러 메시지는 "list or null"인데 도크스트링은 `list[dict]`이라 **두 출처가
  달랐다**) · nit: `CONDITION_KEYS` 주석이 **없는 파일**을 가리키고 있었다(드리프트
  가드는 `test_store_runbook_validation.py` 안에 있다) → 실제 이름으로 고쳤다.
- Changed(가드 +4, `test_steps_reads_are_none_safe.py` 신규): 행동 셋(GCP·Azure 라이브
  경로 + `from_dict`) + **구조 하나** — `src` 추적 파일을 AST로 훑어 `get("steps", …)`
  형태를 금지한다. ⚠️**`glob`로 짰다가 터졌다**: `src/stacks/node_modules/`의 CDK 템플릿
  6개가 `%name.PascalCased%` 때문에 파싱 불가다 — 조용히 건너뛰면 진짜 reader를 놓치니
  **`git ls-files`로 스캔 면을 좁혔다**(레포가 이미 쓰는 방식).
- Verified(**변이 5종, 전부 red**): 네 고침을 하나씩 되돌리면 red(R1~R3는 2건씩,
  R4는 구조 가드만 — 그 경로에 행동 테스트가 없는 게 정직하다) · ⚠️**공허 통과 방지로
  위반을 일부러 심었더니**(R5) red = 스캔이 정말 파일을 열어 본다.
  `make check` **2251 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: PR #42는 **병합 권한이 막혀** 열려 있다.
- Next: 08-19 이후 AMP 실제 청구액 대조.

## 2026-08-17 — 계약을 읽는 쪽만 고쳤더니, 쓰는 쪽이 아무것도 안 물었다 (gate 2247)

- Status: 직전 증분이 남긴 기준(**"조건은 계약이다"**)으로 **쓰는 쪽**을 물었다.
  `validate_runbook`은 최상위 필드를 전부 검증하는데 **`steps` 안은 아예 안 본다** —
  즉 M28이 "변조될 수 있는 쪽"(운영자 스토어=티어 1)을 검증하게 만든 건 껍데기였고,
  조건이 사는 곳은 무검증으로 walk에 넘어갔다.
- Verified(**측정**): 오타 조건 키 `previous_step_fail`은 **검증 0 problems + 평가 True**
  = 에스컬레이션 스텝(`rollback_release`)이 **모든 인시던트에서 실행**된다. 08-16에 고친
  그 결함을 **반대쪽 문**으로 다시 만든다(그때는 조건을 안 읽어서, 이번엔 **아무 뜻도 없는
  조건을 읽어서**). 비-dict 조건은 walk의 try **밖에서** TypeError → 티어 1 주석이
  *"막겠다"*고 적어 둔 바로 그 500. `severity_in: "P12"`는 **부분문자열 매칭**이 되어
  P1 인시던트가 통과한다.
- Verified(⚠️**엄격한 스텝 검증기는 이미 있었다 — 테스트만 부른다**):
  `capability_schema.validate_capability_runbook`은 `src/`에서 **호출처 0**. 검증기가 둘이고
  **실제 경로가 쓰는 건 느슨한 쪽**이었다.
- Changed: 조건 절을 **공유 계약 모듈**(`schema.py::_step_problems`)에 한 벌 넣었다 —
  세 provider가 다 읽는 곳이다. 키 집합 `CONDITION_KEYS`는 **읽는 쪽 옆**에 두고
  validator가 임포트한다(복제 금지). 거절은 M28의 기존 선택대로 **런북 단위**(휴리스틱 폴백).
- Changed(가드 +23): `MALFORMED`를 넓히니 **세 provider 전부**가 이미 있는 형제 기계로
  자동 커버된다 · **잘 형성된 조건 4형식은 여전히 따라가야 한다**(과잉 엄격이 티어 1을
  닫는 방향 — `require_alarm_name` 함정의 한 층 아래) · `CONDITION_KEYS`와 평가기를
  **AST로 대조**해 드리프트를 막는다.
- Verified(**변이 7종, 전부 red**): 절마다 하나씩 · 과잉 엄격(조건 전면 금지) **12건 죽음** ·
  드리프트(평가기에 넷째 형식) **5건 죽음**. ⚠️**`steps` 타입 절은 처음엔 생존했다** —
  픽스처를 `"restart"`로 잡았는데 **문자열은 순회가 되어** 절이 없어도 거절됐다(Risk 12⑤).
  **정수 5**로 바꾸니 절 없이는 **검증기가 TypeError로 터진다**("never raises" 위반) → red.
  `make check` **2247 passed, 2 skipped**(로컬 macOS·py3.13), 건드린 3파일 ruff 깨끗.
- Blockers: 없음. ⚠️PR #42는 **병합 권한이 막혀** 열려 있다.
- Next: 08-19 이후 AMP 실제 청구액 대조.

## 2026-08-17 — 계약이 세 형식인데 walk는 둘만 물었다 (gate 2224)

- Status: 열린 항목 **"런북 walk ②(`severity` 축)"**를 시험했다. **닫혔다 — 두 겹으로.**
  ①`severity` 축 자체는 **M33이 08-16에 닫았다**(가드가 GCP·Azure·AWS 셋 다 있고 양방향).
  ②e2e walk가 `severity="P2"`로 고정인 건 **결함이 아니라 범위**다: 카탈로그 9런북 16스텝을
  세어 보니 **조건 키는 `previous_step_failed` 하나뿐**(6스텝) — 08-12의 *"없는 문제에 대한
  가드는 하중을 못 받는다"*는 **아직 참**이다.
- Verified(**닫으러 갔다가 옆에서 나왔다**): `evaluate_condition`이 문서화한 형식은 **셋**
  (`previous_step_failed`·`severity_in`·`provider`)인데 walk 자리에서 물어진 건 **둘**이었다.
  `provider`는 **순수함수 단위 테스트**(직접 만든 컨텍스트)에만 있었다 — Risk 12④ⓒ.
  ⚠️**`test_step_condition_is_read.py`의 도크스트링이 세 형식을 정확히 열거하면서 둘만 물었다**
  — M20과 같은 모양(**산문이 참이어도 물은 것이 범위다**).
- Verified(**변이 8종, 전부 red · 기준선 먼저**): 대조군으로 세 컨텍스트 dict에서
  `"severity"`를 지우면 red(하네스가 맞는 dict를 겨냥했다는 증거) · **`"provider"`를 지우면
  세 walk 전부 GREEN 생존**(=가드 없음, 2218 그대로) → 가드 추가 후 **지우기 셋·`"aws"`로
  굳히기 셋 = 여섯 전부 red**. `-x` 없이 다시 재니 **정확히 1건**이 죽고 이름은
  `test_the_provider_form_is_honoured[own-provider-runs-gcp]` — **예측대로 하중은 양성 방향
  하나가 진다**(음성 방향은 깨진 구현과 답이 같아 혼자서는 살아남는다, Risk 12⑤).
  ⚠️변이·실행·복구를 한 스크립트에 두고 **복구는 git이 아니라 디스크 백업**으로 했다.
- Changed(가드 +6, `src/` **무변경**): `test_step_condition_is_read.py`에 provider 형식을
  GCP·Azure × 양방향으로(+4) · `test_executor_capability_steps.py`에 **gcp 인시던트가
  `provider: gcp` 스텝을 만족하는지**(+2 — AWS walk는 `normalized_incident`가 없으면
  `"aws"`로 폴백하므로 **인시던트 자신의 provider를 읽는지**를 물어야 하중을 받는다).
- Verified: `make check` **2224 passed, 2 skipped**(로컬 macOS·py3.13) · 두 파일 ruff 깨끗.
  ⚠️**게이트 숫자 가드가 먼저 red를 냈다** — `test_gate_number_claims`가 진입점 셋의 숫자
  일치까지 묻는다. 셋을 같은 커밋에서 고쳤다(**이 가드가 제 일을 했다**).
- Blockers: 없음.
- Next: 08-19 이후 AMP 실제 청구액 대조(4a를 닫는 유일한 남은 측정).

## 2026-08-17 — 4a가 라이브가 됐다: AMP가 계획서의 네 숫자를 그대로 돌려준다 (gate 2218)

- Status: 승인 셋(메트릭 4종·60초·리전)을 받아 4a에 착수. **DoD 네 단계 중 ③(remote_write
  성공)을 넘었다.** ①②는 계획서가 *"무엇을 렌더할지는 일부러 발명하지 않았다 — Phase 4
  결정"*이라 미룬 설계 사안이라 손대지 않았고, ④는 `from_managed`로 이미 서 있다.
- Changed: 워크스페이스 `ws-929b8da9…`(ap-northeast-2) · IAM 사용자 `amp-remote-write-4a`
  (정책 전부 = `aps:RemoteWrite` **하나**를 그 워크스페이스 **하나**에) · 키는 k8s Secret으로만
  존재(**git·로컬 파일 어디에도 안 씀**) · values에 remoteWrite+허용목록 · **간격은 전역이
  아니라 `kube-state-metrics` ServiceMonitor만 60초**(308 중 287이 거기서 온다) · 가드 2종.
- Verified: `make check` **2218 passed, 2 skipped**(로컬 macOS·py3.13, CI 일치) · 적용 전
  `helm template`로 두 키가 **실제로 읽히는지** 확인(Risk 8) + `helm get values`로 파일 밖
  값 없음 확인 · 파이프 `samples_total 319 / failed 0 / dropped 69,076`(99.5% 필터) ·
  **AMP 직접 조회가 §2의 22·50·220·16 = 308을 그대로 반환** · 변이 4종 모두 red.
- Blockers: ⛔**실제 청구액 미측정** — CE 2일 지연이라 **08-19 이후** 크레딧 제외 필터로
  대조해야 4a가 닫힌다. 그전까지 $1.42는 **산수지 측정이 아니다**. ⛔4a ①②는 설계 결정 대기.
- Next: PR #41 병합 → 08-19 청구액 대조 → 관리형 observability를 무엇으로 렌더할지 결정.
