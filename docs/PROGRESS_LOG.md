# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-15 — 승인자에게 "과거 유사 인시던트"라고 보여 준 다섯 건은 랜덤 ID 사전순 최대였다 (gate 1929→1942)

- Status: M21이 `AlarmContext`를 닫았으니 **같은 렌즈를 한 층 아래**(`AnalyzerOutput`)에 댔다.
  `similar_incidents`는 셋 다 채우는데 **시그니처가 달랐다** — AWS만 `severity`를 받고
  **본문에서 안 읽는다**. 그걸 보러 갔다가 **정렬 축이 다르다**는 것을 봤다.
- Verified(**주석이 거짓이었다**): aws는 `ScanIndexForward=False, Limit=5` + 주석 *"most recent
  first"*. 정렬 키가 **`incident_id`**(`incident_agent_stack.ts:30`) = **`INC-<랜덤 hex>`**
  (`executor.py:62`) → **16진수 사전 역순, 시간 무관.** GCP·Azure는 `created_at` 정렬 — **옳았다.**
- Verified(재현, 시드 고정): 한 alarm 12건에서 **최신 5와 겹치는 건 2/5**. ⚠️**"랜덤"보다 나쁘다 —
  안정적이다**: 새 건이 들어갈 확률이 **`5/N`으로 떨어져 이력이 쌓일수록 목록이 얼어붙는다**.
  읽는 사람이 듣는 것("최근")의 정반대다.
- Verified(**읽는 쪽은 사람이다**): `executor.py:458` Slack 승인 메시지 — **무인 조치를 승인할지
  판단하는 사람**이 "선례"로 읽는다. 오류도 빈 목록도 아니라 **조용히 실패한다.**
- Changed: `created_at`은 **이미 모든 행에 있었다** — 없던 건 데이터가 아니라 **그걸로 정렬하는
  코드**다. 서버 측 `Limit=5`(임의의 5건을 먼저 자른다)를 빼고 파티션 페이징
  (`_SIMILAR_SCAN_CAP=500`, 걸리면 **로그로 말한다**) → `created_at` 역순 5건. **발명 아님**:
  정렬 축은 GCP·Azure가 이미 쓰던 것이다. `severity`는 **의미를 주지 않고 제거**했다.
- Verified(가드 +13, `test_similar_incidents_recency.py` 신규): 옛 동작을 **결함으로 고정** ·
  `ScanIndexForward`를 **아예 안 묻는가** · 페이징 · 캡이 시끄러운가 · **세 시그니처 일치** ·
  **이미 옳던 둘이 뒤집히지 않는가**. 변이 **7건 red·생존 0**. ⚠️**M5 첫 시도는 무효였다** —
  red였지만 **내 변이가 문법을 깬 것**(`1 error in 0.06s`)이라 `if False:`로 의미만 바꿔 다시
  물었다. **red의 이유를 안 보면 변이는 자기기만이 된다.** `make check` **1942**(+13),
  2026-08-15, 로컬 macOS·py3.13. 증거 `similar-incidents-were-sorted-by-random-id.log`.
- Blockers: 없음.
- Next: **직전 교훈이 값을 했다** — 변이 원문을 **디스크에 먼저 백업**해 복구가 프로세스보다
  오래 살게 했고 `diff -q`로 바이트 동일을 확인했다 ⇒ **복구 수단은 복구가 필요한 상황보다
  오래 살아야 한다.** 렌즈는 아직 안 말랐다 — **한 층 내려갈 때마다 나온다**
  (AlarmContext → AnalyzerOutput). 다음은 `DecisionOutput`.

## 2026-08-15 — 레포는 GCP/Azure의 정답을 이미 갖고 있었다. 한쪽 진입 경로에만 있었다 (gate 1912→1929)

- Status: `▶ NEXT SESSION`이 가리킨 `observations`를 물었더니 **이미 닫혀 있었다**(M20).
  **그 옆 detector 층에 진짜가 있었다** — 08-15에 이걸로 두 번째다(적힌 항목이 틀려도 값이 난다).
- Verified(**산문이 참인데 범위가 달랐다**): `aws/detector.py::_incident_reason`의 도크스트링이
  *"Provider-neutral by construction"*이라 쓰고 **GCP `policy_name`/`condition_name`·Azure
  `alert_rule`을 이름으로 부른다.** 전수로 세니 **호출자 하나(`aws/detector.py:133`) · 테스트 0개**.
  GCP/Azure는 각각 `summary`/`description` **한 키**로 때웠다.
- Verified(⚠️**더 날카로운 것 — 형제가 provider가 아니라 진입점이었다**): `aws/detector.py:79`의
  `_synthetic_alarm`이 **non-AWS 이벤트에 대해 이미 맞게** 하고 있었다. 즉 같은 GCP 알림이
  **AWS 통합 핸들러로 오면 풍부, 네이티브 GCP 핸들러로 오면 얇은** reason을 받았다.
  **결함은 "안 읽었다"가 아니라 "정답을 한쪽 경로에만 뒀다"이다.**
- Verified(**읽는 쪽까지 갔다**): GCP/Azure엔 AWS에 **없는** 소비자 `_fallback_analysis`가 있고
  `reason`의 낱말로 등급을 정한다. 규칙명 `"checkout service outage"` + 중립 summary로 재현 →
  **P3(사람 승인) ↔ P1(자동 실행)이 뒤집힌다.** M20의 `severity_hint`와 **같은 축·같은 두 provider**.
  ⚠️첫 시도는 안 뒤집혔다 — `signal_type=="reliability"` 분기가 먼저 걸려 낱말 축에 **도달을 안 했다**.
- Changed: 규칙을 `adapters/base.py::incident_reason` **한 벌**로 옮기고 세 detector가 읽는다
  (AWS는 위임). M19의 `runbooks/schema.py::fits_resource`와 같은 선례. **낱말→P1/P2 매핑은
  안 건드렸다**(정책) — 규칙 이름을 reason에 넣은 것은 AWS의 결정을 **옮긴 것**이다.
- Verified(가드 +17, `test_incident_reason_parity.py` 신규): 두 진입 경로 일치 · **읽는 쪽에 대고**
  등급 물음 · 역방향 셋 · **`_RULE_NAME_KEYS` 정의 모듈이 정확히 하나인가**. 변이 **7건 전부
  red·생존 0**(물은 대상 = 신규 + **변경 모듈을 임포트하는 테스트 13개**, `git grep -l`로 산출).
  `make check` **1929**(+17), 2026-08-15, 로컬 macOS·py3.13. 증거
  `incident-reason-two-entry-points-disagreed.log`.
- Blockers: 없음.
- Next(⚠️**Risk 12⑤ 재현**): 변이 하네스가 10분 타임아웃에 잘려 `finally`가 못 돌아 `base.py`가
  변이로 남았다 — `git checkout --`은 피했는데 **프로세스가 죽으면 메모리도 죽는다**를 안 봤다
  ⇒ **복구는 프로세스 밖에도**. **스윕도 닫았다(직전 줄이 틀렸다)**: `AlarmContext` 8필드를 읽는
  쪽까지 세니 **`reason`만 닿았고 일곱은 범위** — ⛔`triggered_at`(AWS 역경로 하나) ⛔`metric_name`
  (빌트인이 AWS 모양이라 살려도 폴백). **더 큰 사실이 덮는 차이는 고쳐도 관측되지 않는다.** 증거 §8.

