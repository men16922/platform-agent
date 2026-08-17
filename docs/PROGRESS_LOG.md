# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-17 — ⓐ를 시험하니 답은 "현행 유지"였고, 스윕이 결함 넷을 냈다 (gate 2257)

- Status: 무과금 목록에 남은 **capability 스캔 ⓐ·ⓒ**. 규율대로 **기록된 이유부터 시험**했다.
- Verified(**ⓐ의 주장은 성립**): `kafka-lag-spike`가 유일하고 어긋남은 **한 방향뿐**(반대 0건 —
  ⚠️처음엔 한 방향만 물었다). ⚠️**내 픽스처가 한 번 틀렸다**: resolve는 **(capability,
  resource_type) 쌍**으로 키를 거는데 `kafka-topic`으로 물어 *"네 provider 전부 미구현"*으로
  읽었다. 올바른 `streaming-consumer`로는 **전부 resolve된다.** 주장 전에 잡았다.
- Verified(**두 선택지는 대칭이 아니다** — 08-12엔 "둘 다 동작 변경"이었다): 티어 2(GCP/Azure)는
  액션을 **steps가 아니라 `recommended_capabilities`에서** 만들고 `capabilities`는 **매치
  게이트일 뿐**이다. `scale_out_workers`가 이미 겹쳐 **더해도 관측 변화 0**, **빼면 네 provider가
  다 resolve하는 에스컬레이션 스텝을 잃는다.** ⇒ **현행 유지로 닫는다.**
- Verified(**스윕이 결함 넷 — 찾던 건 하나였다**): 네 signal 어댑터 × 전 resource_type을 AST로
  훑고 **빠진 capability가 그 provider에서 resolve되는지**까지 물었다. ①`streaming-consumer`/
  `rebalance_consumer`가 **Azure만 없다**(3대1)는데 Azure는 **구현하고 있다**. 네 어댑터는 **같은
  커밋 `a22a283`에서 태어났고 Azure는 처음부터 빠져 있었다**(stale이 아니라 **쓰일 때부터 틀림**).
  ②③④`kubernetes-workload`/`rollback_release`는 **onprem만 추천**하고 셋은 구현했는데 안 한다 —
  ⚠️**1대3, 소수가 갖고 있다**. 롤백은 파괴적이라 **내가 정할 게 아니라** 알로리스트에 이유를
  달아 **사람 결정으로 남겼다.**
- Changed: Azure 추천에 `rebalance_consumer` 하나(+이유). ⚠️**Azure executor가 실행 없이
  resolved를 보고하는 열린 항목과 맞닿는다** — 클레임이 하나 늘지만 **라이브 변경은 없다**(no-op).
  그 항목을 고칠 이유이지, 구현을 못 쓰게 둘 이유는 아니다.
- Changed(가드 +6, `test_signal_capability_parity.py` 신규): 규칙은 **"추천 안 해도 되는 건 실행
  못 하는 것뿐"**. 알로리스트는 이유 없으면 못 넣고 ⚠️**현실과 어긋나면 red**. 공허 통과 방지도
  뒀다 — **AST가 아무것도 못 읽으면 나머지가 저절로 통과**한다(내가 그 함정에 빠졌다).
- Verified(**변이 4종 전부 red**): 고침 되돌리기 · 다른 provider에 새 구멍 심기 · 알로리스트 한
  줄 비우기(=실재하는 구멍을 덮고 있다) · 알로리스트 stale화. `make check` **2257 passed, 2 skipped**.
- Blockers: 없음. ⛔남은 정책 결정(`rollback_release`)은 `NEXT_PLAN`에 있다.
- Next: 08-19 이후 AMP 청구액 대조 · ⓒ(첫-매치 vs 점수제)는 **미측정**.

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
