# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-16 — Qwen3.8-27B로 바꿀 만한가: 쟀다. 아니다 (첫 측정은 무효였다)

- Status: 사용자가 전한 요약에 *"27B가 Opus 4.6급"*이 있었는데 원문 대조에서 **비교 대상은
  Opus 4.8**이고 **비교된 건 27B가 아니라 2.4T(활성 95B)**였다. 27B에 대한 원 출처 주장은
  *"자사 Qwen3.7-Plus를 앞선다"* 하나뿐. **논쟁 대신 레포 하네스로 쟀다.**
- Verified(동일 절차 — 서버 교체→준비 대기→**워밍업**→같은 20문항×온도 2단계):
  현재 **30B-A3B 0.95(19/20) / 3.7s·4.2s** vs 후보 **27B 1.00(20/20) / 15.1s·15.6s**.
  라이브 40건·백스톱 0(양쪽). **품질 차 한 문항 = 해상도 ±5%p와 같아 노이즈와 구별 불가** ·
  지연 **최소 4배**. ⚠️재실행에서 19.9s/24.6s(+32%/+58%)라 **정확한 배수는 주장 안 한다.**
  ⚠️활성 파라미터 비 9배보다 **덜** 느렸다(4배) — **내 사전 추정도 틀렸다**(대역폭 바운드).
- Verified(⚠️**첫 측정 무효**): `live calls: 0`인데 `pass=1.00`이 나왔다 — 백스톱 점수였다.
  재현으로 원인 확정: 27B는 추론 모델이라 `max_tokens=16`을 전부 사고에 쓰고 응답에
  **`content`가 없다**(`reasoning`만) → `KeyError` → 백스톱. **하마터면 "27B 완벽"으로
  보고할 뻔했다.**
- Changed(**하네스 가드 구멍**): `if stats["mismatch"]` 가드는 *"다른 모델이 답했을 때"*만
  잡고, **호출이 그 검사에 닿기 전에 죽으면 `calls=0, mismatch=0`으로 통과**시켜 오염된
  스코어보드를 저장했다. **`calls == configs×cases×trials`를 요구**하도록 고쳤다.
  양방향 확인: 오염 조건 → `only 0 of 40 ... nothing persisted`(파일 미생성) · 정상 → 저장됨.
- Verified(재기 전 잡은 함정 넷): `chat_template.jinja` 미다운로드(`allow_patterns`가 `.jinja`
  누락) · 27B 템플릿이 시스템 프롬프트에 226자 주입(기준선은 주입 0) · ⚠️**`low`가 아니라
  `medium`이 깨끗**(직관과 반대) · 스윕의 `effort`는 reasoning이 아니라 **샘플링 온도**.
  최종적으로 **`enable_thinking=false`** 하나로 정리. `make check` **2076**, 로컬 macOS·py3.13.
  증거 `qwen38-27b-ab-measured-not-argued.log`.
- Changed(가드 +5, `test_sweep_contamination_guard.py` 신규): 고친 가드가 **`scripts/`에 있어
  게이트가 안 덮고 있었다** — 지워도 아무도 red가 안 났다. `spec_from_file_location`(레포 선례)로
  `main()`을 실제로 돌린다: 추론-only 응답 → 거부 + **파일 미생성** · 정상 응답 → 저장 ·
  **옛 mismatch 가드도 여전히 동작** · 에러가 원인(`max_tokens`/`reasoning`)을 말하는가.
  변이 5건 red(새 가드 제거 3 · 기대치 무력화 3 · mismatch 제거 1 · 상시 발화 1 · 문구 1).
- Blockers: 없음.
- Next: ⚠️**exit 0 ≠ 작업 완료** — `run_in_background` 안에 `&`를 또 써서 래퍼가 즉시 끝났고
  그 완료 알림을 측정 완료로 읽을 뻔했다. **알림이 무엇의 종료인지 확인할 것.**
  그리고 **사고 모드 품질은 못 쟀다**(하네스가 `max_tokens=16` 하드코딩 — 다른 계측기 일).

