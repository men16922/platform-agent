# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-16 — 08-11부터 묶여 있던 항목: 기록된 차단 이유가 틀렸다 (gate 2102)

- Status: `slack_live_approval.py`는 *"고치면 조용히 no-op"*이라 08-11부터 안 고치고 있었고,
  기록은 *"올바른 이름은 **Slack 데모를 태워야 확정**된다"*였다. **이 레포는 오늘 이미 그런
  기록 하나가 틀린 걸 봤으니**(M19 ⓑ) 믿지 말고 시험했다.
- Verified(**①은 참, ②는 근사했다**): 임포트 경로
  `src.agents.operations.approval_bridge`는 **추적 트리에 없다** — 패키지가 `aws/` 아래로
  이사했고 옛 경로는 **untracked `cdk.out/`에만** 남아 있다(그래서 `cdk synth`를 돌린 머신에서만
  임포트가 됐다). ⚠️기록은 *"여섯 중 넷 부재"*였는데 실제로는 **5/6이 부재**(`_SFN`만 존재)이고
  **호출하는 셋은 전부 존재**한다.
- Verified(**"데모 선행"은 틀렸다**): 사라진 다섯은 서브모듈 분해로 옮겨졌고 **각각 정확히
  한 곳**에 있다(`slack_interactive` 셋 · `request_store` 둘) — 추측 여지가 없다. 그리고
  `_post_slack_request`가 **호출 시점에 모듈 전역을 읽으므로** setattr이 실제로 먹는다.
- Changed: 임포트를 `aws/` 경로로 고치고 다섯 대입을 **값이 실제로 사는 서브모듈**로 돌렸다.
  `handler._SFN`은 **그대로** — 거기서 읽는다(`handler.py:207,220`). 왜 서브모듈이어야 하는지를
  임포트 옆 주석에 적었다.
- Verified(**오프라인 실증**): 스크립트 자신의 `simulate`가 문서상 완전 오프라인이라 그걸로
  끝까지 돌렸다 — SQS 요청→PENDING 저장→**실제 HMAC 서명** 버튼 콜백→HTTP 200→SFN
  resume→**APPROVED**. **Slack 없이 확정됐다.**
- Changed(가드 +8, `test_harness_patch_targets_exist.py` 신규): 스크립트가 대입하는 이름을
  **AST로 뽑아** 대상 모듈에 실재하는지 묻는다(웹훅·자격증명 없이 성립). 호출 진입점 셋 ·
  옛 임포트 경로 부재도 함께. 변이: 대입 하나를 `handler`로 되돌리면 red.
  `make check` **2102**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**"기록된 이유"가 오늘만 세 번 틀렸다**(M19 ⓑ · `Resource:"*"` 전면 금지 · 이번 것).
  전부 **시험하면 값이 났다**. 남은 것: DUAL 모드 조건부 리다이렉트는 **여전히 안 만든다**
  (둘 다 경고에 못 닿아 하중을 못 받는 가드가 된다 — 이건 시험해서 확인한 게 아니라 기록 유지).
