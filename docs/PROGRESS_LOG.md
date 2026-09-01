# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-01

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

## 2026-09-01 — 시그니처는 필수라 했고 본문은 선택이라 했다: 그 기본값이 정책이었다 (gate 2368)

- Status: mypy 253을 **분류하다가** 나왔다. **결정은 여전히 안 내렸다.** 권위 `docs/evidence/the-signature-said-required-the-body-said-optional.log`.
- Verified(**`arg-type` 15 중 10이 한 함수**): `onprem_webhook_api`가 `summary.get(...)`를 `record_incident(severity: str, …)`의 **필수 `str`** 자리로 넘긴다. 그런데 본문은 다섯 다 **`x or "기본값"`** — **본문은 처음부터 `None`을 받도록 쓰여 있었다. 코드가 옳고 선언이 거짓이었다.**
- Verified(**`None`은 도달 가능하다**): 파이프라인 결과는 **키를 항상 갖지만 값이 `.get()` 결과**이고, 그 위에 파이프라인이 스스로 `incident = detector_out.get("normalized_incident") or {}`라 적어 뒀다 — **부재를 예상했다는 저자들 자신의 진술**이다. 없으면 `service`가 `None`으로 `alarm_name`에 도착한다. ⚠️`else: # MANUAL` 가지는 **`mode`가 `None`일 때도 걸린다**.
- Changed: 다섯을 `str | None`로. ⚠️**문을 닫는 쪽이 아니다** — 거부하면 **저하된 인시던트가 "인시던트 없음"이 된다**. `arg-type` **15→5**, mypy **253→241**.
- Changed(**⚠️진짜 발견은 그다음 — 가드 +10**): 주석을 고치는 건 **도는 것을 하나도 안 바꾼다**. 도는 것은 **기본값 부여**이고, `record_incident`를 쓰는 테스트 7개 중 **다섯 필드에 `None`을 넘기는 파일이 0개**였다 ⇒ **저하된 인시던트의 분류가 무단언**이었다. 둘은 그냥 기본값이 아니라 **축의 안전한 끝**이다: **MANUAL**=실행하지 **않는** 모드(AUTO로 기본값이 되면 **아무도 고르지 않은 조치가 나간다** — M39의 반대편) · **P3**=척도의 **바닥**(P1이면 불완전한 analyzer 출력마다 사람을 호출한다). 신규 가드는 문자열이 아니라 **어느 끝인지**를 묻고 **저장된 행까지** 읽는다(반환값만 보면 파일에 `null`이 적혀도 통과한다).
- Verified(**변이 4 red · 1은 못 쟀다**): mode→AUTO(3 failed) · severity→P1(3) · 기본값 제거(2) · 주어진 값 무시(1). ⚠️**M5(저장 건너뛰기)는 단일 호출 지점이 없어 변이가 안 붙었다** — *"안 쟀다"*로 남긴다.
- Verified(**곁가지 — mypy 오탐 하나를 격리했다**): `return-value` 4건이 전부 `x or os.getenv(k, DEF)` 모양인데, `os.getenv(k, DEF)` 단독은 `str`, `x or "literal"`도 `str`, `x or y`도 `str`인데 **`x or os.getenv(k, DEF)`만 `str | None`**이다 — `or`의 오른쪽에서 **오버로드가 첫 번째로 재해석**된다(mypy 1.14.1). **런타임엔 None이 될 수 없다** ⇒ 고치지 않았다.
- Verified(**누적 그림 — 결정에 줄 숫자**): 실제 주장 53 중 **21건을 열었다** → **실제로 고칠 값이 있던 건 2건**(M44의 계약 갭 + 이 선언 불일치), 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*(오탐 4 · 도달 불가 2 · 재-export 3 · 이종 dict 2 · 이름 재선언 1 · 미설치 라이브러리 2 · 기타). **그게 이 도구의 이 레포에서의 신호 대 잡음비다.**
- Blockers: 없음.
- Next: **정적검사 게이트 편입 — 이제 숫자를 갖고 물을 수 있다**(사용자/레포 결정) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.


## 2026-09-01 — 계약이 모두가 부르는 메서드를 빠뜨리고 있었다: 찾은 건 mypy였다 (gate 2358)

