# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-30 — 같은 함정을 pytest에만 막아 뒀다: ruff는 실행마다 답이 달랐다 (gate 2302)

- Status: 위 증분이 **"미수정, 범위 밖"으로 기록만** 한 항목을 재서 닫았다. 증거
  `docs/evidence/ruff-and-pytest-did-not-exclude-the-same-vendored-trees.log`.
- Verified(**재현 — 같은 명령, 같은 트리, 다른 답**): `ruff check src/ tests/` 10회가
  **20 · 6527 · 20 · 6527 · 6527 · 6527 · 20 · 6527 · 6527 · 20**. 초과분 6,507건이 **전부
  `src/stacks/cdk.out`**(벤더 CDK 자산 4,703 py파일). 캐시를 지우면 첫 실행만 20이고 다시 흔들린다.
- Verified(**원인 = 선언이 아니라 추론**): 두 경로 다 gitignore인데 **pytest만 소리 내어 말했다**
  (`norecursedirs`). `[tool.ruff]`엔 대응 항목이 **없었다**. ⇒ **Risk 12②가 두 번째 도구에서
  재발**(선언되지 않은 것 위에서 통과)이자 **12⑥ 형제 집합의 설정 판** — 같은 함정을 한쪽에만
  막아 뒀다. ⚠️NEXT_PLAN은 **이미 `cdk.out`을 "세는 함정"으로 적어 뒀다**(MCP 항목): 같은
  디렉터리·같은 함정·다른 도구인데 기록이 도구 하나에만 적용돼 있었다.
- Changed: `[tool.ruff] extend-exclude`에 두 경로를 **선언**했다 → 10회 **전부 20**. ⚠️**게이트는
  아니다**(`check: test`) — 나쁜 건 CI가 아니라 `make lint`를 돌린 사람이 실행마다 다른 답을 받고,
  흔들리는 쪽이 **진짜 소견 20건을 벤더 6,507건 밑에 묻었다**는 것이다. **읽을 수 없는 신호는 읽지 않게 된다.**
- Verified(**묻혀 있던 20건 전수 분류 — 결함 0**): F841 8 · E731 5 · E701 5 · F402 1 · E712 1.
  "단언이 빠진 모양"인 **아홉 건을 개별로** 물었다. `azure_runner:275 url`=죽은 변수(분기마다 자기
  URL) · F402=그 함수가 dataclass `field`를 안 씀 · `test_pipeline original_guard`=지역 인스턴스라
  오염 없음 · `test_activity_writer result`=mock의 `put_item`을 단언한다. ⚠️**가장 그럴듯했던 건
  `pipeline.py:218 dep_id`** — `record_deployment()`가 돌려준 id를 버리고 **바로 다음 줄**에서
  ACTIVITY 행을 쓴다(08-18에 "쓸 수 있는데 안 쓴다"로 읽혔던 그 모양). 물어 보니
  **`record_agent_activity`에 `deployment_id` 매개변수가 아예 없다** ⇒ 08-18이 **읽는 쪽**에서
  내린 경계가 **쓰는 쪽에서 독립으로 재확인**됐다. **결함이 아니라 경계다** — 시험은 범위를 줄 때도 값이 있다.
- Changed(**가드 +3**): `test_vendored_paths_are_excluded_from_both_tools.py` — 형제 일치 · 공허
  방지 · **도구에 직접 묻기**(`ruff check --show-settings`). ⚠️**TOML 키는 오타가 나도 파싱된다**:
  `extend_exclude`(밑줄)로 쓰면 ruff가 파일을 받고 키를 **조용히 무시**한다 — 선언을 읽으면 누가
  타이핑했다가, resolved settings를 읽어야 **도구가 동의했다**가 증명된다.
- Verified(**변이 4종 red**): 제외 통째 삭제 · ruff만 한 경로 누락 · **키 오타**(세 번째 방향이
  사는 지점) · **양쪽 다 빈 목록**(형제 일치는 **통과**하고 공허 방지만 red — 그 칸을 메우는 게 요지).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13, 38.0s).
- Blockers: 없음. 20건은 **안 고쳤다**(스타일 · 열 파일 · 범위 밖) — 이제 **읽을 수 있으니**
  고칠지는 결정 사안이고, `make lint`를 게이트에 넣으려면 그게 선행이다.
- Next: **Azure executor 디스패치**(승인 사안) — 그 전에 기록된 근거 *"순수 잠재: 구독에 리소스 없음"*(08-16)을 재는 게 값싸다.

## 2026-08-30 — 4a 마지막 칸: 청구액은 $0.00이었고, 프리티어를 배제한 근거의 전건이 거짓이었다 (gate 2299)

