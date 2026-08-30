# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-30 — 문서화된 `make dev-up`이 새 클론에서 못 돌았다 (gate 2311)

- Status: `AGENT_BRIEF`가 *"`make dev-up`으로 로컬 스택 **한 방 기동**"*이라 적어 뒀다. 그 약속을
  **새 클론 관점**에서 물었다. 증거 `docs/evidence/make-dev-up-launched-a-venv-nothing-created.log`.
- Verified(**쓰는 곳 셋, 만드는 곳 0**): `mlx-serve`·`local-llm-up`·`dev-up`이 `.venv-mlx/bin/mlx_lm.server`를
  띄우는데 **그 venv를 만드는 타깃이 없다**. gitignore돼 있고 이 기계에 **손으로** 만들어져 있었다.
- Verified(**`.[onprem]`의 산물도 아니다**): 그 venv엔 mlx-lm·mlx가 있고 **`platform-agent`도
  `pydantic-ai-slim`도 없다**(36개). ⇒ **`onprem` extra는 mlx-lm이 설치되는 경로가 아니다.** ⚠️그런데 그
  항목이 **CI에 비용을 물린다** — `gate.yml`이 그것 때문에 `pydantic-ai-slim`을 **인라인으로** 적는다
  (fastapi에 대해 이미 한 번 고친 우회). 그리고 그 근거 *"linux에서 resolve 안 된다"*는 **하한 0.19.0엔
  참**이었고(당시 `mlx>=0.17.0`에 마커 없음) **지금은 거짓**이다(현재 `mlx`에 Darwin 마커 → **설치되고
  엔진만 조용히 빠진다**). **실패 모양이 시끄러운 것에서 조용한 것으로 바뀌었다.**
- Verified(**그래서 조용히 깨진다**): 세 지점 중 **둘이 `nohup ... &` + stdout을 로그로** 보낸다. 새
  클론의 `dev-up`은 *"model load takes ~30-60s"*를 찍고 **계속 진행**하며, 프록시는 그다음 **아무것도 없는
  곳에 말을 건다.** Risk 7·8과 같은 계열이다.
- Changed: `make mlx-setup`(없을 때만 생성) + 세 지점에 **실행 전 검사**. ⚠️`dev-up`의 검사는 **실제로
  띄우려는 분기 안**에 뒀다 — 이미 떠 있는 MLX를 재사용하는 경로엔 venv가 필요 없고, 거기서 막으면
  **없는 요구사항을 만드는 것**이다. 실측으로 확인했다(venv를 잠시 옮겨 두고 `mlx-serve`·`dev-up` 둘 다 red).
- Verified(**⚠️내가 만든 가드가 한 번 틀렸다 — 그대로 기록한다**): `mlx-setup` 첫 판이
  `@test ! -x ... || { echo; exit 0; }`를 **자기 줄에** 뒀는데 **Make는 레시피 줄마다 셸이 따로**라 그
  `exit 0`이 다음 줄을 못 막았고 **pip가 기존 venv에 그대로 돌았다**(최신이라 아무것도 안 바뀌었음을
  36개 패키지·서버 바이너리로 확인). ⇒ **뒤따르는 것을 막지 못하는 검사는 검사가 아니다** — 이 레포가
  한 층 위에서 계속 찾던 그 모양이 내 손에서 났다. 한 셸 블록으로 고쳤다.
- Changed(**가드 +5**): `test_local_stack_prerequisites.py` — 만드는 타깃이 있는가 · **모든 실행 지점이
  실행 전에** 검사하는가(**순서까지**) · 실행 지점이 셋 이상 찾아지는가(공허 방지).
  ⚠️`.venv-mlx` **존재는 일부러 단언하지 않는다**(gitignore·기계별·Apple Silicon 전용 — CI에서 red가 나면
  약속이 깨진 게 아니라 **가드가 틀린 것**이다). 변이 4종 red(타깃 삭제 · 검사 제거 · **검사를 실행 뒤로
  이동** · 경로 철자 깨기).
- Verified: `make check` **2311 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. `onprem` extra의 `mlx-lm` 처리는 **결정 사안**으로 `NEXT_PLAN`에 올렸다(⚠️`mlx`가 CUDA
  리눅스도 지원한다고 해서 Darwin 마커가 옳은지는 자명하지 않다).
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정).

## 2026-08-30 — 두 번 "미검증"이라 적어 둔 주장을 재다: 거짓이었다 (gate 2306)

- Status: `AGENT_BRIEF`와 `STATUS` Risk 12②가 **두 번** *"`requires-python = ">=3.11"`은 아무도
  확인한 적 없는 주장"*이라 적어 뒀다. 이 기계에 python3.11이 있는 걸 보고 **처음으로 쟀다**.
  증거 `docs/evidence/requires-python-was-an-unverified-claim-and-it-was-false.log`.
- Verified(**첫 시도는 내 잘못 — 기록해 둔다**): `.[dev]`만 깔고 돌리니 **수집 에러 7개**(`fastapi` 5 ·
  `pydantic_ai` 2)가 나 M25 계열로 보였다. **아니었다** — `fastapi`는 `serving`, `pydantic-ai-slim`은
  `onprem`에 **선언돼 있고** CI는 `.[dev,state,observability,serving]`+`pydantic-ai-slim[openai]`를 깐다.
  ⚠️**"게이트가 red다"라고 말하기 전에 CI와 같은 줄로 깔았는지부터 물을 것.**
- Verified(**3.11은 red**): CI와 같은 줄로 다시 깔고 → **2 failed, 2300 passed**. ①SSE 스트림이
  `done` 대신 `error`로 끝난다(anyio *"exit cancel scope in a different task"*) ②monkeypatch가
  `time.sleep`에 심은 `StopIteration`이 루프를 빠져나온다.