- Status: *"정적검사를 게이트에 넣을지"*의 **선행 실측을 다시 돌리다가** 나왔다. **결정은 내리지 않았다.** 권위 `docs/evidence/the-contract-omitted-the-method-everyone-calls.log`.
- Verified(**기록의 "전수 분류 결함 0"이 재현된다**): 가장 위험해 보이는 여섯을 실제로 열었다 — `dep_id`(넘길 파라미터가 **아예 없다**) · `azure_runner.url`(각 분기가 자기 URL을 만든다, **죽은 코드**) · F402(문자열 루프 변수와 **이름만** 겹침) · `original_guard`(**새 인스턴스**라 복원할 게 없다) · `result`(단언은 put_item 부작용에 건다) · E701 ×5(열 맞춤). **20건 전부 미관/죽은 변수.**
- Verified(**없던 반쪽 — mypy 253의 성격**): `type-arg` 71·`import-untyped` 40·`no-any-return` 36·`no-untyped-def` 32·`no-untyped-call` 21 = **200/253(79%)이 주석 부채**이고 나머지 **53이 실제 타입 주장**이다. **"253"은 절망적으로 읽히고 "200은 부채, 53이 주장"은 결정 가능하게 읽힌다.**
- Verified(**나머지 여섯은 닫았다 — "모른다"와 "도달 불가"는 다른 답이다**): 재-export 셋은 런타임 무관 · `model_router`의 `None` 역참조 둘은 **재서 도달 불가**다 — 업스트림이 *"if it has ended, otherwise None"*이라 관건은 **어디서 읽는가**이고, `result = run.result`가 `async for`를 **완주한 뒤**(본문에 `break` 없음)에 있다. 예외도 `GeneratorExit`도 그 줄에 못 닿는다. **mypy는 선언 타입에 대해 옳고 코드도 옳다** — 좁히기를 안 썼을 뿐. **다음 세션이 같은 줄을 다시 파지 않게 적어 둔다**(마른 스윕도 측정, M26).
- Verified(**⚠️그 53 중 하나가 진짜였다**): `"ExecutionAdapter" has no attribute "parameters_for_action"` — 네 어댑터가 **다 구현**하고 `aws/executor.py`가 **베이스 타입을 통해 부르는데** 계약이 선언하지 않았고 **테스트는 그 이름을 한 번도 언급하지 않는다(0건)**. ⚠️**오늘 런타임 결함은 없다**(넷 다 있다). 나쁜 건 호출부가 `except Exception: pass`라는 것 — 베이스를 만족시키는 데 `resolve_action` **하나면 충분**했으므로, 다섯째 provider가 그 조건만 채우면 `AttributeError`가 **삼켜지고 AWS 모양 파라미터**를 받는다. **에러 나지 않는 방식으로 실패한다**(Risk 8).
- Verified(**⚠️`from_alarm_context`는 고치지 않았다**): 정의가 **AWS 하나**뿐이고 호출도 `get_signal_adapter("aws")`로 **리터럴 고정**이라, 베이스에 선언하면 나머지 셋에 **거짓**이 된다. 기준은 *읽는 쪽의 provider 간 비대칭*이지 고아 선언이 아니다(M19 ⓑ) — **리터럴 고정 호출엔 틀릴 비대칭이 없다.**
- Changed(**가드 +8**): 베이스에 `parameters_for_action` 선언 + 신규 `test_adapter_contract_declares_what_callers_call.py` — **목록이 아니라 AST 유도**: provider가 **변수면 베이스가 선언해야 하고 리터럴이면 면제**(정규식으론 둘을 못 가른다) · 형제 넷이 계약 전체를 구현하는가(선언만 하면 `NotImplementedError`가 같은 `except`에 삼켜지니 **선언은 절반**).
- Verified(**⚠️내가 두 번 더 틀렸다**): ⓐ면제 테스트를 **`assert … or True`**로 끝냈다 — assertion이 아니고 무엇에 대고도 통과한다. 세션 내내 *실패할 수 없는 규칙*을 찾아 온 손이 그걸 썼다 ⇒ **면제가 실제로 무언가를 면제하는지** 묻게 고쳤다. ⓑM3(호출부 provider를 리터럴로)이 이 파일에서 초록이라 **또 한 파일에서 읽을 뻔했는데, 전체 스위트에 물으니 이번엔 진짜였다**(2356 passed — 아무것도 안 잡는다): provider를 **인자로 받은 함수가 그걸 무시하고 AWS를 하드코딩해도** 레포가 초록이다(M23과 같은 모양). **내 면제가 만든 탈출구라 내가 닫았다.**
- Verified(**변이 5종 전부 red**): 베이스 선언 제거 · gcp 구현 제거 · **호출부 리터럴화**(닫기 전엔 전체 스위트도 초록) · 스윕 공허화 · 면제 무력화. 복구는 `__pycache__` 삭제 후 확인.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 여전히 사용자/레포 결정** — 이 증분은 *"켜라"*가 아니라 **"이 도구가 이 레포에서 무엇을 찾는가"의 한 표본**이다 · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.


