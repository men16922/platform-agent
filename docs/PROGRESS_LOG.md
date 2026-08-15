# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-15 — 파괴 액션 하나가 두 클라우드에선 APPROVE였고 세 번째에선 AUTO였다 (gate 1942→2021)

- Status: 렌즈를 또 한 층 아래(`DecisionOutput`)로. **먼저 나온 건 범위였다** — `steps`·
  `reconciliation`은 AWS만 채우고 AWS만 읽는데, 공유 executor에도 gcp/azure executor에도
  **steps 처리 코드가 아예 없다** → 도달 불가 분기가 아니라 **일관된 부재**(AWS 전용 기능).
- Verified(**가장 위험한 필드를 열었더니 나왔다**): `remediation_mode`의 severity 매핑은 셋 다
  동일한데 **안전 오버라이드가 다르다** — gcp·azure는 `{Delete,Drop,Terminate,Destroy}` **4개**,
  **aws만 인라인 3개**로 **`Destroy`가 빠졌다**. 실행 확인: `DestroyCluster` P1 →
  **aws=AUTO · gcp/azure=APPROVE**. `Severity` 정의대로 **AUTO = 사람 없이 실행**이다.
  `AGENT_BRIEF` 가드레일 문구("Delete/Drop/Terminate 강제 APPROVE")는 **AWS 그대로였고 나머지
  둘은 이미 그것을 넘어 자라 있었다** — **뒤처진 쪽이 하필 파괴 경로**다.
- Verified(도달 가능성, 정직하게): 빌트인 카탈로그는 전부 `AWS-PascalCase` 12종이고
  `Destroy` 계열이 **없다** → 오늘은 도달 불가. **그러나 런북은 운영자가 등록한다**
  (`schema.py` 도크스트링 · 스캔 티어가 그 테이블을 읽는다) → `AWS-DestroyStack`은
  **운영자가 만드는 이름**이고 그게 이 갭이 열리는 자리다. **가설이 아니라 이미 어긋난 세 구현.**
  ⚠️**소문자는 안 고쳤다**(`destroy-stack`은 셋 다 AUTO) — 네 실행 어댑터 전부
  `PROVIDER-PascalCase`만 낸다(4×~29 매핑 전수). **아무도 만들지 않는 형태의 가드는 하중을
  못 받는다.** 대신 **그 전제를 가드로 고정**했다.
- Changed: `runbooks/schema.py`에 `DESTRUCTIVE_ACTION_PATTERNS` + `is_destructive_action()`
  한 벌, 세 decision이 읽는다(M19의 `fits_resource`와 같은 자리·같은 이유). **발명 아님** —
  4번째 동사는 GCP·Azure가 이미 쓰던 것이다. ⚠️네 번째 사본도 있다:
  `deploy-policy.yaml:42`(소문자, **다른 서브시스템**) — 정본 의도가 4개임을 보여 준다.
- Verified(가드 +79, `test_destructive_action_gate.py` 신규): 4동사×3provider×3severity 전수 ·
  역방향(**상시 발화 게이트는 게이트가 아니다**) · 셋이 같은 답인가 · 사본 0인가 ·
  **대소문자 결정의 전제**(어댑터가 PascalCase를 내는가). 변이 **8건 red·생존 0**.
  `make check` **2021**(+79), 2026-08-15, 로컬 macOS·py3.13.
  증거 `destroy-was-approve-on-two-clouds-and-auto-on-the-third.log`.
- Blockers: 없음.
- Next: ⚠️**내 가드가 `cdk.out` 함정을 밟았다** — `rglob`로 "누가 정의하나"를 세니 untracked
  빌드 사본 22건이 잡혀 red. 레포가 적어 둔 **`git grep`을 쓸 것** 그대로다. **더 나쁜 건
  M21의 같은 가드도 같은 결함이었고 상수가 새것이라 우연히 초록이었다** — 다음 `cdk synth`에
  red였을 것이다. 둘 다 `git ls-files` 기반으로 고쳤다. ⇒ **"누가 정의하나"를 파일시스템에
  묻지 말 것.** 그리고 ⚠️**열린 항목 하나**: `test_gcp_day2_operations.py`가 **200초**로
  게이트 288초의 대부분이다(Azure 대응 파일은 **0.43초**, 같은 28건) — **형제 중 하나만 느리다.**