- Verified(**⚠️결론 전에 교란 요인을 지웠다**): 3.11 venv는 오늘 새로 해석돼 이 기계의 오래된 3.13보다
  **최신 패키지**를 받았다(starlette **1.6.0 vs 1.3.1** · pytest **9.1.1 vs 8.3.4**). 그래서 실패가
  **인터프리터 탓인지 의존성 최신화 탓인지 아직 몰랐다.** ⇒ **fresh 3.13**을 같은 줄로 만들었더니
  **3.11과 같은 버전으로 해석**되고 **2302 passed 초록**이었다. **같은 의존성·다른 인터프리터** ⇒
  **인터프리터 탓이고 주장은 거짓**이다. ⚠️곁가지: 이 기계의 상시 3.13 환경이 **stale**하다는 것도
  드러났다(둘 다 초록이라 다행이지만, **그건 확인해서 안 것이지 가정한 게 아니다**).
- Changed(**선언을 측정에 맞췄다**): `requires-python` `>=3.11`→**`>=3.13`** · ruff `target-version`
  `py311`→`py313` · mypy `python_version` `3.11`→`3.13`. **셋은 한 결정의 세 철자**였고 셋 다 틀린 수를
  들고 있었다(M19). ⚠️**좁혀도 안전한지 먼저 물었다** — 워크플로가 둘이고 **파이썬이 다르다**
  (`gate.yml` 3.13 · **`sign-image.yml` 3.11**). 형제를 안 셌으면 여기서 깨졌다: 실측 결과 그 워크플로엔
  **`pip install`이 0개**고 돌리는 스크립트가 **표준 라이브러리만** 쓴다 ⇒ 영향 없다.
- Verified(**곁가지 — `[tool.mypy] strict = true`는 아무도 안 돈다**): Makefile·CI·scripts·pre-commit
  어디에도 mypy 호출이 없다(`.mypy_cache` 흔적만). 실측 **253 errors / 88 of 165 files**. **안 지웠다** —
  게이트에 넣는 건 `gate.yml`이 lint에 대해 적어 둔 것과 같은 결정이다(*"a CI job is a bad place to
  introduce a standard nobody agreed to"*). 대신 **주석으로 사실을 적고** 가드가 그 주석을 지키게 했다.
- Changed(**가드 +4**): `test_pyproject_claims.py` — 세 버전 선언 일치 · 바닥이 돌리는 인터프리터보다
  높지 않음 · **`[tool.X]`는 불리거나 왜 안 불리는지 적혀 있어야** · 공허 방지. ⚠️게이트가 선언된
  바닥에서 통과하는지는 **일부러 단언하지 않는다**(스위트 안에서 다른 인터프리터로 스위트를 도는 일).
- Verified: `make check` **2306 passed, 2 skipped**(로컬 macOS·py3.13) · ruff 20으로 결정론 유지.
- Blockers: 없음. Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) ·
  **mypy/lint를 게이트에 넣을지**(결정 — 각각 253·20건이 선행).

## 2026-08-30 — Tier B 수행: 대시보드 취약점 8 → 0, 그리고 "새 소견 0"을 재서 말했다 (gate 2302)

- Status: 승인 후 Tier B(`next 16.2.10 → 16.3.3`)를 적용했다. **소스 변경 0** — `package.json` 2줄과
  lockfile뿐이다. 증거는 같은 로그의 **§Tier B 수행**.
- Verified(**8 → 0**): `npm audit`이 **critical 0 · high 0 · total 0**. Tier A(`audit fix`)가 critical 2를
  0으로 내렸고 남아 있던 high 3(next·postcss·sharp)이 전부 이 업그레이드에 달려 있었다. peer는 맞는다
  (16.3.3이 `react ^19.0.0`을 요구하고 대시보드는 **19.2.4**).
- Verified(**조용히 실패하는 쪽을 겨눴다**): `tsc` 통과 · `build` **exit 0** · ⚠️**라우트 매니페스트를
  before/after로 대조**해 **17개 완전 동일**을 확인했다. Risk 7·8이 가르친 모양이다 — 타입은 초록인데
  런타임이 죽고, 차트는 Synced인데 파드가 0개였다. **빌드가 통과했다는 것과 같은 걸 냈다는 건 다르다.**
- Verified(**⚠️"기존 것"을 가정하지 않고 쟀다**): `npm run lint`가 **41 problems**를 낸다. 소스를 안
  건드렸으니 기존 것이라 **말할 수는 있었지만**, `react-hooks/set-state-in-effect`가 새 룰일 수 있어
  `git worktree`로 **main을 따로 체크아웃해 `npm ci` 후 같은 명령**을 돌렸다 → **41 problems (33 errors,
  8 warnings)**로 **완전히 동일**, 룰 분포까지 같다. ⇒ **새 소견 0.** 의심을 사실로 바꾸는 데 worktree
  하나면 충분했다. (대시보드 eslint는 게이트도 CI도 아니다 — `gate.yml`이 그 이유를 적어 뒀다.)
- Changed: `STATUS` Risk 11 **해소**로 전환하되 ⚠️**"기록이 세 군데 다 틀렸다"는 남겼다** — 결론이
  닫혔다고 그 항목이 왜 틀렸는지가 지워지면 같은 방식으로 다시 닫힌다. `NEXT_PLAN`의 Tier B 결정 항목은
  ⛔닫힘으로 옮겼다.
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13) — py 쪽 변경 0.
- Blockers: 없음.
- Next: **Azure executor 배선**(승인 — 근거는 08-30에 다시 세워 뒀다) · **BQ 결제 내보내기**(콘솔 수동) ·
  **`make lint` 20건 처리 여부**(결정).