## 2026-09-01 — 게이트가 안 돈 PR을 "CI 초록"으로 읽었다: 없는 것과 통과한 것이 같은 색이다 (gate 2350)

- Status: 이번 세션이 **직접 밟은** 것을 고쳤다. 권위 `.github/workflows/gate.yml` 트리거 블록 주석 · `tests/test_the_gate_runs_on_every_pull_request.py`.
- Verified(**⛔먼저 오해를 막을 것 — `main`은 무방비였던 적이 없다**): 브랜치 보호가 `check` 컨텍스트를 **요구**하고(`required_status_checks.contexts == ["check"]`), 게이트는 **main 대상 PR에선 언제나 돌았다**. **D43은 계속 성립했다.**
- Verified(**그럼 무엇이 문제였나 — 스택 PR**): `pull_request: branches: [main]` 필터 때문에 **base가 다른 브랜치인 PR엔 이 job이 아예 안 돈다**. PR **#58**(base = M39 브랜치)에서 `gh pr checks`가 *Amazon Q: pass / Vercel: pass / Vercel Preview Comments: pass*를 답했고 **`check` 행이 아예 없었다** — 그걸 "CI 초록"으로 읽었다. ⚠️**없는 것과 통과한 것은 그 목록에서 같아 보이고, 차이는 읽는 사람이 채운다.**
- Verified(**이건 이 레포가 이미 이름 붙인 실패의 한 층 위다**): Risk 12②가 *"skip은 실패가 아니라서 **검사 안 하는 게이트와 통과한 게이트가 같은 색**"*이라 적었다 — 거기선 **건너뛴 테스트**였고 여기선 **안 돈 워크플로**다. 같은 모양, 한 층 위.
- Changed: `pull_request`에서 `branches` 필터 제거 ⇒ **모든 PR이 게이트를 받는다**. CI 몇 분을 더 쓰고 **초록이 어디서나 같은 뜻이 된다**. 이유는 트리거 블록 주석에 적었다.
- Changed(**가드 +4**): 트리거가 존재하는가(공허성) · **base 필터가 없는가**(진짜 고침) · 이유 주석이 `#58`·`Risk 12`를 계속 가리키는가. ⚠️**YAML 1.1은 맨 `on:`을 불리언 `True`로 읽는다** — `wf["on"]`만 본 테스트는 KeyError로 *"트리거가 없다"*를 답했을 것이라 **둘 다** 조회한다(자기가 막는 실패와 같은 모양).
- Verified(**⚠️경계**): **게이트가 병합 조건이라는 것은 이 파일이 주장하지 않는다** — 그건 GitHub 브랜치 보호에 있지 레포에 없다. `test_signature_gate_claims`가 **배선을 앞질러 간 주장**의 표준 사례다. 레포 안에 있는 절반만 묻는다.
- Verified(**변이 4종 전부 red**): `branches` 필터 복귀 · `branches-ignore` 형태 · `pull_request` 트리거 제거 · 이유 주석 삭제.
- Changed(**재개 방지**): `docs/plans/2026-08-08-phase4-scope-and-cost.md`의 4a 절이 아직 **착수 대상**으로 읽혀 *"끝났고 접혔다"* 박스를 얹었다(§10·§11 · M38·M40 · D50 Folded를 가리킨다).
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.
