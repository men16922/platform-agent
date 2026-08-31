# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-01

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

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


## 2026-09-01 — `onprem` extra의 `mlx-lm`: 선언은 있고 그걸 쓰는 곳이 없었다 (gate 2342)

- Status: `NEXT_PLAN` 08-30 항목. 기록된 근거를 먼저 다시 돌렸고 **적을 당시엔 참**이었다. 권위 `docs/evidence/the-onprem-extra-declared-a-mechanism-nobody-used.log`.
- Verified(**근거가 stale해진 게 아니라 더 나빠졌다**): PyPI 메타데이터 재측정 — 선언 하한 `mlx-lm==0.19.0`은 `mlx>=0.17.0`에 **플랫폼 마커가 없어** 리눅스 resolve가 진짜 실패한다. 그런데 `>=0.19`는 리졸버에게 **0.31.3**을 고르게 하고 거기엔 `platform_system == "Darwin"` 마커 + `py3-none-any` 휠이 있다 ⇒ **설치는 되고 엔진만 조용히 빠진다.** ⚠️**우회를 "이제 필요 없다"고 풀었으면 CI는 엔진 없는 mlx-lm을 초록으로 깔았을 것이다.**
- Verified(**그래서 우회가 아니라 선언을 물었다**): `src/`가 mlx를 임포트하는 곳 **0건**(에이전트는 MLX **서버**와 HTTP로 말한다 ⇒ 엔진은 임포트가 아니라 **프로세스**) · `.venv-mlx`엔 mlx-lm은 있고 `pydantic-ai-slim`은 없다 ⇒ **`.[onprem]`의 산물이 아니다**(08-30) · 실제 메커니즘은 `make mlx-setup`.
- Verified(**⚠️"안 쓰이니 지운다"가 아니다**): Makefile 최상단이 *"활성화된 `.venv-mlx`가 pytest를 가린다"*고 적고 인터프리터를 **탐침으로 고른다** — `.venv-mlx`가 프로젝트 env와 떨어진 건 **설계**다. `.[onprem]`이 mlx를 프로젝트 env로 들이면 그 분리를 정면으로 뒤집는다. **미사용이 아니라 틀린 메커니즘이었다.**
- Changed: `onprem`에서 `mlx-lm` 제거(근거는 주석에) · `gate.yml`이 인라인 `pydantic-ai-slim[openai]` 대신 **`.[onprem]`을 깐다** ⇒ **인라인 패키지 0개**(`serving` extra가 없앤 것과 같은 모양의 우회가 하나 남아 있었다).
- Changed(**가드 +3**): `TestMlxIsNotAProjectDependency` — 어떤 extra도 `mlx*`를 선언하지 않는다 · `src/`를 rglob으로 훑어 **전제를 코드에 묻는다** · `test_ci_requests_the_onprem_extra` + 인라인 금지 목록에 `pydantic-ai-slim` 추가.
- Verified(**⚠️내가 만든 가드 하나가 주석으로 통과했다**): *"`make mlx-setup`이 여전히 메커니즘인가"*를 `"mlx-lm" in Makefile`로 물었는데 **`MLX_BIN` 위 주석**에 그 문자열이 있어 레시피를 깨도 초록이었다. **주석이 주어인 규칙은 규칙이 아니다.**
- Verified(**⚠️그걸 "레시피 가드가 없다"로 읽은 것도 틀렸다 — Risk 12⑦ 재발**): 변이를 **이 파일에만** 물어서였다. 전체 스위트엔 red고, `test_local_stack_prerequisites.py::test_something_creates_the_venv_the_stack_runs_from`이 **레시피를 직접 읽는 옳은 자리의 옳은 질문**이었다 ⇒ 내 약한 사본은 **지우고** 어디가 그 자리인지 주석으로 적었다(두 번째 사본은 첫 번째의 그림자).
- Verified(**변이**): M1 extra 복귀 red · M2 인라인 복귀 red(2건) · M3 `src/`가 mlx 임포트 red · M4 레시피 깸 red(**전체 스위트에서**) · M5 규칙 무력화 **초록 — 설명됨**(현재 위반 0건이라 꺼도 관측 불변; 그 규칙의 하중을 재는 변이는 **M1**이고 red다).
- Blockers: 없음. ⚠️**리눅스 resolve는 로컬에서 증명 못 한다** — 이 PR의 CI 체크가 그 답이다.
- Next: **정적검사를 게이트에 넣을지**(lint 20건·mypy 253건 — **레포의 결정**) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.