## 2026-08-15 — 세 번 어긴 규칙을 약속 대신 가드로 바꿨다 (gate 2073)

- Status: 오늘 문서 예산을 **세 번 어겼고 매번 커밋 후에 알았다**(그리고 `--amend`로 고쳤다).
  "다음부터 커밋 전에 확인하겠다"는 **약속이지 집행이 아니다** — D45가 정확히 그렇게
  참이기를 그만뒀다(→D49). 그래서 가드로 바꿨다.
- Verified(**선언은 셋, 집행은 0**): `.claude/harness-config.json`의 `budgets` ·
  `DOCS_POLICY.md`의 표 · **각 문서 헤더가 스스로 주장하는 값**(`이 파일은 **≤60줄**로 유지한다`).
  오늘은 셋이 일치하지만 **아무도 확인하지 않는다** — M19가 값을 치른 "복사본" 모양이다.
- Changed(가드 +14, `test_doc_budgets.py` 신규): 두 방향 — ①각 문서가 예산 안인가
  ②**세 선언이 서로 일치하는가**(한 곳만 고치면 red). 예산은 `harness-config.json`을
  단일 출처로 읽는다(스킬들이 이미 그걸 읽는다). **코드 변경 없음.**
- Verified: 변이 M1~M4 전부 red(STATUS 1줄 초과 · config 상향 · 표 변경 · 헤더 주장 변경).
  ⚠️**M5(비공허 검사 무력화)는 생존** — 앞과 같이 숨기지 않는다. 진짜 실패 모드를 따로 물었다:
  **예산을 통째로 비우면 2 failed**(`test_the_policy_table_has_no_extra_rows`가 잡는다) ⇒
  비공허 assert는 보호가 아니라 문서다. `make check` **2073 · 36.73s**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**내 가드가 자기 창을 물었다** — `_header_claim`이 앞 12줄만 봐서 `AGENT_BRIEF`의
  선언(23번째 줄, `▶ NEXT SESSION` 블록 뒤)을 "없음"으로 읽고 red를 냈다. **문서가 아니라 내
  윈도우에 대한 답이었다**(Risk 12④). 전체를 훑도록 고쳤다. 그리고 ⚠️**변이 무효가 오늘
  네 번째**(JSON을 깨뜨림) — 기준선 먼저 찍기가 매번 잡아 준다.

## 2026-08-15 — 렌즈의 마지막 층: "resolved"는 셋이 같은 뜻이었다. 우연히 그랬다 (gate 2059)

- Status: 렌즈를 한 층씩 내려 왔다(`AlarmContext`→`AnalyzerOutput`→`DecisionOutput`→게이트
  자신→의존성 선언). 마지막 층 `ExecutorOutput`을 물었다 — **필드는 셋이 글자 그대로 동일**하다.
  그래서 **값 축**으로 물었다: `resolved`는 계산되고 `resolved_at`·MTTR로 이어진다.
- Verified(**계산은 달랐다, 그런데 결함은 아니다**): aws는 `resolution_verdict(...).resolved`,
  gcp/azure는 `bool(executed) and not skipped` **하드코딩**. AWS 주석이 *"so both axes have one
  definition"*이라 쓰는데 **둘이 그 정의를 안 썼다**. ⚠️단 **오늘 동작은 같다** — 검증이 없으면
  계약이 정확히 그 규칙이고, **gcp/azure엔 verify 경로가 0건**이다(`git grep "verif"`).
  ⇒ M23의 `steps`와 같은 판정: **도달 불가 분기가 아니라 일관된 부재**.
- Changed(**동작 변경 0**): 그래도 계약으로 모았다 — `NEXT_PLAN` 유지 규약이 금지하는 모양
  (*"복사본 둘은 다음 고침이 한쪽에만 닿는 방식"*)이고, **계약 모듈은 이미 있었고 AWS는 이미
  읽고 있었다**. 값은 **미래 드리프트 제거**이고 그 대가는 M19가 이미 지불했다(67/81).