- Status: 13일간 세 진입점이 가리켜 온 마지막 미측정 항목("08-19 이후 AMP 실제 청구액")을 실행했다.
  **PR #44**(Phase DoD 전수 검증)는 CI 초록 확인 후 squash 병합(`4fb4185`). 권위는 계획서 **§10**과
  `docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.
- Verified(**$0.00이고, "목록에 없어서 0"이 아니다**): CE를 **크레딧 제외 필터**로 물으니 AMP는
  08-17부터 **13일 전부 그룹이 존재**하고 금액만 0. `RECORD_TYPE`으로 가르니 **`Credit` 행이 없다**
  — 상쇄가 아니라 **Usage 행 자체가 $0**이다. 계량 **798,331 샘플**·0.0005 GB-Mo·쿼리 920.
  ⚠️계량되고 0인 것과 계량조차 안 된 것은 다른 사실이다.
- Changed(**사유 — 기록의 전건이 거짓이었다**): `aws freetier get-free-tier-usage`가 AMP 행 셋을
  전부 **`freeTierType: "Always Free"`**(40M/월 · 10GB · 200B)로 답한다. §3과 D50은 *"12개월
  한정**이면** 안 붙는다"*는 **조건문**을 세우고 전건을 참이라 가정했다. ⚠️**틀린 기록이 아니다** —
  추론임을 명시했고 **무엇이 확정할지 지목했다**(*"AMP를 켠 뒤 첫 청구서"*). 다만 답은 **이미 그
  계정 데이터 안에 있었다**: 당시 12건이 **전부 "Always Free"**였고 "12 Month Free 0건"은 "창을
  지났다"로도 **"이 계정 프리티어 행은 원래 그 종류뿐"**으로도 읽힌다 — 같은 데이터가 두 결론을
  지탱했고 **비싼 쪽을 골랐다**(보수적이라 안전했다). §3에 정정 박스, §10 신설.
- Verified(**교차 확인 2.4%**): AMP에 직접 물어 잰 실가동 **41.3 수집-시간** × 설계 부하 19,800/h
  = **817,740** vs AWS 계량 **798,331** — 파이프 모델과 청구 계량이 서로를 확인한다.
- Verified(**허용목록 유출 0**): 전체 창에서 workspace가 아는 메트릭 이름이 **정확히 4개**, 시계열은
  **08-17T08:00Z·08-27T12:00Z 두 시점 모두 308**(22/50/220/16 — §2의 네 칸 그대로).
- Verified(**⚠️두 번째 발견 — 파이프는 연속이 아니고 지금 죽어 있다**): 13일 중 **4일만**(11.1h ·
  10.0h · 3.6h · 16.7h), 마지막 샘플 **08-27T19:55Z** — 로컬 **kind**가 Docker와 함께 뜬다(오늘
  `docker info` 실패). duty cycle **13%** ⇒ **$1.42는 720h 연속 가동 가정**이라 이 환경에선 원리상
  안 난다(프리티어가 없었어도 **$0.07**). **가정이 지배하는 추정은 그 가정이다** — 08-15엔 시계열 수, 오늘은 **가동 시간**에서 재성립.
- Changed(**가드 +8**): `test_amp_bill_claims.py`(+6) — 진입점이 **$1.42를 정정 없이 다시 적으면**
  red(±3줄 근접). ⚠️**첫 판은 하중이 없었다**: 문서 단위로 마커를 찾아 한번 고쳐진 문서엔 다시
  red가 안 났다(Risk 12③ 그 모양) → **근접 창으로 바꿨다.** `test_evidence_pointers_resolve.py`(+2)
  — 인용된 `docs/evidence/*.log` 실재 스윕(**측정 후 작성**: 68건·dangling 0). `test_amp_cost_handles.py`는
  계약 그대로 두고 **금액을 한도 대비로** 고쳤다 — 절벽이 40M 한도로 옮겼을 뿐 필터 없음은 **128배 초과**.
- Verified(**변이 7종 전부 red**, 변이·실행·복구 한 스크립트 + 디스크 백업): BRIEF에 정정 없는
  $1.42 삽입 · 세 진입점에서 측정 결과 제거 · 증거 로그 삭제 · §10 제목 변경 · 한도 40M 제거 ·
  인용 정규식 무력화(공허 통과 방지) · 없는 증거 로그 인용. 복구 후 8 passed, 워킹트리 깨끗.
- Verified: `make check` **2299 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13, 36.4s).
  ⚠️**새 가드가 그 자리에서 일했다** — BRIEF를 아직 안 고친 채 처음 돌리자 정확히 그 주장을 red로 잡았다.
- Observed: `make lint`가 실행마다 **20 ↔ 6,527**을 오간다(⛔같은 날 아래 증분이 재서 닫았다).
- Blockers: 없음. ⚠️측정 비용 = CE 2회 $0.02 · 창 전체에서 **CE $0.17이 이 계정 최대 항목**(2위
  EC2-Other $0.0462) — **"무엇이 도는가"를 묻는 게 도는 것보다 비싸다.**
- Next: **Azure executor 디스패치**(승인 사안) — 고치면 **Phase 3② 면제도 같이 지울 것**.

## 2026-08-18 — Phase DoD 전수 검증: Phase 0의 ts 절반과 Phase 3②의 배선이 비어 있었다 (gate 2285)

- Status: 지시 "최대한 많은 phase 검증". 권위는 설계 계획서 §Phases의 **DoD 문장 그 자체**로
  두고, 각 절을 그것을 단언하는 테스트에 맞댔다. 전체 판정표는 증거 로그가 권위.
  `docs/evidence/phase-dod-verification-2026-08-18.log`.
- Verified(**0·1a·2·5 성립**): 1a는 DoD 세 절이 이름 붙은 테스트로 있고 ⚠️**형제를 세는 가드까지
  있다**(`test_every_provider_branch_is_covered_by_the_test_above`) · 2는 `applicable=false`를
  **돈 쓰기 전에** faked 디스크립터로 실증 · 5는 "diff가 단 한 줄 추가"·"관계없는 dirt는 dirty인
  채로"까지 단언한다.
- Changed(**Phase 0 — ts 절반은 아무도 안 물었다**, 가드 +6): DoD가 "로더·타입 검증 **(py/ts)**"인데
  TS를 읽는 테스트가 **0개**였다(같은 기법을 쓰는 파일이 이미 **15개**인데 이 쌍만 빠졌다).
  먼저 "TS가 두 번째 로더인가"를 물었고 **아니었다** — 그 파일이 스스로 *"Deliberately NOT a YAML
  reader"*라 적는다. 그래도 **계약은 네트워크를 건넌다**(`to_dict()` → `interface`). 실측: 필드 9·
  Sync 4값·Health 5값이 **정확히 일치**한다. ⇒ 결함이 아니라 **집행 부재**이고, TS가 두 축을
  **union literal**로 적기 때문에 실패가 날카롭다: py에 값을 하나 더하면(M37이 `n/a`로 실제로 한
  변경) 대시보드 타입이 "존재할 수 없다"는 값이 도착하는데 **`tsc`는 계속 초록**이다(Risk 7).
- Verified(**변이 5종 전부 red**): py enum 값 추가 · ts union에서 `n/a` 제거 · py `to_dict`에 새 키 ·
  ts interface에서 `applicable` 제거 · **interface 이름을 바꿔 파서 무력화**(공허 통과 방지가 산다).
  복구 후 초록, 워킹트리 깨끗.
- Verified(**Phase 3② — 구현은 있고 묻는 쪽이 하나뿐이다**, 미수정·승인 사안): `guard_rollback`을
  부르는 러너는 **`onprem_runner` 하나**인데 `ROLLBACK_ACTIONS`는 **네 provider 7종을 다 안다**.
  ⚠️**M31이 고친 건 목록이고, 호출 지점을 세는 가드는 없다** — M18 계열이 한 층 위에서 재발했다
  (세는 대상이 액션이 아니라 **러너**였다). 건너뛸 근거 둘을 다 물었고 **둘 다 성립하지 않는다**:
  gcp/azure 러너는 롤백 직전 **매니페스트를 이미 GET한다**(배선 비용 = 추가 호출 0) · 레지스트리가
  kind/k3s만 선언한 건 그 모듈이 **"소유권은 라이브 마커에서 읽는다"**고 명시하므로 근거가 아니다.
  ⛔안 고쳤다 → **승인받아 GCP만 배선했다**: 롤백 walk가 이미 GET하던 매니페스트를 그대로
  넘긴다(**추가 호출 0**), 거부는 `patch` 앞이다. Azure는 `JUSTIFIED_GAPS`(러너를 안 부르니
  하중이 없다 — 그 항목이 닫히면 **면제를 지우라고 가드가 red를 낸다**), AWS는 **러너가 없다**
  (SSM 경로 — 그 사실을 가드에 박았다). ⚠️**가드가 한 번 틀렸다**: 문자열 검사라 **호출을 지워도
  import 줄이 남아 통과**했다 → **AST로 실제 호출**을 센다(같은 변이가 1건→**2건 red**).
- Verified(**Phase 1b는 정적만**): flux는 134줄 실구현, 두 어댑터가 `wave`를 각자 시맨틱으로 렌더.
  라이브는 **오늘 재현 불가** — Docker 데몬 down(kind), k3s `k8s-lab`은 살아 있으나 **네임스페이스가
  기본 4개뿐**(flux·워크로드 없음). `STATUS` Risk 5의 "여는 조건: k3s-lab에 워크로드"를 **측정이
  확인**했다. ⚠️"한때 통과했다"와 "지금 재현된다"는 다르며 이 기록은 후자만 주장하지 않는다.
- Verified: `make check` **2291 passed, 2 skipped**(2026-08-18 로컬 macOS·py3.13, 37.4s) — 가드 **+12**.
  ⚠️게이트가 스스로를 잡았다 — `test_gate_number_claims`가 **진입점 셋이 다 같은 숫자를 말할 때까지**
  red였다(brief·STATUS만 고치고 NEXT_PLAN을 빠뜨리자 그 자리에서 실패).
- Blockers: 없음. Phase 1b 라이브는 **정적 검증으로 남기기로 결정**(Docker down · k3s-lab 비어 있음).
- Next: 08-19 이후 AMP 청구액 대조 · Azure executor 디스패치를 고치면 **Phase 3② 면제도 함께 지울 것**.
