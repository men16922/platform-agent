# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-30 — "업스트림 대기" 둘의 재개 조건을 재다: 하나는 열렸고, 하나는 다른 리스크였다 (gate 2302)

- Status: 남은 항목이 승인·콘솔 수동에 몰려 있어, **닫혀 있던 "업스트림 대기" 항목들의 재개 조건**을
  쟀다. 둘 다 기록이 낡아 있었고 **한쪽은 리스크의 성격 자체가 달랐다**. 증거 둘:
  `the-azure-extra-cannot-be-installed.log`(기존, 조건 갱신) ·
  `docs/evidence/the-dashboard-audit-record-described-a-different-risk.log`(신규).
- Verified(**`.[azure]` — 재개 조건 ①은 충족됐다**): 격리 venv(py3.13)에서 `pip install .[azure]`가
  **31.5초에 성공**한다. 08-15엔 `agent-framework>=1.0` 단독으로 **150초 타임아웃**이었다
  (`core[all]` 강제 → 무한 역추적). 지금은 **1.16.0**이고 `Provides-Extra: []` — 업스트림이 풀었다.
- Verified(**②는 미충족이고, 버전 지연이 아니다**): 진짜 라이브러리에 대고 태우니 `msft_deployer.py:19`가
  `ImportError: cannot import name 'AzureOpenAIResponsesClient'`로 죽는다. 설치 트리를 훑으니
  **`AzureOpenAI*Client` 클래스가 0개**고, 그 이름은 **업스트림 자신의 docstring 한 줄**에만 있다
  (`agent_framework_azure_contentunderstanding/_file_search.py:78`). ⇒ **여전히 안 고친다 — 대체 심볼이
  없으므로 추측은 발명.** 형제 스윕: adk/local은 **자기 extra 미설치**일 뿐이고(둘 다 선언돼 있다)
  strands는 임포트된다 — **자기 extra가 깔린 채 죽는 건 msft 하나**다.
- Verified(**⚠️Risk 11 — 기록이 세 군데 다 틀렸다**): *"PostCSS moderate 2건 · 패치 없음 · 빌드타임이라
  런타임 위험 낮음"*인데 실측은 **critical 2 · high 6**이고 **런타임**이다. `next-auth`가 *"auth checks
  **fail open**"*(critical)인데 **런타임 8파일**에 있고 그중 하나가 **승인 UI**(`pending-approvals`) ·
  next는 **미들웨어 우회·SSRF·내부 Server Function 노출** · PostCSS조차 이제 **high**(임의 `.map` 읽기).
  ⚠️**기록의 반증 실험이 `--force` 하나였다** — non-force는 **메이저 강등이 없다**. 하나의 경로에서 얻은
  답을 항목 전체의 성질로 쓴 것이고, 08-18의 *"거부가 러너 하나의 성질이었다"*와 같은 모양이다.
- Changed(**Tier A만 적용**): `npm audit fix` → **critical 2 → 0**(총 8→3). 변경은 **lockfile 32줄**이고
  **package.json은 그대로**다. `npx tsc --noEmit` 통과 · `npm run build` **exit 0**(라우트 전부 생성).
  ⛔**Tier B는 안 했다**: 남은 high 3(next·postcss·sharp)이 **`next@16.3.3`**에 달렸는데 major는 아니어도
  **프레임워크 마이너 업**이고 이 대시보드는 **조용히 강등된 이력**이 있다(Risk 1) → **결정 사안**.
- Changed(**측정이 남긴 것도 치웠다**): `pip install .`이 리포 루트에 **`build/`를 남기는데 gitignore에
  없었다** — 지우고 `.gitignore`에 넣었다(커밋될 수 있던 함정).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. ⚠️**Risk 11을 "upstream 대기"로 다시 닫지 말 것** — 업스트림은 이미 고쳤다.
- Next: **Tier B 결정**(`next@16.3.3`) · Azure executor 배선(승인) · BQ 결제 내보내기(콘솔 수동).