- Verified(가드 +13, `test_resolution_parity.py` 신규): **오늘의 답이 안 움직였는가**(5케이스) ·
  `verified`가 None(unknown)인가 · 셋 다 계약을 임포트하는가 · **하드코딩 사본이 다시 생기지
  않았는가** · 셋이 같은 답인가. 변이 **5건 red·생존 0**(기준선 108).
  `make check` **2059 · 32.35s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `resolved-meant-the-same-thing-by-accident.log`.
- Blockers: 없음.
- Next: ⚠️**변이 M4 첫 시도가 또 무효였다 — 오늘 세 번째**(함수 이름을 바꿔 `2 errors` 수집 실패).
  절차에 넣은 **기준선 먼저 찍기**가 잡았다. ⇒ **이름을 바꾸는 변이는 의미 변이가 아니라 문법
  변이다.** 그리고 **렌즈 결산**: 다섯 층에서 다섯 결함, **여섯째에서 멈췄다** — 마르는 지점을
  적어 두는 건 다음 세션이 같은 자리에 다시 대지 않게 하려는 것이다(증거 §5).

## 2026-08-15 — 08-08에 배운 교훈을 한 패키지에만 적용했다. 형제 여섯을 안 셌다 (gate 2046)

- Status: D49의 원인이 *"`except ImportError` 폴백이 원리상 도달 불가"*였다 — **그 패턴을
  일반화해** 물었다. `pyproject.toml`이 이미 그 교훈을 **한 패키지 분량으로** 적어 두고 있었다
  (08-08 opentelemetry: *"게이트가 선언되지 않은 패키지 위에서 통과하고 있었다"*). **형제를 안 셌다.**
- Verified(전수 스윕, AST + `git ls-files`): `try/except ImportError` 뒤 서드파티 임포트 13종 중
  **여섯이 어느 extra에도 없다** — `google-cloud-{firestore,logging,monitoring}` ·
  `azure-cosmos` · `azure-monitor-query` · **`openai`**(azure analyzer의 **LLM 자체**) ·
  `fastapi`/`uvicorn`(**`make dev-up`이 쓰는데 아무도 선언 안 했다**).
- Verified(**왜 조용한가**): 폴백이 전부 **에러가 아니라 warning**이다. 선언이 빠져도 설치가
  실패하지 않고 **팔다리 없는 에이전트가 배포된다** — `.[gcp]`는 로그·메트릭·스토어가 없고,
  `.[azure]`는 **LLM·스토어·로그가 없다**. `AGENT_BRIEF`가 광고하는 `make dev-up`은
  **새 클론에서 안 돈다**. CI도 못 잡는다(거기서도 조용히 폴백한다).
- Changed(**선언만**, 코드 무변경): gcp/azure extra 보강 + `serving` extra 신규. 폴백은 그대로
  유효하다 — 바뀐 건 *"설치하겠다고 말한 것을 실제로 설치한다"*뿐이다.
- Verified(가드 +19, `test_optional_dependencies_declared.py` 신규): **설치 상태가 아니라
  소스↔선언을 비교**한다("여기선 되는데"가 이걸 숨겼다). 방어선은
  **`test_no_guarded_import_is_unmapped`** — 소스에 새 optional 임포트가 생기면 red다.
  변이 5건 red. ⚠️**M6(비공허 검사 무력화)은 생존했고 숨기지 않는다** — 가드의 가드는 없다.
  대신 **진짜 실패 모드**를 따로 물어 red를 확인했다(스윕이 `{}` → 2 failed · stdlib 필터
  상실 → 1 failed). ⇒ **생존한 변이는 "가드가 없다"가 아니라 "무엇이 진짜 보호인지"를 묻게 한다.**
  `make check` **2046 · 38.81s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `six-optional-imports-nobody-declared.log`.
- Blockers: 없음.
- Next: ⚠️**설치해서 확인하지는 않았다** — 빈 환경에서 `pip install .[gcp]`를 돌려 정말 로그를
  못 읽는지는 **미검증**이고, 근거는 선언↔임포트 대조다. 이 머신엔 전이 의존으로 전부 깔려
  있어 증상이 안 보인다 — **바로 그게 이 결함이 오래 산 이유다.** 버전 하한도 관례로 골랐다.

