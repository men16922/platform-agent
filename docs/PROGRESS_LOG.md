# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-01

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

## 2026-09-01 — 계약이 모두가 부르는 메서드를 빠뜨리고 있었다: 찾은 건 mypy였다 (gate 2358)

- Status: *"정적검사를 게이트에 넣을지"*의 **선행 실측을 다시 돌리다가** 나왔다. **결정은 내리지 않았다.** 권위 `docs/evidence/the-contract-omitted-the-method-everyone-calls.log`.
- Verified(**기록의 "전수 분류 결함 0"이 재현된다**): 가장 위험해 보이는 여섯을 실제로 열었다 — `dep_id`(넘길 파라미터가 **아예 없다**) · `azure_runner.url`(각 분기가 자기 URL을 만든다, **죽은 코드**) · F402(문자열 루프 변수와 **이름만** 겹침) · `original_guard`(**새 인스턴스**라 복원할 게 없다) · `result`(단언은 put_item 부작용에 건다) · E701 ×5(열 맞춤). **20건 전부 미관/죽은 변수.**
- Verified(**없던 반쪽 — mypy 253의 성격**): `type-arg` 71·`import-untyped` 40·`no-any-return` 36·`no-untyped-def` 32·`no-untyped-call` 21 = **200/253(79%)이 주석 부채**이고 나머지 **53이 실제 타입 주장**이다. **"253"은 절망적으로 읽히고 "200은 부채, 53이 주장"은 결정 가능하게 읽힌다.**
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


## 2026-09-01 — 셋째 형제는 mypy였다: 정적검사 선행을 재다가 나왔다 (gate 2346)

- Status: `NEXT_PLAN`의 *"정적검사를 게이트에 넣을지"*는 **레포의 결정**이라 묻지 않고 **선행 실측 둘만** 다시 쟀다. 재는 도중에 나왔다. 권위 `docs/evidence/the-third-sibling-was-mypy.log`.
- Verified(**기록은 둘 다 맞았다**): `make lint` **20건**(F841 8·E731 5·E701 5·F402 1·E712 1 · src 7·tests 13, ruff 0.15.10) · mypy **253 errors in 88 files (166 checked)** — 기록 *"253 across 88 of 165"*와 일치(파일이 하나 늘었다).
- Verified(**⚠️그런데 그 253은 그냥은 안 나온다**): `mypy src/`는 `cdk.out`의 **중복 모듈에서 수집 단계에 죽는다** — *"Found 1 error in 1 file (errors prevented further checking)"*. 253을 보려면 `--exclude`를 손으로 붙여야 했다 ⇒ **선언된 설정이 그대로는 실행조차 안 됐다.** `pyproject.toml`은 그 블록을 *"the settings are the target"*이라 적어 뒀는데 **못 돌리는 target은 돌려서 실패하는 target보다 약하다.**
- Verified(**⚠️Risk 12⑥ 재발 — 그것도 그 규칙을 집행하려고 만든 가드 안에서**): 08-30에 pytest↔ruff 비대칭을 고치며 만든 가드의 파일명이 **`..._from_both_tools.py`(both=둘)**였는데 같은 `pyproject.toml`에 **`[tool.mypy]`가 셋째 형제로 있었고 두 경로 중 아무것도 안 적고 있었다**. ⚠️**빠진 쪽이 하필 가장 나쁜 형제였다** — ruff의 실패는 시끄럽고 오락가락(20↔6,527)인데 mypy의 실패는 **총체적**이고(우리 코드를 한 줄도 안 본다) 문장이 *"1 error"*라 **작아 보인다**.
- Changed: `[tool.mypy] exclude` 추가 ⇒ `mypy src/`가 이제 그냥 돈다. 가드는 `..._from_every_tool.py`로 개명하고 **셋 다 순회**. ⚠️**게이트 편입은 바뀐 게 없다** — 선언을 실행 가능하게 만든 것뿐이고 결정은 그대로 레포의 것이다.
- Changed(**가드의 가드 — 변이가 시켜서 만들었다, +3**): 첫 판의 `TOOLS`는 **손으로 적은 dict**라 **M5(=TOOLS에서 mypy 제거)가 초록으로 살아남았다** — **이 파일의 주제가 이 파일에 그대로 일어났다: 세는 일 자체를 아무도 안 세고 있었다**(내 docstring은 *"derived, not listed"*라고 **코드가 안 하는 걸 주장**했다). ⇒ `pyproject`의 `[tool.*]`에서 제외 키를 **유도**해 `TOOLS`와 양방향 대조.
- Verified(**⚠️재는 동안 두 번 더 틀렸다**): ⓐ`mypy src/`가 **252**를 답한 적이 있는데 그건 **증분 캐시**였다(`--no-incremental`·캐시 삭제 둘 다 253) — 하마터면 *"기록이 틀렸다"*고 쓸 뻔했다. **캐시된 답은 측정이 아니다**(Risk 12⑦ `.pyc` 계열). ⓑ**변이를 적용하지 않고 변이를 쟀다** — 정규식이 과도 이스케이프돼 한 건도 안 지웠는데 두 후보의 시간을 쟀고, `diff`로 대조해서야 알았다. **변이 적용부터 확인하고 결과를 읽을 것.**
- Verified(**게이트 비용**): `mypy src/` **49.2s**(게이트 36초의 배)를 `mypy src/stacks/` **0.13s**로 바꿨다 — 결함이 사는 바로 그 자리이고 답이 둘뿐이라 공허하지 않다. 진짜 253은 손으로 재서 `pyproject`에 적었다. **집행 안 하기로 한 숫자를 재느라 게이트를 두 배로 만드는 건 나쁜 거래**(D49가 288s→39s를 얻은 이유).
- Verified(**변이 8종**): M1 mypy exclude 삭제 red(2) · M2 부분 드리프트 red · M3 ruff 삭제 red(3) · M4 pytest 삭제 red · **M5 red(고치기 전엔 초록)** · M6 초록—**설명됨**(위반 0건이라 꺼도 관측 불변; 하중은 M1이 재고 M1이 그 테스트를 죽인다, 귀속 확인) · M7 새 도구가 exclude 선언 red · M8 유도 무력화 red.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 이제 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.
