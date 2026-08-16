# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-15 — "느린 테스트"를 열었더니 게이트가 테스트마다 Gemini를 과금 호출하고 있었다 (288s→39s)

- Status: M23의 변이 범위를 정하려고 파일별 시간을 쟀다 — **결함을 찾을 생각이 아니었다.**
  형제 둘이 같은 28건을 도는데 `test_gcp_day2_operations` **200.66s** vs
  `test_azure_day2_operations` **0.43s**(466배). 28건이 **균일하게** 13~23초 = 공통 호출이다.
- Verified(**원인**): `gcp/analyzer.py::_analyse`가 함수 안에서 `import vertexai`를 하는데
  **패키지가 설치돼 있어 `except ImportError` 폴백이 원리상 도달 불가**다. 격리 재현에서
  실제 HTTP가 잡혔다 — `gemini-2.5-flash:generateContent` **→ 200**. **게이트가 테스트마다
  Gemini 추론을 사고 있었다.** ⚠️**D45 위반**(*"게이트는 라이브 클라우드에 의존하지 않는다"*) —
  결정은 있었고 **집행이 없어 참이기를 그만뒀다**. `STATUS` Risk 4의 "Vertex ~₩48K/월" 일부다.
- Verified(⚠️**더 나쁜 절반**): 자격증명만 숨기고 같은 테스트 → **16.55s(라이브) vs 0.90s(폴백),
  둘 다 통과**. 단언은 모델을 필요로 한 적이 없고, **머신에 무엇이 인증됐느냐로 코드 경로가
  갈렸다**(Risk 12②) — **양쪽 다 초록이라 안 보였다**. Azure도 **같은 구멍**이고 Azure
  자격증명이 없어서 안 보였을 뿐이다(AWS만 제대로 모킹해 0.22초).
- Changed: provider별 모킹이 아니라 **스위트의 성질**로 — `tests/conftest.py`(신규)가 세션
  autouse로 **외부 egress 차단**(`connect`+`connect_ex` 둘 다 · 루프백 허용 · 에러가 목적지와
  D45를 말한다). **프로덕션 코드 무변경** — 각 모듈이 이미 가진 폴백이 결정적으로 걸리게 했다.
  **D49**로 기록.
- Verified: 대상 파일 **200.66s→1.42s**, 전체 게이트 **288.56s→38.69s**(2021 passed 동일).
  ⚠️**차단으로 깨진 테스트 0건 = D45는 내내 만족 가능했다.** 가드 +6
  (`test_gate_has_no_network.py`: 차단 발화 · `connect_ex`도 · 에러 내용 · **루프백 생존** ·
  `_analyse`가 폴백을 타는가 · **폴백이 조용히 비어 있지 않은가**). 변이 **5건 red·생존 0**.
  `make check` **2027 / 39.75s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `the-gate-was-paying-for-gemini-once-per-test.log`.
- Blockers: 없음.
- Next: ⚠️**변이 첫 판이 무효였다** — 5건 전부 "RED"였는데 출력이 `no tests ran in 0.00s`였다.
  범위에 **없는 파일 이름**을 적어 pytest가 수집에서 죽었고 하네스가 종료코드만 보고 red로 셌다.
  M22가 남긴 *"red의 이유를 안 보면 변이는 자기기만이 된다"* 덕에 잡았다. ⇒ **변이 하네스는
  기준선을 먼저 찍고 "몇 건이 죽었는지"까지 볼 것** — 종료코드는 수집 실패와 가드 발화를 못 가린다.

