# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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
- Next: ⚠️**Risk 12⑤를 내가 재현했다** — 변이 하네스가 10분 타임아웃에 잘려 `finally`가 못 돌아
  `base.py`가 변이 상태로 남았다. `git checkout --`은 피했는데 **프로세스가 죽으면 메모리도
  같이 죽는다**를 안 봤다. ⇒ **복구는 프로세스 밖에도 있어야 한다**(원문을 디스크에 먼저
  떨구거나 변이를 한 번에 하나로). 남은 자리: **`triggered_at`은 여전히 AWS만 저장**한다.

## 2026-08-15 — 4a를 "비용 최소화"로 승인하고 그 비용을 처음 쟀더니, 전제가 100배 틀렸다 (코드 변경 없음)

- Status: 사용자가 **비용 근거로 4a를 승인**했다(≈$5/월, 4b의 1/40). 승인이 났으니 계획서가
  스스로 적어 둔 *"승인 전 재확인할 것"*을 수행했다. **재확인해야 했던 건 정가가 아니라
  그 옆 칸의 가정이었다.**
- Verified(실측 2회, 재현): `kind-platform-agent`에 직접 물었다 — **52,275→52,438 시계열**,
  **1,979.7→1,981.0 samples/sec** = **월 5.13 B 샘플**. 역산 스크랩 간격 26.4초로 차트
  기본 30초와 일치(두 측정이 서로를 교차검증). §4 가정 "랩 규모 수백 시계열"의 **약 100배**.
- Verified(가격): AMP 정가 $0.90/1천만 샘플은 **맞았다**(AWS 자체 예시 892.8M→$80.93로 교차
  확인). ⚠️**2B 초과 요율은 페이지에 표가 없어 미확인** → 총액은 **하한**이다.
  프리티어(40M)는 **기대지 않는다**: `aws freetier get-free-tier-usage`가 이 계정에서
  "Always Free" 12건 · **"12 Month Free" 0건** → 첫 12개월 창을 지났다.
- Verified(허용목록 견적): job별 분해에서 **apiserver+kubelet이 67%**. 데모 룰이 쓰는 메트릭은
  `kube_pod_container_status_restarts_total` **하나(50 시계열)**. 후보별 월비용@60s —
  A+D(72개) **$0.28** · C(2,671) $10.39 · **E=kube-state-metrics 전부(4,188) $16.28** ·
  **필터 없음(52,361) ≥$180**. ⚠️**필터 없는 4a는 4b($185)보다 비싸다** = 승인 근거가 소멸한다.
- Changed(문서만): 증거 `4a-cost-assumed-a-hundredth-of-the-cluster.log` 신규 ·
  계획서 §4·§5·§7 정정(**틀린 표는 남겨 두고 정정 박스를 얹었다**) · 진입점 3곳의 "≈$5/월".
  **코드·게이트 무관**(1912 그대로, 안 돌렸다).
- Blockers: 없음. **단 4a 착수 전 결정이 하나 생겼다** — `write_relabel_configs` 허용목록.
  승인받은 $5는 **60초 간격에서 약 1,285 시계열**(전체의 2.5%)을 산다.
- Next: **추정표는 어느 칸이 측정이고 어느 칸이 가정인지 표시할 것.** 총액을 지배한 건
  가정 쪽이었다. ⚠️그리고 **권위 문서가 틀리면 복제본이 그걸 사실로 굳힌다** — 진입점
  3곳이 "$5"를 복제해 승인까지 갔다. **복제 금지 규약이 겨냥한 실패가 실제로 일어났다.**

## 2026-08-15 — 직전 고침이 남긴 기준을 다음 계약에 댔더니, 형제 집합이 다섯 번째로 걸렸다 (gate 1894→1912)

- Status: M19의 결론(**판단 기준은 읽는 쪽의 provider 간 비대칭**)을 `NormalizedIncident`에
  그대로 적용했다. `severity_hint`는 **네 시그널 어댑터가 전부 채우는데**(Azure
  `essentials.severity` · GCP `incident.severity` · onprem 라벨 · AWS 알람 상태) **읽는 곳은
  `aws/analyzer.py:200` 하나**였다.
- Verified(⚠️**레포가 스스로 적어 뒀는데 가드가 안 지켰다**): `test_analyzer_prompt_evidence.py`
  도크스트링이 **네 어댑터를 정확히 열거**하고 *"severity가 AUTO냐 APPROVE냐를 정한다 —
  07-29 라이브 관측: `warning` 규칙이 P1으로 등급 매겨져 즉시 조치됐다"*라고 쓴다. 그런데
  그 파일의 임포트는 **`aws.analyzer` 한 줄**이다 → **산문이 참이어도 임포트 줄이 범위다.**
- Verified(재현): 실제 `_build_prompt` — aws는 severity·alert detail 둘 다 YES,
  **gcp/azure는 둘 다 NO**. 두 정규화 블록은 **AWS의 고치기 전 다섯 줄과 글자 그대로 같다**.
  onprem은 `onprem_incident_pipeline.py:34`가 AWS analyzer를 임포트해 **이미 덮인다**.
