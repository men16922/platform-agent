# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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
  ⛔안 고쳤다 — 배선하면 **지금 성공하는 롤백이 거부**된다(fail-closed지만 동작 변경).
- Verified(**Phase 1b는 정적만**): flux는 134줄 실구현, 두 어댑터가 `wave`를 각자 시맨틱으로 렌더.
  라이브는 **오늘 재현 불가** — Docker 데몬 down(kind), k3s `k8s-lab`은 살아 있으나 **네임스페이스가
  기본 4개뿐**(flux·워크로드 없음). `STATUS` Risk 5의 "여는 조건: k3s-lab에 워크로드"를 **측정이
  확인**했다. ⚠️"한때 통과했다"와 "지금 재현된다"는 다르며 이 기록은 후자만 주장하지 않는다.
- Verified: `make check` **2285 passed, 2 skipped**(2026-08-18 로컬 macOS·py3.13, 37.0s).
  ⚠️게이트가 스스로를 잡았다 — `test_gate_number_claims`가 **진입점 셋이 다 같은 숫자를 말할 때까지**
  red였다(brief·STATUS만 고치고 NEXT_PLAN을 빠뜨리자 그 자리에서 실패).
- Blockers: 없음. ⛔**승인 대기 하나**: Phase 3② 배선(remediation 동작 변경).
- Next: 08-19 이후 AMP 청구액 대조 · Phase 3② 배선 여부 결정.


## 2026-08-18 — `cost_metrics` 잔여: 기록된 이유가 맞았고, 면제는 목록이 아니라 경계였다 (gate 2279)

- Status: 08-19 전까지 AMP 청구액은 원리상 못 잰다. 그래서 잔여 목록의 **`cost_metrics`**
  (*"`deployment_id`가 없어 렌더하는 뷰에 안 닿는다", 08-08*)를 규율대로 시험했다.
  **PR #43**(3커밋, capability 스캔 셋)은 CI 초록 확인 후 squash 병합했다(`a9331bb`).
- Verified(**쓰는 쪽 형제는 넷이고 하나는 다른 모듈에 있다**): ACTIVITY 행 writer는
  `record_route_activity`·`_write_row`·`record_rollback`(deploy_recorder) + **`record_agent_activity`
  (`operations/activity_writer.py`)**. 그중 둘만 `cost_metrics`를 쓴다. ⚠️`record_route_activity`는
  **350KB짜리 trace를 쓰면서** 그것만 안 쓴다 — `_cost_metrics`가 바로 그 trace에서 유도하므로
  "쓸 수 있는데 안 쓴다"로 읽히는 모양이다.
- Verified(**읽는 쪽으로 가니 결함이 아니라 범위였다**): cost를 렌더하는 곳은 **한 곳뿐**
  (`deployments/[id]/page.tsx`)이고 그걸 먹이는 `mergeActivity`의 선택 규칙은 `deployment_id === id`
  한 줄이다. route·provider-activity 행은 그 키가 없어 **원리상 그 뷰에 못 닿는다.** 더하면 이
  저장소가 반복해 값을 치른 **"선언됐는데 아무도 안 읽는 필드"**가 하나 는다. ⇒ **현행 유지.**
- Verified(**면제가 손으로 고른 목록인지**): 아니다. 가드가 의무를 **읽는 쪽 선택 규칙에서
  유도**하고(모듈이 아니라 `deployment_id` 보유가 기준) 범위는 `SRC_AGENTS.rglob("*.py")`라
  **전 모듈**을 덮는다 — 넷째 writer가 다른 모듈에 있어도 잡힌다. 공허 통과 방지도 있다(`>= 4`).
- Verified(**변이 3종 전부 red**, 변이·실행·복구 한 스크립트): 롤백 행에서 `cost_metrics` 제거
  (4건, db41874가 고친 그 결함) · **route에 `deployment_id` 부여**(1건 — 경계를 넘는 순간 의무가
  생긴다는 게 요지) · `"PK": "ACTIVITY"` 리터럴을 깨 스윕 무력화(1건, 공허 통과 방지가 산다).
  복구 후 8 passed, `git diff --stat` 비어 있음. 증거
  `docs/evidence/cost-metrics-exemption-is-derived-and-load-bearing.log`.
