# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

## 2026-08-17 — ⓒ: 앞쪽은 맞았고 "테스트가 고정했다"가 틀렸다 (gate 2269)

- Status: 마지막 미측정 항목 **ⓒ**(*"티어 2는 첫 매치가 이긴다(AWS는 점수제) — 테스트가
  고정했으니 우연이 아니라 결정이다"*). **앞쪽은 정확하고 뒤쪽이 틀렸다.**
- Verified(**기존 가드가 생산 경로를 한 번도 안 물었다**): `test_capability_catalog_scan`의
  케이스는 **후보를 유일하게 가리는 capability 집합을 손으로 골랐다**(`["rollback_release"]` →
  health-check-failure, `["drain_node"]` → network-latency-high). ⚠️**어떤 signal 어댑터도
  그런 집합을 안 낸다** — `kubernetes-workload`엔 전부 `restart_workload`+`scale_out`을 내고
  그건 **후보 셋과 동시에 겹친다.** 즉 **첫-매치 구현과 점수제 구현이 답이 같은 경우만
  태웠다**(Risk 12⑤). 게다가 `["rollback_release"]`는 **그 세 provider가 추천하지 않는 값**이다
  (오늘 M35에서 측정) — 생산에서 도달 불가한 입력으로 통과하고 있었다.
- Verified(**실제 집합으로 물은 결과**): GCP/Azure는 OOM·health-check·latency **셋 다**
  `eks-pod-oom`/**rto 180**을 보고한다. AWS는 namespace(+2)·keyword(+1) 점수로 **셋을
  구분한다** — health-check는 `health-check-failure`/**rto 240**. 액션은 추천에서 오므로
  같지만 **운영자에게 보고되는 runbook_id·rto_sec이 다르다**(M22 계열: 사람에게 틀린 걸 보여준다).
- Verified(**catalog 규약의 안전 속성이 provider마다 다르다**): *"appending은 선택을 못
  바꾼다"*는 주석은 **AWS 점수 동점 규칙**에 대한 것이다. GCP/Azure는 점수가 없어 **순서가 곧
  알고리즘**이라, 앞에 끼운 런북이 **모든 선택을 훔친다**(실측: `thief`/rto 9999). 주석에
  provider 범위를 적고 가드로 집행했다.
- Changed: `catalog.py` 주석에 **AWS-scoped임과 "append, never insert"**를 명시. `src` 동작
  변경은 **0** — 판별 수단을 줄지는 **설계 결정**이라 손대지 않았다(`NEXT_PLAN` ⓒ).
- Changed(가드 +12, `test_tier2_selection_is_ordered_not_scored.py` 신규): 입력을 **어댑터에서
  직접 읽어** 픽스처가 생산과 어긋날 수 없게 했다 · 전제(후보>1)를 먼저 묻는다 · GCP/Azure ×
  세 인시던트 · AWS가 셋을 구분함 · **앞에 끼우면 훔치고 뒤에 붙이면 안 훔친다.**
- Verified(**변이 4종 전부 red**): 첫→마지막 매치(9건) · overlap 게이트 제거(6건) · 추천 집합
  축소로 모호성 제거(4건) · **AWS namespace 점수 죽이기(1건)**. ⚠️**마지막이 1건인 게 요지다** —
  AWS 점수제가 셋을 구분한다는 사실을 잡는 건 **오늘 만든 가드 하나뿐**이었다.
  `make check` **2269 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: 없음. ⛔설계 결정 하나가 열렸다(GCP/Azure 판별 수단) + M35의 `rollback_release` 정책.
- Next: 08-19 이후 AMP 청구액 대조.