- Changed: 프롬프트 두 줄 + **시스템 프롬프트 안전장치**("강한 증거지만 **구속력은 없다**")를
  같이 이식. ⚠️**안전장치 없이 라벨만 넣으면 구멍보다 나쁘다** — 라벨이 지시로 읽혀
  AUTO/APPROVE를 혼자 정한다. 어휘 → P1/P2/P3 **매핑은 안 한다**(정책, AWS도 안 했다).
- Changed(가드 +18): 기존 파일을 세 analyzer로 parametrize — 이식 전 **16 red**, **AWS 11은
  내내 초록**. 역방향 둘(힌트 없으면 줄 안 붙임 · 시스템 프롬프트가 "not binding"을 말함).
  onprem을 목록에서 뺀 이유를 **코드에 적었다**(빠진 것과 덮인 것은 구별돼야 한다).
- Verified: 변이 **6건 전부 red·생존 0**(무조건 붙이기 · 안전장치 제거 · 어휘 정규화 포함),
  복구 후 0 modified. `make check` **1912**(+18) · CI도 **1912** — 일치. 2026-08-15,
  로컬 macOS·py3.13. 증거 `operator-severity-never-reached-two-models.log`. PR #37.
- Blockers: 없음.
- Next: **"무과금 소진"이 일곱 번째로 틀렸고, 이번엔 목록 밖이 아니라 목록이 만든 기준에서
  나왔다.** 다음 수도 같은 자리에 있다 — **가드 파일의 임포트를 그 파일이 주장하는 범위와
  맞대 볼 것**(`observations`·`triggered_at`도 AWS만 읽는다).

## 2026-08-15 — 틀린 기록을 시험하러 갔더니, 옆에서 AWS가 이미 닫은 결함이 두 provider에 살아 있었다 (gate 1862→1894)

- Status: 먼저 **직전 세션의 문서 체크포인트가 커밋 안 된 채** 트리에 있었다(코드는
  `main`, 진입점 문서는 로컬만) → PR #33으로 닫았다. 그다음 `NEXT_PLAN`의 열린 항목
  **ⓑ**("`renew_certificate`가 GCP/Azure 어댑터에 매핑 없음")를 시험했다.
- Verified(**ⓑ는 틀렸다 — stale이 아니라 쓰일 때부터**): 읽지 말고 돌려서 쟀더니
  **네 provider 전부** 풀린다(`actions=[]` 없음). `git log -L`로 매핑은 **2026-07-09**부터
  있었다 — 그 기록이 쓰인 08-14 커밋보다 **한 달 앞선다**.
- Verified(**그 자리에 있던 진짜 결함**): 티어 2가 런북의 `resource_types`를 **안 읽는다**.
  AWS는 `_fits_resource`로 **이미 닫아 뒀고**, 어긋난 쌍 **67/81**이 GCP/Azure에선 그대로
  선택된다. ⚠️**AWS보다 조용하다** — AWS는 하드코딩 액션으로 폴백(시끄러움), GCP/Azure는
  풀리지 않는 capability를 **버리고 짧아진 목록**을 준다 → `certificate-expiry`가
  kubernetes-workload에 선택되고 **RTO 600을 달고 notify만 한다**.
- Changed: 규칙을 `runbooks/schema.py::fits_resource` **한 곳**에 두고 세 provider가 읽는다
  (AWS는 위임). 복사본을 안 늘린 건 `NEXT_PLAN` 유지 규약이 **이 티어를 예로** 적어 둔 그대로다.
  "양쪽 unknown이면 배제 안 함"은 AWS의 결정을 **옮긴 것**(발명 아님).
- Changed(가드 +32): ground truth를 **함수가 아니라 카탈로그가 선언한 데이터**에 댔다.
  전수 스윕(9타입 × 전 런북 × 2 provider) + 역방향 셋(선언한 타입은 뽑힌다 · unknown은
  아무것도 배제 안 한다 · **폴백은 게이팅 안 된다** — AWS엔 있고 여기엔 없던 짝).
  ⚠️**기존 테스트 2건이 red가 됐고 옳았다**: 픽스처가 모든 런북을 **k8s인 척** 물었다.
- Verified: 변이 **6건 전부 red·생존 0**, 복구 후 63 초록·0 modified. `make check`
  **1894**(+32) · CI도 **1894** — 로컬↔CI 일치. 2026-08-15, 로컬 macOS·py3.13.
  증거 `resource-types-declared-and-unread.log`. PR #33·#34.
- Blockers: 없음.
- Next: ⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다.** 계약 필드 일곱을 훑어 보니
  **`provider`도 아무도 안 읽는데** 빌트인 9개가 **전부 `"aws"`**라, 읽기 시작하면 GCP/Azure는
  **전부 `generic-recovery`로 떨어진다**(=#30 이전 상태). 판단 기준은 **읽는 쪽의 비대칭**이지
  선언의 고아 상태가 아니다. 남은 무과금은 ⓐ·ⓒ(정책) · `slack_live_approval`(Slack 데모 선행).