- Changed: **src 변경 0.** `NEXT_PLAN`에서 열린 잔여 → ⛔닫힘으로 이동. 진입점 stale도 고쳤다 —
  brief가 이미 닫힌 ⓒ·`rollback_release`를 무과금 다음 수로 가리키고 있었고, 4a DoD ①②는
  brief·STATUS 양쪽에서 "남은 설계 결정"인 채였다(M37이 결정·구현했다).
- Verified: `make check` **2279 passed, 2 skipped**(2026-08-18 로컬 macOS·py3.13, 35.8s) —
  08-17 숫자를 오늘 같은 기계에서 재측정해 baseline에 날짜와 기계를 적었다(Risk 12②).
- Blockers: 없음. AMP 청구액은 **08-19 이후**(CE 2일 지연 · ⚠️크레딧 제외 필터).
- Next: 08-19 이후 AMP 실제 청구액 대조.


## 2026-08-17 — 추천안 셋 수행: 점수제·조건 준수·관리형 렌더 (gate 2279)

- Status: 열려 있던 판단 셋을 **추천안대로 실행**했다. ⓒ 판별 수단 · `rollback_release`
  정책 · 4a DoD ①②. ⚠️**둘째의 전제가 측정에서 무너져 답이 바뀌었다.**
- Changed(**#1 판별 수단**): 점수 로직을 **계약 모듈**에 한 벌 두고(`schema.score_runbook`
  ·`match_text`) 세 provider가 읽는다. GCP/Azure 티어 2가 **첫 매치 대신 점수**로 고른다 →
  세 provider가 같은 인시던트에 **같은 답**(health-check = `health-check-failure`/rto **240**).
  키워드 어휘는 이미 클라우드-중립이라 **없던 건 데이터가 아니라 읽는 쪽**이었다.
- Verified(**#2의 답이 바뀌었다 — 추천 목록이 아니라 티어 2가 문제였다**): 티어 2는 액션을
  **조건 평가 없이** 추천에서 만든다. 카탈로그에서 **에스컬레이션에만 존재**하는 capability는
  넷(`expand_storage`·`rebalance_consumer`·`rollback_release`·`scale_database_read`)이고,
  그중 **둘이 GCP/Azure에서 first-response로 실행**되고 있었다 — **같은 모듈의 티어 1은 조건을
  평가한다**(M21 모양: 형제가 provider가 아니라 진입점). AWS·onprem은 추천이 액션이 안 되므로
  같은 목록이 무해하다. ⇒ **티어 2가 승자의 steps에서 액션을 만들게 고쳤다**(에스컬레이션은
  `condition_false` 로그와 함께 제외). `rollback_release`는 **추천에 넣지 않는다**(현행 유지).
  ⚠️**티어 2 액션을 단언하는 테스트가 0개였다** — 그래서 조건 무시도, 이 고침도 red를 안 냈다.
- Changed(**#3 4a DoD ①②**): 결정 = **관리형은 매니페스트를 내지 않고 read model이 부재를
  설명한다**(`applicable=False`·sync **n/a**). **새 매니페스트 종류는 발명하지 않았다.**
  ①`globex/dev`가 `amazon-managed-prometheus`를 **실제로 선언**한다(①이 ②의 하중이다) ·
  ②`DesiredAddon.managed`를 두 어댑터가 읽고 건너뛴다 · **관리형은 싱글턴 문제가 아니다**
  (설치가 없으니 두 번째 컨트롤러가 없다 — 계획서 정정 박스가 *"Prometheus CR을 주라"*는
  따를 수 없는 안내를 남긴 지점) · `ManagedBackendNotRenderable`는 **삭제**(결정이 났다).
- Verified(**변이 16종 전부 red**): 점수제 되돌리기(3·3) · 조건 무시로 되돌리기(2·2) · 공유
  점수 함수 가중 죽이기(1·15) · 관리형 표시 제거(5) · 두 어댑터가 차트를 내게(2·1) · 싱글턴이
  관리형을 삼키게(3) · **선언 되돌리기(4)** · **read model이 sync를 꾸며내게(4)**.
  `make check` **2279 passed, 2 skipped**(로컬 macOS·py3.13), ruff 신규 0.
- Blockers: 없음. ⚠️도중에 **ruff 비교용 `git stash`/`pop`이 `git rm`을 언스테이지**해
  `git ls-files`엔 있고 디스크엔 없는 파일이 생겼다 — **그걸 스캔하는 가드가 잡았다.**
- Next: 08-19 이후 AMP 청구액 대조(4a의 마지막 미측정).
